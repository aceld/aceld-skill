# -*- coding: utf-8 -*-
"""配音：CosyVoice2 零样本音色克隆 + 后处理（+ 可选 ASR 质检）

用法（课程工程根目录）：
  python scripts/tts_cosy.py                 # 全部段落
  python scripts/tts_cosy.py --only 3,7      # 只重配指定段
  python scripts/tts_cosy.py --qc            # 边配边做 ASR 质检（慢，但能早发现丢字）

★ 三条不要动的东西：
  1. speed = 1.0（改 speed 是频谱线性拉伸，会发闷且调不回来）
  2. 淡出 6ms（不是 28ms，否则句末轻声被削掉）
  3. 静音裁剪「头部严 0.08 / 尾部宽 0.015」
"""
import os
import re
import sys
import json
import time
import argparse

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from config import cfg                        # noqa: E402
from num2cn import num2cn                     # noqa: E402


# ---------------- 文本预处理 ----------------

def speak_text(t: str) -> str:
    """阿拉伯数字 / 百分号 → 中文读法（避免 TTS 把 2.0 读成乱码）"""
    t = re.sub(r"(\d+(?:\.\d+)?)\s*%", lambda m: "百分之" + num2cn(m.group(1)), t)
    return num2cn(t)


def apply_repl(t: str, repl) -> str:
    """发音替换：只改送模型的文本，字幕仍用原文"""
    for a, b in repl:
        t = t.replace(a, b)
    # 替换后清掉中文之间的多余空格
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", t)


# ---------------- 后处理 ----------------

def trim(a, sr, thr_ratio=0.08, pad_ms=6, run=3, tail_ratio=0.015, tail_pad_ms=40):
    """裁首尾静音/噪声。

    头部阈值要高（0.08 ≈ -22dB），否则 vocoder 的 -34dB 残留噪声会被当成语音起音，
    听起来就是句首那一声「杂质」；run=3 要求连续 3 帧超阈值才算真正起音。

    ★尾部要用更宽的阈值（0.015）：句末常是轻声（的/了/干/停），用 0.08 会被当静音裁掉。
    """
    win = int(sr * 0.01)
    if len(a) < win * (run + 2):
        return a
    n = len(a) // win
    e = np.sqrt(np.mean(a[:n * win].reshape(n, win) ** 2, axis=1))
    peak = float(e.max()) or 1.0

    on = e > max(peak * thr_ratio, 0.01)
    start = None
    for i in range(len(on) - run + 1):
        if on[i:i + run].all():
            start = i
            break

    on_tail = e > max(peak * tail_ratio, 0.004)
    end = None
    for i in range(len(on_tail) - 1, -1, -1):
        if on_tail[i]:
            end = i + 1
            break

    if start is None or end is None or end <= start:
        return a
    pad = int(sr * pad_ms / 1000)
    tpad = int(sr * tail_pad_ms / 1000)
    return a[max(0, start * win - pad): min(len(a), end * win + tpad)]


def fade(a, sr, ms=6):
    """首尾淡入淡出，消除拼接处的波形阶跃（爆音）。★6ms，不是 28ms"""
    n = int(sr * ms / 1000)
    if len(a) < 2 * n or n <= 0:
        return a
    a = a.copy()
    a[:n] *= np.linspace(0, 1, n, dtype=a.dtype)
    a[-n:] *= np.linspace(1, 0, n, dtype=a.dtype)
    return a


def prep(a, sr):
    """去 DC 偏移 → 裁静音 → 首尾淡化。三者缺一都会在拼接处爆音。"""
    a = np.asarray(a, dtype=np.float32).squeeze()
    a = a - float(a.mean())
    a = trim(a, sr)
    return fade(a, sr, 6)


# ---------------- 主流程 ----------------

def main():
    ap = argparse.ArgumentParser(description="CosyVoice2 配音")
    ap.add_argument("--segments", default="", help="讲稿 JSON，默认 root/segments.json")
    ap.add_argument("--out", default="", help="输出目录，默认 root/voice/seg")
    ap.add_argument("--only", default="", help="只配指定 sid，逗号分隔")
    ap.add_argument("--qc", action="store_true", help="开启 ASR 质检")
    ap.add_argument("--force", action="store_true", help="覆盖已有 wav")
    a = ap.parse_args()

    c = cfg()
    root = c.root
    seg_path = a.segments or os.path.join(root, "segments.json")
    outdir = a.out or os.path.join(root, "voice", "seg")
    os.makedirs(outdir, exist_ok=True)

    REF_AUDIO = c.path("voice.ref_file")
    REF_TEXT = c.text("voice.ref_text")
    SPEED = float(c.get("voice.speed", 1.0))
    GAP = float(c.get("voice.gap_sent", 0.60))
    REPL = c.repl()

    if not os.path.exists(REF_AUDIO):
        raise SystemExit("找不到音色参考音频：%s\n请在 course.yaml 里配置 voice.ref_file" % REF_AUDIO)
    if not REF_TEXT:
        raise SystemExit("course.yaml 里 voice.ref_text 为空——必须是参考音频里说的话，一字不差")
    if abs(SPEED - 1.0) > 1e-6:
        print("!! 警告：speed=%.2f，非 1.0 会对频谱做线性拉伸，可能发闷。建议改回 1.0" % SPEED)

    # ---- 载入 CosyVoice ----
    COSY = c.path("paths.cosyvoice")
    MODEL = c.path("paths.cosyvoice_model")
    sys.path.insert(0, COSY)
    sys.path.insert(0, os.path.join(COSY, "third_party", "Matcha-TTS"))
    sys.path.insert(0, os.path.join(COSY, "third_party", "Matcha-TTS", "matcha"))

    import torch
    import torchaudio
    import soxr
    from cosyvoice.cli.cosyvoice import CosyVoice2

    # Windows 上 torchcodec 的 DLL 常加载失败，用 soundfile 顶掉 torchaudio 的读写
    def _sf_load(path, **kw):
        x, sr = sf.read(str(path), dtype="float32")
        if x.ndim > 1:
            x = x.mean(axis=1)
        return torch.from_numpy(np.asarray(x, dtype=np.float32)).unsqueeze(0), sr

    torchaudio.load = _sf_load
    torchaudio.save = lambda p, w, sr, **kw: sf.write(str(p), w.squeeze().cpu().numpy(), int(sr))

    print("加载 CosyVoice2 ...", flush=True)
    t0 = time.time()
    cosy = CosyVoice2(MODEL, load_jit=False, load_trt=False, fp16=False)
    sr_out = cosy.sample_rate
    print("加载完成 %.1fs，采样率 %d，speed=%.2f" % (time.time() - t0, sr_out, SPEED), flush=True)

    # ---- 参考音频 ----
    x, sr = sf.read(REF_AUDIO, dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != 16000:
        x = soxr.resample(x, sr, 16000)
    prompt = torch.from_numpy(np.asarray(x, dtype=np.float32)).unsqueeze(0)
    print("参考音频 %.2fs @16k" % (prompt.shape[-1] / 16000), flush=True)

    # ---- 可选：ASR 质检 ----
    wm = None
    if a.qc:
        from faster_whisper import WhisperModel
        wm = WhisperModel(c.text("paths.whisper_model", "large-v3"), device="cuda", compute_type="float16")
        print("ASR 质检已开启", flush=True)

    def gen(text):
        parts = []
        for j in cosy.inference_zero_shot(apply_repl(text, REPL), REF_TEXT, prompt,
                                          stream=False, speed=SPEED):
            parts.append(prep(j["tts_speech"].cpu().numpy().squeeze(), sr_out))
        if not parts:
            raise RuntimeError("没有产生音频")
        gap = np.zeros(int(sr_out * GAP), dtype=np.float32)
        out = []
        for k, p in enumerate(parts):
            out.append(p)
            if k < len(parts) - 1:
                out.append(gap)
        return np.concatenate(out)

    def qc_score(path, expected):
        segs, _ = wm.transcribe(path, language="zh", beam_size=1,
                                vad_filter=True, condition_on_previous_text=False)
        heard = "".join(s.text for s in segs)
        a = re.sub(r"[^\u4e00-\u9fff0-9]", "", num2cn(expected))
        b = re.sub(r"[^\u4e00-\u9fff0-9]", "", heard)
        if not b:
            return 0.0
        import difflib
        return difflib.SequenceMatcher(None, a, b).ratio()

    # ---- 逐段生成 ----
    segs = json.load(open(seg_path, encoding="utf-8"))["segments"]
    only = {int(v) for v in re.findall(r"\d+", a.only)} if a.only else None
    meta_path = os.path.join(outdir, "meta.json")
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {}

    total = 0.0
    for s in segs:
        sid = s["id"]
        if only is not None and sid not in only:
            continue
        p = os.path.join(outdir, "seg_%02d.wav" % sid)
        if os.path.exists(p) and not a.force:
            d = sf.info(p).duration
            total += d
            print("[skip] seg %02d  %.1fs" % (sid, d), flush=True)
            continue

        t0 = time.time()
        try:
            audio = gen(s["text"])
        except Exception as e:
            print("[FAIL] seg %02d  %s" % (sid, e), flush=True)
            continue

        pk = float(np.abs(audio).max()) or 1.0
        if pk > 0.92:
            audio = audio / pk * 0.9
        sf.write(p, audio, sr_out, subtype="FLOAT")
        dur = len(audio) / sr_out
        total += dur

        score = qc_score(p, s["text"]) if wm else None

        # 字幕行先按字数粗分（align_asr.py 会用 ASR 重新精确对齐）
        text = s["text"]
        n_sent = max(1, len([ch for ch in text if ch in "。！？"]) or 1)
        step = max(1, int(len(text) / n_sent))
        lines, t = [], 0.0
        for i in range(0, len(text), step):
            part = text[i:i + step]
            d = dur * len(part) / len(text)
            lines.append({"text": part, "tts": apply_repl(part, REPL),
                          "start": round(t, 2), "end": round(t + d, 2)})
            t += d

        meta[str(sid)] = {"dur": round(dur, 3), "sents": len(lines), "lines": lines}
        json.dump(meta, open(meta_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

        qc = "" if score is None else "  qc=%.2f%s" % (score, "  << 低分，建议重配" if score < 0.90 else "")
        print("[ok] seg %02d  %.1fs  %d字  %.0f字/分  /%.0fs%s"
              % (sid, dur, len(text), len(text) / dur * 60, time.time() - t0, qc), flush=True)

    print("\nDONE. 合计 %.1fs = %.2fmin" % (total, total / 60))


if __name__ == "__main__":
    main()
