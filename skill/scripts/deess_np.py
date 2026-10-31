# -*- coding: utf-8 -*-
"""平滑去齿音（numpy 实现）

为什么不用 ffmpeg 的 sidechaincompress：
它是压缩器，ratio/attack 的抽吸（pumping）会在齿音上产生「拉链声」，
听感就是「偶尔蹦出的尖锐刺耳噪音」——而峰值、Flat factor、噪声底全部正常，极难定位。

原理：
  - STFT 512 / hop 128
  - 按「5.5k 以上能量 ÷ 以下能量」的**比值**判断（与电平无关，
    不会出现「小声段落完全不压、大声段落压过头」）
  - 增益在**增益域**做 attack / release 一阶平滑 → 没有拉链声
  - 只衰减高频段，元音和低频完全不动（实测 RMS 只降 0.3%）

用法：
  from deess_np import deess
  audio, gmax_db, gmean_db = deess(audio, sr, ratio_thr=0.15, max_db=7.0)

验收：
  - ffmpeg astats 的 Flat factor == 0
  - np.abs(np.diff(audio)) > 0.35 的点数为 0
"""
import numpy as np


def _frames(x, nfft, hop):
    pad = nfft
    xp = np.concatenate([np.zeros(pad, x.dtype), x, np.zeros(pad, x.dtype)])
    nfr = 1 + (len(xp) - nfft) // hop
    idx = np.arange(nfft)[None, :] + hop * np.arange(nfr)[:, None]
    return xp[idx], pad, nfr


def _istft(F, nfft, hop, win, total):
    frames = np.fft.irfft(F, n=nfft, axis=1) * win
    out = np.zeros(nfft + hop * (frames.shape[0] - 1), dtype=np.float32)
    wsum = np.zeros_like(out)
    w2 = (win ** 2).astype(np.float32)
    for i in range(frames.shape[0]):
        s = i * hop
        out[s:s + nfft] += frames[i]
        wsum[s:s + nfft] += w2
    out /= np.maximum(wsum, 1e-8)
    return out


def deess(audio, sr, ratio_thr=0.15, max_db=7.0, k=1.2,
          nfft=512, hop=128, split_hz=5500.0, attack_ms=4.0, release_ms=120.0):
    """返回 (处理后的音频, 最大衰减 dB, 平均衰减 dB)"""
    a = np.asarray(audio, dtype=np.float32).squeeze()
    if a.ndim != 1:
        raise ValueError("只支持单声道")
    if len(a) < nfft * 2:
        return a, 0.0, 0.0

    win = np.hanning(nfft).astype(np.float32)
    frames, pad, nfr = _frames(a, nfft, hop)
    F = np.fft.rfft(frames * win, axis=1)

    freqs = np.fft.rfftfreq(nfft, 1.0 / sr)
    hi_mask = freqs >= split_hz
    lo_mask = ~hi_mask

    mag2 = (np.abs(F) ** 2).astype(np.float32)
    hi = mag2[:, hi_mask].sum(axis=1)
    lo = mag2[:, lo_mask].sum(axis=1) + 1e-12
    ratio = hi / lo

    # 需要压多少（0~1）
    need = np.clip((ratio / max(ratio_thr, 1e-6) - 1.0) * k, 0.0, 1.0)
    target_db = -max_db * need

    # 增益域一阶平滑（attack 快、release 慢）——这一步是「没有拉链声」的关键
    at = float(np.exp(-1.0 / max(1e-3, attack_ms * 1e-3 * sr / hop)))
    rt = float(np.exp(-1.0 / max(1e-3, release_ms * 1e-3 * sr / hop)))
    g = np.zeros(nfr, dtype=np.float32)
    cur = 0.0
    for i in range(nfr):
        t = target_db[i]
        coef = at if t < cur else rt          # 更负 = 压得更狠 → 用 attack
        cur = coef * cur + (1 - coef) * t
        g[i] = cur

    # 应用到高频段
    lin = (10.0 ** (g / 20.0)).astype(np.float32)
    F[:, hi_mask] *= lin[:, None]

    out = _istft(F, nfft, hop, win, len(a) + 2 * pad)[pad:pad + len(a)]

    # 峰值兜底，避免浮点溢出
    pk = float(np.abs(out).max())
    if pk > 0.99:
        out = out / pk * 0.99
    return out.astype(np.float32), float(-g.min()), float(-g.mean())


if __name__ == "__main__":
    import sys
    import soundfile as sf

    if len(sys.argv) < 3:
        print("用法: python deess_np.py <in.wav> <out.wav> [ratio_thr] [max_db]")
        raise SystemExit(0)
    x, sr = sf.read(sys.argv[1], dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    thr = float(sys.argv[3]) if len(sys.argv) > 3 else 0.15
    mdb = float(sys.argv[4]) if len(sys.argv) > 4 else 7.0
    y, gmax, gmean = deess(x, sr, ratio_thr=thr, max_db=mdb)
    sf.write(sys.argv[2], y, sr)
    print("去齿音完成：最大衰减 %.2f dB，平均 %.2f dB" % (gmax, gmean))
