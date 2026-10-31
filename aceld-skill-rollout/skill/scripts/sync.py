#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sync.py —— 仓库 skill/ → 本地已装副本，**默认只报告不覆盖**

为什么默认不覆盖：
    本地副本常常比仓库「更新」（仓库是发布版，本地是工作版，比如 aceld-course
    本地 1600+ 行、仓库 250 行）。repo→local 无脑覆盖会把工作版冲掉。

用法：
    python sync.py                       # 只报告差异（安全）
    python sync.py --apply               # 只装「本地还没有」的技能
    python sync.py --force aceld-diagram --apply   # 强制覆盖某个（自动备份）
"""
import argparse
import filecmp
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit import LOCAL_DEFAULT, find_repo, is_backup, scan_repo


def tree_files(root):
    out = []
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith((".pyc",)) or "__pycache__" in dp:
                continue
            out.append(os.path.relpath(os.path.join(dp, f), root))
    return sorted(out)


def same_tree(a, b):
    fa, fb = tree_files(a), tree_files(b)
    if fa != fb:
        return False
    for rel in fa:
        if not filecmp.cmp(os.path.join(a, rel), os.path.join(b, rel), shallow=False):
            return False
    return True


def main():
    ap = argparse.ArgumentParser(description="仓库 → 本地技能同步（默认只报告）")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--local", default=LOCAL_DEFAULT)
    ap.add_argument("--apply", action="store_true", help="执行安装/覆盖")
    ap.add_argument("--force", default="", help="强制覆盖这些技能（逗号分隔，会备份）")
    a = ap.parse_args()

    repo = find_repo(a.repo)
    if not repo:
        print("!! 找不到 aceld-skill 仓库，用 --repo 指定，或设 ACELD_SKILL_REPO")
        return 2
    force = {x.strip() for x in a.force.split(",") if x.strip()}
    items = scan_repo(repo)

    print("仓库：%s\n本地：%s\n模式：%s\n"
          % (repo, a.local, "执行" if a.apply else "只报告（加 --apply 执行）"))

    todo, skipped, blocked = [], [], []
    for it in items:
        name = it["name"]
        src = os.path.join(repo, name, "skill")
        dest = os.path.join(a.local, name)
        if not os.path.isdir(src):
            continue
        if not os.path.isdir(dest):
            print("  + %-24s 本地没有 → 待安装（%d 个文件）" % (name, len(tree_files(src))))
            todo.append((name, src, dest, "install"))
            continue
        if same_tree(src, dest):
            print("  = %-24s 一致，跳过" % name)
            skipped.append(name)
            continue
        ls, ld = len(tree_files(src)), len(tree_files(dest))
        if name in force:
            print("  ! %-24s 不一致（仓库 %d / 本地 %d 文件）→ 强制覆盖（会备份）"
                  % (name, ls, ld))
            todo.append((name, src, dest, "force"))
        else:
            print("  ~ %-24s 不一致（仓库 %d / 本地 %d 文件）→ 不动，需 --force %s"
                  % (name, ls, ld, name))
            blocked.append(name)

    if not a.apply:
        print("\n待安装 %d / 强制覆盖 %d / 一致 %d / 需人工确认 %d"
              % (len([t for t in todo if t[3] == "install"]),
                 len([t for t in todo if t[3] == "force"]),
                 len(skipped), len(blocked)))
        if todo:
            print("加 --apply 执行上面的待安装项。")
        return 0

    for name, src, dest, how in todo:
        if os.path.isdir(dest):
            bak = dest + ".bak." + time.strftime("%Y%m%d%H%M%S")
            shutil.move(dest, bak)
            print("  ✓ %-24s 已备份到 %s" % (name, os.path.basename(bak)))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copytree(src, dest)
        print("  ✓ %-24s %s 完成" % (name, "安装" if how == "install" else "覆盖"))

    if todo:
        print("\n别忘了重启会话让 Agent 重新加载技能列表。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
