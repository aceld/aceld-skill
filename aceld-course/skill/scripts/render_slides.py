# -*- coding: utf-8 -*-
"""按真实时间轴逐页渲染幻灯片 → clips/slide_XX.mp4 + slide_timeline.json

用法（课程工程根目录）：
  python scripts/render_slides.py             # 正常渲染
  python scripts/render_slides.py --test      # 用假时长快速自检（不依赖配音）
  python scripts/render_slides.py --only 3,7  # 只重渲这几页

时间轴来源优先级：
  1. voice/seg/meta_asr.json 的 chars[]（逐字真实时间，推荐）
  2. voice/seg/meta.json 的 lines[]（分句时间）
  3. --test 假时长
"""
import os
import re
import sys
import json
import time
import shutil
import argparse
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from config import cfg                           # noqa: E402

from playwright.sync_api import sync_playwright   # noqa: E402


# ---------------- 工具 ----------------

def probe_dur(path, ffprobe="ffprobe"):
    """用 ffprobe 读真实时长（秒）。★不要用渲染时声明的 dur"""
    r = subprocess.run([ffprobe, "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def resolve_steps(steps, chars, text, dur):
    """把 [触发词, 选择器, 动效, 持续秒] 解析成绝对时间 [起始秒, 选择器, 动效, 持续秒]

    chars: [{"c": "字", "t": 0.12, "e": 0.25}, ...] 逐字时间（可为 None）
    """
    out = []
    n = len(steps)
    for k, s in enumerate(steps):
        cue = str(s[0])
        sel = s[1]
        fx = s[2]
        d = float(s[3]) if len(s) > 3 else 0.6

        if cue.startswith("@"):                       # 手写比例，兜底用
            t = float(cue[1:]) * dur
        elif chars:                                   # 真实时间：触发词 → 字索引 → 时间
            idx = text.find(cue) if not cue.endswith("#2") else text.find(cue[:-2], text.find(cue[:-2]) + 1)
            if idx >= 0 and idx < len(chars):
                t = float(chars[idx]["t"])
            else:
                t = dur * (k + 1) / (n + 1)
        else:                                         # 无对齐数据：均匀铺开
            t = dur * (k + 1) / (n + 1)
        out.append([round(min(t, max(0.0, dur - 0.05)), 3), sel, fx, d])
    return out


def build_times(steps, dur, fps):
    """关键帧时间点集合：每步的起点 + 终点，加上首尾"""
    ts = {0.0, round(dur, 4)}
    for s in steps:
        t0 = float(s[0])
        d = float(s[3]) if len(s) > 3 else 0.6
        if t0 > dur:
            continue
        t1 = min(t0 + d, dur)
        k = 0
        while True:
            t = t0 + k / fps
            if t > t1 + 1e-6:
                break
            ts.add(round(t, 4))
            k += 1
    return sorted(t for t in ts if t <= dur)


def make_seq(paths, times, dur, fps, seqdir):
    """★按 duration 建硬链接帧序列（不占磁盘），帧号 = 时间 × fps，可验证"""
    os.makedirs(seqdir, exist_ok=True)
    for f in os.listdir(seqdir):
        if f.endswith(".png"):
            os.remove(os.path.join(seqdir, f))
    n_out = 0
    for k, pth in enumerate(paths):
        d = (times[k + 1] - times[k]) if k + 1 < len(times) else (dur - times[k])
        n = max(1, int(round(d * fps)))
        for _ in range(n):
            dst = os.path.join(seqdir, "%05d.png" % n_out)
            try:
                os.link(pth, dst)          # 同 inode，不占空间
            except OSError:
                shutil.copy(pth, dst)
            n_out += 1
    return n_out


# ---------------- 主流程 ----------------

def main():
    ap = argparse.ArgumentParser(description="渲染幻灯片")
    ap.add_argument("--test", action="store_true", help="用假时长自检")
    ap.add_argument("--only", default="", help="只渲染指定 sid，逗号分隔")
    ap.add_argument("--deck", default="", help="slides 目录（默认 root/slides）")
    ap.add_argument("--voice", default="", help="配音目录（默认 root/voice/seg）")
    a = ap.parse_args()

    c = cfg()
    root = c.root
    FPS = int(c.get("video.fps", 30))
    TAIL = float(c.get("video.tail", 0.70))
    FF = c.path("paths.ffmpeg", "ffmpeg")
    FP = c.path("paths.ffprobe", "ffprobe")
    CHROME = c.text("paths.chrome_channel", "chrome")

    deck_dir = a.deck or os.path.join(root, "slides")
    voice_dir = a.voice or os.path.join(root, "voice", "seg")
    frames_dir = os.path.join(deck_dir, "frames")
    clips_dir = os.path.join(deck_dir, "clips")
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(clips_dir, exist_ok=True)

    meta_path = os.path.join(deck_dir, "deck_meta.json")
    if not os.path.exists(meta_path):
        raise SystemExit("请先运行 build_deck.py 生成 deck_meta.json")
    meta = json.load(open(meta_path, encoding="utf-8"))

    # ---- 时长与逐字时间 ----
    segdur, segchars, seglines = {}, {}, {}
    meta_asr = os.path.join(voice_dir, "meta_asr.json")
    meta_tts = os.path.join(voice_dir, "meta.json")
    if not a.test and os.path.exists(meta_asr):
        d = json.load(open(meta_asr, encoding="utf-8"))
        for k, v in d.items():
            segdur[k] = float(v.get("dur", 0))
            segchars[k] = v.get("chars")
            seglines[k] = v.get("lines", [])
    elif not a.test and os.path.exists(meta_tts):
        d = json.load(open(meta_tts, encoding="utf-8"))
        for k, v in d.items():
            segdur[k] = float(v.get("dur", 0))
            seglines[k] = v.get("lines", [])

    only = {int(x) for x in re.findall(r"\d+", a.only)} if a.only else None
    deck_url = "file:///" + os.path.join(deck_dir, "deck.html").replace("\\", "/")

    timeline, total_frames, t_all = [], 0, time.time()

    with sync_playwright() as pw:
        b = pw.chromium.launch(channel=CHROME)
        pg = b.new_page(viewport={"width": int(c.get("video.width", 1920)),
                                  "height": int(c.get("video.height", 1080))},
                        device_scale_factor=1)
        pg.goto(deck_url)
        pg.wait_for_timeout(400)

        for m in meta:
            i, sid = m["i"], m["sid"]
            key = str(sid)
            out = os.path.join(clips_dir, "slide_%02d.mp4" % i)

            if only is not None and sid not in only and os.path.exists(out):
                d = probe_dur(out, FP)          # ★跳过的页也取真实时长
                timeline.append({"i": i, "sid": sid, "chapter": m["chapter"],
                                 "dur": round(d, 3), "clip": out, "frames": int(round(d * FPS))})
                print("  [%02d] %-24s %7.2fs  沿用旧 clip" % (i, m["chapter"][:22], d))
                continue

            if a.test or key not in segdur:
                dur = 6.0 + 1.5 * len(m["steps"]) + TAIL
            else:
                dur = segdur[key] + TAIL

            fdir = os.path.join(frames_dir, "s%02d" % i)
            os.makedirs(fdir, exist_ok=True)
            for f in os.listdir(fdir):
                if f.endswith(".png"):
                    os.remove(os.path.join(fdir, f))

            text = m.get("text", "")
            steps_abs = resolve_steps(m["steps"], segchars.get(key), text, dur)

            pg.evaluate("a => { showSlide(a[0]); buildSteps(a[1]); }", [i, steps_abs])
            times = build_times(steps_abs, dur, FPS)

            paths = []
            for k, t in enumerate(times):
                pg.evaluate("t => seek(t)", t)
                p = os.path.join(fdir, "%05d.png" % k)
                pg.screenshot(path=p)
                paths.append(p)

            n_frames = make_seq(paths, times, dur, FPS, os.path.join(fdir, "seq"))
            r = subprocess.run(
                [FF, "-hide_banner", "-loglevel", "error", "-y",
                 "-framerate", str(FPS), "-i", os.path.join(fdir, "seq", "%05d.png"),
                 "-r", str(FPS),
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                 "-pix_fmt", "yuv420p", out],
                capture_output=True, text=True)
            if r.returncode != 0:
                print("FFMPEG FAIL", r.stderr[-800:])
                raise SystemExit(1)

            real = probe_dur(out, FP)          # ★以实测为准
            timeline.append({"i": i, "sid": sid, "chapter": m["chapter"],
                             "dur": round(real, 3), "clip": out, "frames": n_frames})
            total_frames += n_frames
            print("  [%02d] %-24s %7.2fs  %5d帧  (%.1fs)"
                  % (i, m["chapter"][:22], real, n_frames, time.time() - t_all), flush=True)

        b.close()

    json.dump(timeline, open(os.path.join(deck_dir, "slide_timeline.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    total = sum(x["dur"] for x in timeline)
    print("\n完成：%d 页 / %d 帧 / %.1f 分钟" % (len(timeline), total_frames, (time.time() - t_all) / 60))
    print("总时长 %.2f 分钟" % (total / 60))
    if not a.test:
        expect = int(round(total * FPS))
        print("帧数核对：期望 ≈ %d，实际关键帧 %d（应 ≥ 期望的 1/10）" % (expect, total_frames))


if __name__ == "__main__":
    main()
