# -*- coding: utf-8 -*-
"""合成：动画底片 + 配音 + 字幕 +（可选）主播小窗 → 成片

用法（课程工程根目录）：
  python scripts/compose.py
  python scripts/compose.py --out dist/第1课.mp4
  python scripts/compose.py --no-deess        # 关掉去齿音
  python scripts/compose.py --no-subs         # 不要字幕

★ 时间轴一律用 ffprobe 实测的 clip 时长累加，不用渲染时声明的值。
"""
import os
import re
import sys
import json
import math
import argparse
import subprocess

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from config import cfg                          # noqa: E402

try:
    from deess_np import deess
except Exception:                                # pragma: no cover
    deess = None


def run(cmd, desc=""):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("!! FAIL %s\n%s" % (desc, r.stderr[-2500:]))
        raise SystemExit(1)
    return r


def probe_dur(p, ffprobe="ffprobe"):
    r = subprocess.run([ffprobe, "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", p], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def ass_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return "%d:%02d:%05.2f" % (h, m, s)


def split_long(text, maxlen=20):
    """按标点切，不按字数硬切（硬切会断在词中间）"""
    if len(text) <= maxlen:
        return [text]
    parts, cur = [], ""
    for ch in text:
        cur += ch
        if ch in "，、；：,;" and len(cur) >= maxlen * 0.65:
            parts.append(cur)
            cur = ""
        elif ch in "。！？":
            parts.append(cur)
            cur = ""
        elif len(cur) >= maxlen * 1.45:
            parts.append(cur)
            cur = ""
    if cur.strip():
        parts.append(cur)
    return [p for p in parts if p.strip()] or [text]


def build_subtitles(items, max_chars):
    """★用「整段原文 + 逐字时间」切字幕，不要用 TTS 的粗切行"""
    out = []
    for it in items:
        chars = it.get("chars") or []
        full = it.get("text") or "".join(ln["text"] for ln in it.get("lines", []))
        if not full:
            continue
        if not chars:                       # 没有逐字时间就退回分句时间
            for ln in it.get("lines", []):
                out.append((it["start"] + ln["start"], it["start"] + ln["end"], ln["text"]))
            continue
        pos = 0
        for sub in split_long(full, max_chars):
            k = full.find(sub, pos)
            if k < 0 or k >= len(chars):
                continue
            st = it["start"] + chars[k]["t"]
            e_idx = min(k + len(sub) - 1, len(chars) - 1)
            en = it["start"] + (chars[e_idx].get("e") or chars[e_idx]["t"] + 0.15)
            out.append((st, max(en, st + 0.3), sub))
            pos = k + len(sub)
    return out


def main():
    ap = argparse.ArgumentParser(description="合成成片")
    ap.add_argument("--slides", default="", help="slides 目录（默认 root/slides）")
    ap.add_argument("--voice", default="", help="配音目录（默认 root/voice/seg）")
    ap.add_argument("--out", default="", help="输出路径")
    ap.add_argument("--no-deess", action="store_true")
    ap.add_argument("--no-subs", action="store_true")
    a = ap.parse_args()

    c = cfg()
    root = c.root
    FF = c.path("paths.ffmpeg", "ffmpeg")
    FP = c.path("paths.ffprobe", "ffprobe")
    slides = a.slides or os.path.join(root, "slides")
    voice = a.voice or os.path.join(root, "voice", "seg")
    work = os.path.join(root, "compose")
    os.makedirs(work, exist_ok=True)

    out_path = a.out or os.path.join(root, c.text("output.dir", "dist"),
                                     c.text("course_title", "course") + ".mp4")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    tl = json.load(open(os.path.join(slides, "slide_timeline.json"), encoding="utf-8"))
    meta_path = os.path.join(voice, "meta_asr.json")
    if not os.path.exists(meta_path):
        meta_path = os.path.join(voice, "meta.json")
    meta = json.load(open(meta_path, encoding="utf-8"))
    seg_path = os.path.join(root, "segments.json")
    segs = {}
    if os.path.exists(seg_path):
        segs = {str(s["id"]): s.get("text", "")
                for s in json.load(open(seg_path, encoding="utf-8"))["segments"]}

    # ---- 时间轴：★用实测时长累加 ----
    items, t = [], 0.0
    for it in tl:
        k = str(it["sid"])
        if k not in meta:
            print("!! 缺少 seg %s 的音频，跳过" % k)
            continue
        real = probe_dur(it["clip"], FP) or it["dur"]      # 实测优先
        items.append({"sid": it["sid"], "chapter": it["chapter"], "clip": it["clip"],
                      "start": round(t, 3), "vid": real, "aud": meta[k]["dur"],
                      "lines": meta[k].get("lines", []),
                      "chars": meta[k].get("chars") or [],
                      "text": meta[k].get("text") or segs.get(k, "")})
        t += real
    total = t
    print("%d 页，总时长 %.1fs = %.2f min" % (len(items), total, total / 60))

    # ---- 1. 拼视频 ----
    lst = os.path.join(work, "vlist.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for it in items:
            f.write("file '%s'\n" % it["clip"].replace("\\", "/"))
    vbase = os.path.join(work, "video_base.mp4")
    run([FF, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", lst, "-c", "copy", vbase], "concat video")
    print("video_base ok")

    # ---- 2. 拼音频（每段后补静音，与画面时长对齐）----
    pieces, sr = [], None
    for it in items:
        p = os.path.join(voice, "seg_%02d.wav" % it["sid"])
        x, sr = sf.read(p, dtype="float32")
        if x.ndim > 1:
            x = x.mean(axis=1)
        pad = int(sr * max(0.0, it["vid"] - len(x) / sr))
        pieces.append(np.concatenate([x, np.zeros(pad, dtype=np.float32)]))
    audio = np.concatenate(pieces)

    # ---- 3. 去齿音（可选）----
    if not a.no_deess and deess is not None:
        audio, gmax, gmean = deess(audio, sr)
        print("去齿音：最大衰减 %.2f dB / 平均 %.2f dB" % (gmax, gmean))

    # ---- 4. 响度对齐 + tanh 软膝限幅 ----
    rms_db = 20 * math.log10(max(float(np.sqrt(np.mean(audio ** 2))), 1e-9))
    audio = audio * (10 ** ((-16.2 - rms_db) / 20))
    thr = 10 ** (-1.0 / 20)
    knee = thr * 0.65
    ab = np.abs(audio)
    audio = np.sign(audio) * np.where(
        ab > knee, knee + (thr - knee) * np.tanh((ab - knee) / (thr - knee)), ab)
    audio = audio.astype(np.float32)

    apath = os.path.join(work, "audio.wav")
    sf.write(apath, audio, sr)
    new_rms = 20 * math.log10(max(float(np.sqrt(np.mean(audio ** 2))), 1e-9))
    print("audio %.2fs  rms %.1f -> %.1f dB  peak %.1f dB"
          % (len(audio) / sr, rms_db, new_rms,
             20 * math.log10(max(float(np.max(np.abs(audio))), 1e-9))))

    # ---- 5. 字幕 ----
    ass = os.path.join(work, "subs.ass")
    n_lines = 0
    if not a.no_subs:
        subs = build_subtitles(items, int(c.get("subtitle.max_chars", 20)))
        n_lines = len(subs)
        font = c.text("subtitle.font", "Microsoft YaHei")
        size = int(c.get("subtitle.size", 44))
        with open(ass, "w", encoding="utf-8") as f:
            f.write("[Script Info]\nScriptType: v4.00+\n"
                    "PlayResX: %d\nPlayResY: %d\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
                    % (c.get("video.width", 1920), c.get("video.height", 1080)))
            f.write("[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, "
                    "SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
                    "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
                    "Alignment, MarginL, MarginR, MarginV, Encoding\n")
            f.write("Style: Default,%s,%d,&H00FFFFFF,&H00FFFFFF,&H00202020,&H00000000,"
                    "0,0,0,0,100,100,0,0,1,2.4,0,2,70,490,30,1\n\n" % (font, size))
            f.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, "
                    "MarginV, Effect, Text\n")
            for st, en, txt in subs:
                if en - st < 0.06:
                    en = st + 0.06
                f.write("Dialogue: 0,%s,%s,Default,,0,0,0,,%s\n"
                        % (ass_time(st), ass_time(en), txt))
        print("字幕 %d 行" % n_lines)

    # ---- 6. 合成 ----
    W = int(c.get("video.width", 1920))
    H = int(c.get("video.height", 1080))
    avatar = c.get("video.avatar")
    if avatar:
        avatar = avatar if os.path.isabs(avatar) else os.path.join(root, avatar)

    vfilters = []
    inputs = ["-i", vbase]
    if avatar and os.path.exists(avatar):
        ax, ay, aw, ah = c.get("video.avatar_box", [1500, 840, 420, 240])
        # ★-stream_loop -1 放在它作用的 -i 之前，否则素材播完会定格
        inputs += ["-stream_loop", "-1", "-i", avatar]
        vfilters.append("[0:v][1:v]overlay=%d:%d:shortest=0[bg]" % (ax, ay))
        last = "[bg]"
    else:
        last = "[0:v]"

    if not a.no_subs and c.get("subtitle.band", True):
        y = H - 84
        vfilters.append("%sdrawbox=x=0:y=%d:w=%d:h=84:color=black@0.52:t=fill[b2]"
                        % (last, y, W - 420))
        last = "[b2]"

    if not a.no_subs and n_lines:
        esc = ass.replace("\\", "/").replace(":", "\\:")
        vfilters.append("%sass='%s'[v]" % (last, esc))
        last = "[v]"

    fc = ";".join(vfilters) if vfilters else None
    cmd = [FF, "-hide_banner", "-loglevel", "error", "-y"] + inputs + ["-i", apath]
    if fc:
        cmd += ["-filter_complex", fc, "-map", last]
    else:
        cmd += ["-map", "0:v"]
    cmd += ["-map", "%d:a" % (2 if (avatar and os.path.exists(avatar)) else 1),
            "-t", "%.3f" % total,
            "-c:v", "libx264", "-preset", c.text("video.preset", "medium"),
            "-crf", str(c.get("video.crf", 19)), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart", out_path]
    run(cmd, "final mux")

    size = os.path.getsize(out_path) / 1048576
    print("FINAL: %s  %.1f MB  %.2f min" % (out_path, size, total / 60))


if __name__ == "__main__":
    main()
