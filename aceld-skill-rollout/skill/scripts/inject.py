#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inject.py —— 把一个能力块幂等地铺到所有自有技能

用法：
    # 只看不改（默认 dry-run）
    python inject.py --block block.md --marker "开工前置检查"
    # 真的写
    python inject.py --block block.md --marker "开工前置检查" --apply
    # 换锚点
    python inject.py --block b.md --marker X --anchor after-heading "## 0. 一分钟速览"
    # 摘掉
    python inject.py --marker "开工前置检查" --remove --apply

幂等规则：
    有哨兵 → 替换哨兵之间的内容（不会越注越多）
    有裸标题无哨兵（手写老块）→ 把那段 blockquote 整段替换成新块（并补上哨兵）
    都没有 → 按锚点插入
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit import (LOCAL_DEFAULT, classify, code_mask, find_repo, inspect,
                   is_backup, scan_local, scan_repo)

BEGIN = "<!-- aceld-rollout:begin %s %s -->"
END = "<!-- aceld-rollout:end -->"


def legacy_region(lines, marker):
    """找到手写老块的起止行号（含），没有返回 None。"""
    mask = code_mask(lines)
    for i, ln in enumerate(lines):
        if mask[i]:
            continue
        if marker in ln and "aceld-rollout" not in ln:
            if ln.lstrip().startswith(">"):
                j = i
                while j + 1 < len(lines) and (lines[j + 1].lstrip().startswith(">")
                                              or lines[j + 1].strip() == ""):
                    if lines[j + 1].strip() == "" and j + 2 < len(lines) \
                            and not lines[j + 2].lstrip().startswith(">"):
                        break
                    j += 1
                return i, j
            j = i
            while j + 1 < len(lines):
                nxt = lines[j + 1]
                if nxt.strip() == "---" or nxt.startswith("## "):
                    break
                j += 1
            return i, j
    return None


def sentinel_region(lines, marker):
    b = re.compile(r"<!--\s*aceld-rollout:begin\s+.*?" + re.escape(marker))
    mask = code_mask(lines)
    for i, ln in enumerate(lines):
        if mask[i]:
            continue
        if b.search(ln):
            for j in range(i, len(lines)):
                if "aceld-rollout:end" in lines[j]:
                    return i, j
            return i, len(lines) - 1
    return None


def anchor_index(lines, anchor, heading):
    if anchor == "append":
        return len(lines), "末尾（⚠ 大概率不会被读到）"
    if anchor == "after-heading":
        for i, ln in enumerate(lines):
            if ln.strip() == heading.strip() or ln.startswith(heading):
                return i, "「%s」之前" % heading.strip()
        return None, "找不到标题 %r" % heading
    # after-intro：H1 之后的第一条 --- 之前
    seen_h1 = False
    for i, ln in enumerate(lines):
        if ln.startswith("# "):
            seen_h1 = True
            continue
        if seen_h1 and ln.strip() == "---":
            return i, "一句话定位之后"
    for i, ln in enumerate(lines):
        if seen_h1 and ln.strip() == "":
            return i, "H1 之后（无分隔线，退到首个空行）"
    return None, "找不到锚点"


def main():
    ap = argparse.ArgumentParser(description="幂等注入能力块")
    ap.add_argument("--block", default=None, help="块内容文件（markdown）")
    ap.add_argument("--text", default=None, help="直接给块内容（与 --block 二选一）")
    ap.add_argument("--marker", required=True, help="能力名，用于哨兵标签与老块识别")
    ap.add_argument("--version", default="v1", help="块版本号，改内容必须升")
    ap.add_argument("--anchor", default="after-intro",
                    choices=["after-intro", "after-heading", "append"])
    ap.add_argument("--heading", default="", help="--anchor after-heading 时用")
    ap.add_argument("--only", default="", help="只处理这些技能（逗号分隔）")
    ap.add_argument("--remove", action="store_true", help="摘掉能力块")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--local", default=LOCAL_DEFAULT)
    ap.add_argument("--apply", action="store_true", help="真的写盘（默认只看）")
    a = ap.parse_args()

    if not a.remove:
        if a.block:
            body = open(a.block, encoding="utf-8").read().rstrip("\n")
        elif a.text:
            body = a.text.rstrip("\n")
        else:
            print("!! 需要 --block 或 --text（或用 --remove）", file=sys.stderr)
            return 2
        if "aceld-rollout:begin" in body:
            print("!! block 里不要自己写哨兵，inject.py 会加", file=sys.stderr)
            return 2
        new_block = [BEGIN % (a.marker, a.version)] + body.splitlines() + [END]

    repo = find_repo(a.repo)
    items = scan_repo(repo) + scan_local(a.local)
    repo_names = {i["name"] for i in scan_repo(repo)}
    only = {x.strip() for x in a.only.split(",") if x.strip()}

    print("模式：%s%s" % ("移除" if a.remove else "注入",
                         "" if a.apply else "（dry-run，加 --apply 才写盘）"))
    print("能力：%s  锚点：%s\n" % (a.marker, a.anchor if not a.remove else "-"))

    stat = {"insert": 0, "replace": 0, "legacy": 0, "remove": 0,
            "skip3": 0, "same": 0, "fail": 0}
    for it in items:
        name, path = it["name"], it["path"]
        if only and name not in only:
            continue
        kind = classify(it, repo_names)
        if kind.startswith("三方"):
            print("  - %-32s 三方技能，跳过" % name)
            stat["skip3"] += 1
            continue

        lines = open(path, encoding="utf-8").read().splitlines()
        s = sentinel_region(lines, a.marker)
        legacy = legacy_region(lines, a.marker) if not s else None
        if legacy and legacy[0] >= 40:
            # 40 行以外的同名标题是「文档里的示例」，不是真的能力块
            print("  ! %-32s 第 %d 行的同名标题视为文档示例，不替换" % (name, legacy[0] + 1))
            legacy = None

        if a.remove:
            reg = s or legacy
            if not reg:
                print("  = %-32s 没有块，无需移除" % name)
                stat["same"] += 1
                continue
            i, j = reg
            out = lines[:i] + lines[j + 1:]
            while out and out[min(i, len(out) - 1)].strip() == "":
                del out[min(i, len(out) - 1)]
            action = "已移除"
            stat["remove"] += 1
        elif s:
            i, j = s
            if lines[i:j + 1] == new_block:
                print("  = %-32s 内容一致，跳过" % name)
                stat["same"] += 1
                continue
            out = lines[:i] + new_block + lines[j + 1:]
            action = "替换（第 %d 行）" % (i + 1)
            stat["replace"] += 1
        elif legacy:
            i, j = legacy
            out = lines[:i] + new_block + lines[j + 1:]
            action = "老块升级为哨兵块（第 %d–%d 行）" % (i + 1, j + 1)
            stat["legacy"] += 1
        else:
            idx, why = anchor_index(lines, a.anchor, a.heading)
            if idx is None:
                print("  ✗ %-32s %s" % (name, why))
                stat["fail"] += 1
                continue
            out = lines[:idx] + new_block + [""] + lines[idx:]
            action = "插入（%s，第 %d 行）" % (why, idx + 1)
            stat["insert"] += 1

        if a.apply:
            # 原子写：先写 .tmp 再 os.replace。
            # 直接用 open(path,"w") 会在 join 抛异常时留下 0 字节文件（踩过，
            # 把 aceld-course 的 SKILL.md 清空过一次）。
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(out).rstrip("\n") + "\n")
            os.replace(tmp, path)
            print("  ✓ %-32s %s" % (name, action))
        else:
            print("  · %-32s %s" % (name, action))

    print("\n汇总：新增 %d / 替换 %d / 老块升级 %d / 移除 %d / 一致 %d / 三方跳过 %d / 失败 %d"
          % (stat["insert"], stat["replace"], stat["legacy"], stat["remove"],
             stat["same"], stat["skip3"], stat["fail"]))
    if not a.apply and any(stat[k] for k in ("insert", "replace", "legacy", "remove")):
        print("确认无误后加 --apply 写盘，再跑 audit.py --verify 复核。")
    return 0 if stat["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
