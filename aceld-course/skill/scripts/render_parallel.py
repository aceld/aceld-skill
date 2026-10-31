# -*- coding: utf-8 -*-
"""render_parallel.py —— 分片并行渲染 + 用 ffprobe 重建 timeline

为什么需要它：
  单进程顺序渲染，一页约 100 秒（screenshot 是瓶颈），27 页要 45 分钟。
  一节课出横版 + 竖版两套就是 1.5 小时纯等待。
  拆 4 个进程并行，同机 12.5 分钟跑完，快 3.6 倍。

用法：
  python render_parallel.py                    # 横版，4 进程
  python render_parallel.py --vertical         # 竖版
  python render_parallel.py --jobs 3           # 改并行数（4 核机器建议 3）

约定目录（与 build_deck.py / render_slides.py 一致）：
  横版  <root>/work/slides/{deck_meta.json, clips/, timeline.json}
  竖版  <root>/work/slides_v/{deck_meta.json, clips/, timeline.json}

★ 两个必须做对的地方（否则结果会错，且不报错）
  1. 子进程用 ONLY 只渲自己那几页时，**不归自己渲的页绝不能写进 timeline**。
     否则会 probe 到上一版残留的旧 clip，合并后同一页出现两三次、dur 还是旧的
     （27 页能合出 106 条）。见 render_slides.py 里 `if want and i not in want: continue`。
  2. 合并时不要信子进程写的 dur，用 ffprobe 按 deck_meta 的页序重建。
     分片渲染有 1/30 帧漂移，声明值本来就不可靠。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402


def probe(ffprobe: str, p: str) -> float | None:
    r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", p], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vertical", action="store_true", help="渲染竖版目录 slides_v/")
    ap.add_argument("--jobs", type=int, default=4, help="并行进程数（默认 4）")
    ap.add_argument("--slides-dir", default="", help="覆盖幻灯片目录")
    ap.add_argument("--script", default="", help="覆盖渲染脚本名")
    ap.add_argument("--python", default=sys.executable, help="子进程解释器")
    args = ap.parse_args()

    c = config.cfg()
    root = c.root
    work = os.path.join(root, "work")
    sl = args.slides_dir or os.path.join(work, "slides_v" if args.vertical else "slides")
    script = args.script or os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "render_slides.py" if not args.vertical else "render_slides_v.py")
    ffprobe = c.path("paths.ffprobe", "ffprobe")

    meta_path = os.path.join(sl, "deck_meta.json")
    if not os.path.exists(meta_path):
        print(f"!! 找不到 {meta_path}（先跑 build_deck.py）")
        return 1
    meta = json.load(open(meta_path, encoding="utf-8"))
    pages = [m["i"] for m in meta]
    n = max(1, min(args.jobs, len(pages)))

    slices: list[list[int]] = [[] for _ in range(n)]
    for k, p in enumerate(pages):
        slices[k % n].append(p)          # 交错分片，页数均衡

    t0 = time.time()
    procs = []
    for k, sl_pages in enumerate(slices):
        if not sl_pages:
            continue
        env = os.environ.copy()
        env["ONLY"] = ",".join(map(str, sl_pages))
        env["TL"] = f"timeline_part{k}.json"     # ★ 各写各的，避免互相覆盖
        lg = os.path.join(work, f"render_part{k}.log")
        fh = open(lg, "w", encoding="utf-8")
        p = subprocess.Popen([args.python, "-u", script], cwd=work, env=env,
                             stdout=fh, stderr=subprocess.STDOUT)
        procs.append((k, sl_pages, p, fh, lg))
        print(f"[片{k}] {len(sl_pages)} 页 {sl_pages}", flush=True)

    fails = []
    for k, sl_pages, p, fh, lg in procs:
        rc = p.wait()
        fh.close()
        print(f"[片{k}] rc={rc}  {(time.time()-t0)/60:.1f} 分钟", flush=True)
        if rc != 0:
            fails.append((k, lg))

    # ---------- 用实测时长重建 timeline ----------
    clips_dir = os.path.join(sl, "clips")
    items, missing = [], []
    for m in meta:
        cp = os.path.join(clips_dir, f"slide_{m['i']:02d}.mp4")
        if not os.path.exists(cp):
            missing.append(m["i"]); continue
        d = probe(ffprobe, cp)
        if d is None:
            missing.append(m["i"]); continue
        items.append({"i": m["i"], "sid": m.get("sid"), "chapter": m.get("chapter", ""),
                      "dur": round(d, 3), "clip": cp, "frames": 0})

    out = os.path.join(sl, "timeline.json")
    json.dump(items, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    total = sum(x["dur"] for x in items)
    print(f"\n{len(items)} 页 / {total/60:.2f} 分钟 / 用时 {(time.time()-t0)/60:.1f} 分钟")
    print(f"-> {out}")

    if missing:
        print(f"!! 缺页 {sorted(missing)}")
    if fails:
        for k, lg in fails:
            print(f"!! 片{k} 失败，看 {lg}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
