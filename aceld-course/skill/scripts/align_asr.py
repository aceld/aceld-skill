# -*- coding: utf-8 -*-
"""ASR 强制对齐：把 TTS 文本逐字对到真实语音时间上 → meta_asr.json

流程：
  1) faster-whisper 词级转写，得到每个词的起止时间
  2) 把词展开成「字 → 时间」序列（词内按时长均分）
  3) difflib 把 TTS 文本（去标点）与该序列做字符级对齐
  4) 未匹配到的字用前后锚点线性插值
  5) 逐句给出真实起止；再把原文字符映射到 TTS 字符，得到每个原文字的时间

产出：
  voice/seg/meta_asr.json
  { "0": {"dur": 12.3,
          "lines": [{"text","tts","start","end"}],
          "chars": [{"c","t","e"}] } }

用法：
  python scripts/align_asr.py
  python scripts/align_asr.py --only 3,7
"""
import os
import re
import sys
import json
import argparse
import difflib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from config import cfg                          # noqa: E402

CJK = re.compile(r"[\u4e00-\u9fff]")


def keep(ch):
    return bool(CJK.match(ch)) or ch.isalnum()


def transcribe(path, model):
    """★VAD 必开：否则 Whisper 会在静音处幻觉出假词。
       抗重复三件套：compression_ratio + 温度回退 + no_repeat_ngram。"""
    segs, _info = model.transcribe(
        path, language="zh", word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=300, speech_pad_ms=120),
        beam_size=5,
        condition_on_previous_text=False,
        compression_ratio_threshold=2.0,
        no_speech_threshold=0.5,
        log_prob_threshold=-1.0,
        temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        repetition_penalty=1.05,
        no_repeat_ngram_size=4,
    )
    words = []
    for s in segs:
        for w in (s.words or []):
            t = w.word.strip()
            if t:
                words.append((t, float(w.start), float(w.end)))
    return words


def char_times(words):
    """词 → 字序列 [(ch, t0, t1)]，词内按时长均分"""
    out = []
    for w, a, b in words:
        cs = [c for c in w if keep(c)]
        if not cs:
            continue
        d = (b - a) / len(cs)
        for i, c in enumerate(cs):
            out.append((c, a + d * i, a + d * (i + 1)))
    return out


def align_to_tts(tts_text, ct):
    """返回 {tts 字符索引: (t0, t1)}，未匹配的用前后锚点插值"""
    tchars = [(i, c) for i, c in enumerate(tts_text) if keep(c)]
    tstr = "".join(c for _, c in tchars)
    astr = "".join(c for c, _, _ in ct)
    n = len(tchars)
    res = [None] * n
    if n == 0 or not astr:
        return {}

    sm = difflib.SequenceMatcher(None, tstr, astr, autojunk=False)
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            res[a + k] = (ct[b + k][1], ct[b + k][2])

    known = [i for i, r in enumerate(res) if r]
    if not known:
        return {tchars[i][0]: (0.0, 0.0) for i in range(n)}
    for i in range(n):
        if res[i]:
            continue
        prev = max((k for k in known if k < i), default=None)
        nxt = min((k for k in known if k > i), default=None)
        if prev is None:
            res[i] = res[nxt]
        elif nxt is None:
            res[i] = res[prev]
        else:
            r = (i - prev) / (nxt - prev)
            a = res[prev][1] + (res[nxt][0] - res[prev][1]) * r
            res[i] = (a, a)

    last = 0.0
    for i in range(n):
        a, b = res[i]
        a = max(a, last)
        b = max(b, a)
        res[i] = (a, b)
        last = b
    return {tchars[i][0]: res[i] for i in range(n)}


def map_orig(orig, tts, ttimes):
    """原文字符 → 时间。tts 与 orig 长度可能不同（数字转中文会变长）"""
    oi = [(i, c) for i, c in enumerate(orig) if keep(c)]
    ti = [(i, c) for i, c in enumerate(tts) if keep(c)]
    ostr = "".join(c for _, c in oi)
    tstr = "".join(c for _, c in ti)
    out = [None] * len(orig)

    sm = difflib.SequenceMatcher(None, ostr, tstr, autojunk=False)
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            out[oi[a + k][0]] = ttimes.get(ti[b + k][0])

    known = [(i, out[i]) for i in range(len(out)) if out[i]]
    if not known:
        return [(c, 0.0, 0.0) for c in orig]
    for i in range(len(out)):
        if out[i] is None:
            prev = max((k for k, _ in known if k < i), default=None)
            nxt = min((k for k, _ in known if k > i), default=None)
            out[i] = out[prev] if prev is not None else out[nxt]
    return [(c, out[i][0], out[i][1]) for i, c in enumerate(orig)]


def main():
    ap = argparse.ArgumentParser(description="ASR 强制对齐")
    ap.add_argument("--voice", default="", help="配音目录，默认 root/voice/seg")
    ap.add_argument("--segments", default="", help="讲稿，默认 root/segments.json")
    ap.add_argument("--only", default="", help="只对齐指定 sid")
    ap.add_argument("--dev", default="cuda", help="cuda / cpu")
    a = ap.parse_args()

    # faster-whisper 用 GPU 需要 torch 的 CUDA DLL 在搜索路径上
    try:
        import torch
        _l = os.path.join(os.path.dirname(torch.__file__), "lib")
        if os.path.isdir(_l):
            os.add_dll_directory(_l)
            os.environ["PATH"] = _l + os.pathsep + os.environ.get("PATH", "")
    except Exception as e:
        print("torch 未就绪（可忽略，会走 CPU）:", e, flush=True)

    from faster_whisper import WhisperModel

    c = cfg()
    root = c.root
    voice = a.voice or os.path.join(root, "voice", "seg")
    seg_path = a.segments or os.path.join(root, "segments.json")
    out_path = os.path.join(voice, "meta_asr.json")

    meta = json.load(open(os.path.join(voice, "meta.json"), encoding="utf-8"))
    segs = {s["id"]: s for s in json.load(open(seg_path, encoding="utf-8"))["segments"]}

    cache_path = os.path.join(voice, "words.json")
    cache = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {}

    holder = {"m": None}

    def get_model():
        if holder["m"] is None:
            name = c.text("paths.whisper_model", "large-v3")
            try:
                print("loading faster-whisper %s (%s) ..." % (name, a.dev), flush=True)
                holder["m"] = WhisperModel(name, device=a.dev,
                                           compute_type="float16" if a.dev == "cuda" else "int8")
            except Exception as e:
                print("GPU 不可用，退回 CPU int8:", str(e)[:200], flush=True)
                holder["m"] = WhisperModel(name, device="cpu", compute_type="int8")
        return holder["m"]

    want = {int(x) for x in re.findall(r"\d+", a.only)} if a.only else None
    out = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}

    for sid_s, m in sorted(meta.items(), key=lambda x: int(x[0])):
        sid = int(sid_s)
        if want and sid not in want:
            continue
        wav = os.path.join(voice, "seg_%02d.wav" % sid)
        if not os.path.exists(wav):
            print("[miss] seg %02d" % sid, flush=True)
            continue

        words = cache.get(sid_s)
        if not words:
            words = transcribe(wav, get_model())
            cache[sid_s] = words
            json.dump(cache, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False)

        ct = char_times(words)
        tts_all = "".join(ln["tts"] for ln in m["lines"])

        if not ct:
            print("[warn] seg %02d ASR 无结果，退回比例时间轴" % sid, flush=True)
            lines = [{"text": ln["text"], "tts": ln["tts"],
                      "start": ln["start"], "end": ln["end"]} for ln in m["lines"]]
            chars = []
            for ln in m["lines"]:
                n = max(1, len(ln["text"]))
                for k, ch in enumerate(ln["text"]):
                    t0 = ln["start"] + (ln["end"] - ln["start"]) * k / n
                    chars.append({"c": ch, "t": round(t0, 3), "e": round(t0, 3)})
            out[sid_s] = {"dur": m["dur"], "lines": lines, "chars": chars}
            json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            continue

        tt = align_to_tts(tts_all, ct)

        lines, pos = [], 0
        for ln in m["lines"]:
            n = len(ln["tts"])
            span = [tt.get(i) for i in range(pos, pos + n) if tt.get(i)]
            st = span[0][0] if span else 0.0
            en = span[-1][1] if span else st
            lines.append({"text": ln["text"], "tts": ln["tts"],
                          "start": round(st, 3), "end": round(en, 3)})
            pos += n

        orig = segs[sid]["text"]
        chars = map_orig(orig, tts_all, tt)
        out[sid_s] = {"dur": m["dur"], "lines": lines,
                      "chars": [{"c": c, "t": round(x, 3), "e": round(y, 3)}
                                for c, x, y in chars]}
        json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

        cov = sum(1 for ch in chars if ch[2] > ch[1]) / max(1, len(chars))
        print("[ok] seg %02d  %d 词  覆盖 %.0f%%  %.2f~%.2f"
              % (sid, len(words), cov * 100, lines[0]["start"], lines[-1]["end"]), flush=True)

    print("DONE ->", out_path)


if __name__ == "__main__":
    main()
