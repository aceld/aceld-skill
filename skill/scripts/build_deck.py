# -*- coding: utf-8 -*-
"""组装 deck.html + deck_meta.json，并在组装时做三项校验。

用法（在课程工程根目录执行）：
  python scripts/build_deck.py                       # 自动找 deck_*.py
  python scripts/build_deck.py --modules deck_a,deck_b
  python scripts/build_deck.py --segments work/segments.json --out work/slides

页面定义格式（每个 deck_*.py 里）：
  S.append((sid, "章节名", 总页数, "<div class='inner'>…</div>", [
      ("触发词", "#选择器", "动效", 0.6),
  ]))
"""
import os
import re
import sys
import json
import glob
import importlib.util
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from gen_common import CSS, JS, crumb           # noqa: E402
from config import cfg                          # noqa: E402


# ---------------- 校验 ----------------

def _ids_in(body: str):
    return set(re.findall(r'id="([^"]+)"', body))


def check_steps(slides, segs):
    """返回问题列表（空 = 通过）。

    三条硬约束：
      1. 选择器必须存在于该页
      2. 触发词必须是该段正文的原样子串
      3. 触发词在正文里的位置必须严格递增
    """
    problems = []
    for sid, chapter, _page, body, steps in slides:
        text = ""
        if sid < len(segs):
            text = segs[sid].get("text", "")
        last = -1
        for st in steps:
            cue, sel = str(st[0]), str(st[1])
            if sel.startswith("#") and sel[1:] not in _ids_in(body):
                problems.append("P%02d 选择器不存在：%s" % (sid, sel))
            if cue.startswith("@"):
                continue
            pos = text.find(cue)
            if pos < 0:
                problems.append("P%02d 触发词未命中：%r" % (sid, cue))
            elif pos <= last:
                problems.append("P%02d 触发词位置倒退：%r（%d <= %d）" % (sid, cue, pos, last))
            else:
                last = pos
    return problems


def check_orphan_ids(slides, allow=("marker", "grad", "clip", "mask")):
    """有 id 但没有任何 step 用到 → 这块内容永远不会亮（或一开场就亮）。"""
    problems = []
    for sid, _chapter, _page, body, steps in slides:
        used = {str(st[1])[1:] for st in steps if str(st[1]).startswith("#")}
        ids = _ids_in(body)
        # 代码行锚点由级联跟进，允许不在 steps 里
        orphan = {i for i in ids - used
                  if not i.startswith("codel")
                  and not any(i.startswith(a) for a in allow)}
        if orphan:
            problems.append("P%02d 这些 id 没有对应动画：%s" % (sid, ", ".join(sorted(orphan))))
    return problems


def check_sid(slides, segs):
    problems = []
    for i, (sid, *_rest) in enumerate(slides):
        if sid != i:
            problems.append("第 %d 个页面的 sid=%s，与顺序不一致（必须从 0 连续）" % (i, sid))
        if sid >= len(segs):
            problems.append("sid=%s 超出讲稿段数（%d）" % (sid, len(segs)))
    return problems


# ---------------- 组装 ----------------

def load_slides(module_names, search_dirs):
    slides = []
    for name in module_names:
        found = None
        for d in search_dirs:
            p = os.path.join(d, name + ".py")
            if os.path.exists(p):
                found = p
                break
        if not found:
            print("[skip] %s 未找到" % name)
            continue
        spec = importlib.util.spec_from_file_location(name, found)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        slides.extend(getattr(mod, "S", []))
    slides.sort(key=lambda x: x[0])
    return slides


def main():
    ap = argparse.ArgumentParser(description="组装幻灯片 deck.html")
    ap.add_argument("--modules", default="", help="逗号分隔的 deck 模块名，默认自动发现 deck_*.py")
    ap.add_argument("--segments", default="", help="讲稿 JSON，默认找 root/segments.json")
    ap.add_argument("--out", default="", help="输出目录，默认 root/slides")
    ap.add_argument("--strict", action="store_true", help="有校验问题时直接退出")
    a = ap.parse_args()

    c = cfg()
    root = c.root
    seg_path = a.segments or os.path.join(root, "segments.json")
    out_dir = a.out or os.path.join(root, "slides")
    os.makedirs(out_dir, exist_ok=True)

    if os.path.exists(seg_path):
        segs = json.load(open(seg_path, encoding="utf-8"))["segments"]
    else:
        print("!! 找不到讲稿：%s（校验会跳过触发词检查）" % seg_path)
        segs = []

    # 找 deck 模块
    if a.modules:
        names = [x.strip() for x in a.modules.split(",") if x.strip()]
    else:
        dirs = [os.getcwd(), out_dir, os.path.dirname(seg_path)]
        names = []
        for d in dirs:
            names.extend(sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(d, "deck_*.py"))))
        names = list(dict.fromkeys(names))
    if not names:
        raise SystemExit("!! 没有找到 deck_*.py，请用 --modules 指定")

    search_dirs = [os.getcwd(), out_dir, os.path.dirname(seg_path)]
    slides = load_slides(names, search_dirs)
    if not slides:
        raise SystemExit("!! 没有加载到任何页面")

    # 校验
    problems = check_sid(slides, segs) + check_steps(slides, segs) + check_orphan_ids(slides)
    if problems:
        print("\n===== 校验问题 %d 条 =====" % len(problems))
        for p in problems:
            print("  -", p)
        if a.strict:
            raise SystemExit(1)
    else:
        print("校验通过：%d 页，触发词全部命中，id 无遗漏" % len(slides))

    # 组装
    title = "%s · %s" % (c.text("course_title", "Course"), c.text("author", ""))
    parts = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
             "<title>%s</title>" % title, CSS, "</head><body>"]

    meta = []
    for idx, (sid, chapter, page, body, steps) in enumerate(slides):
        parts.append('<section class="slide" id="slide%d" data-sid="%s">%s%s</section>'
                     % (idx, sid, crumb(chapter, page), body))
        meta.append({"i": idx, "sid": sid, "chapter": chapter, "steps": steps,
                     "text": segs[sid].get("text", "") if sid < len(segs) else ""})

    parts.append(JS)
    parts.append("<script>window.DECK_META=%s;</script>" % json.dumps(meta, ensure_ascii=False))
    parts.append("</body></html>")

    html_path = os.path.join(out_dir, "deck.html")
    open(html_path, "w", encoding="utf-8").write("\n".join(parts))
    json.dump(meta, open(os.path.join(out_dir, "deck_meta.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print("deck.html 已生成：%s（%d 页）" % (html_path, len(slides)))
    for m in meta:
        print("  [%02d] sid=%02d  %s  (%d 步)"
              % (m["i"], m["sid"], m["chapter"], len(m["steps"])))


if __name__ == "__main__":
    main()
