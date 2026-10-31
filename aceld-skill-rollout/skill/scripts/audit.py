#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit.py —— 能力铺开审计：哪些技能有？在什么位置？是不是真的会生效？

用法：
    python audit.py                                  # 审计默认 marker「开工前置检查」
    python audit.py --marker "某个能力名"
    python audit.py --verify                         # 加严：位置 + 脚本存在 + 仓库/本地一致
    python audit.py --repo D:/path/to/aceld-skill --local ~/.workbuddy-ai/skills

判定「生效」的规则（血泪教训）：
    能力块必须在 SKILL.md 前 30 行内，或在流程第一屏。
    写在末尾的一律按「没有」处理 —— Agent 从上往下读，读到「阶段一」就开始干活了。
"""
import argparse
import os
import re
import sys

DEFAULT_MARKER = "开工前置检查"
LOCAL_DEFAULT = os.path.expanduser("~/.workbuddy-ai/skills")
TOP_LINES = 30


def find_repo(arg=None):
    if arg:
        return os.path.abspath(arg)
    env = os.environ.get("ACELD_SKILL_REPO")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    d = os.getcwd()
    for _ in range(8):
        if os.path.isfile(os.path.join(d, "aceld-course", "skill", "SKILL.md")):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return None


def is_backup(name):
    return ".bak" in name or name.endswith(".zip")


def read_skill_name(path):
    """读 SKILL.md frontmatter 的 name:，读不到就退回目录名。

    ★仓库目录名 ≠ 技能名：`aceld-course/` 装出来是 `course-studio`
    （仓库里是目录归类，本地是技能标识，由 frontmatter 的 name 决定）。
    按目录名去同步，会拿「通用开源版」覆盖本地的「个人实战工作版」——
    两者是 254 行 vs 1634 行，结构都不一样，覆盖就是丢工作。
    """
    lines = read_lines(path)
    if not lines or lines[0].strip() != "---":
        return os.path.basename(os.path.dirname(os.path.dirname(path)))
    for ln in lines[1:40]:
        if ln.strip() == "---":
            break
        m = re.match(r"^name:\s*(.+?)\s*$", ln)
        if m:
            return m.group(1).strip().strip("\"'")
    return os.path.basename(os.path.dirname(os.path.dirname(path)))


def scan_repo(repo):
    """仓库里每个技能：<dir>/skill/SKILL.md"""
    out = []
    if not repo or not os.path.isdir(repo):
        return out
    for d in sorted(os.listdir(repo)):
        p = os.path.join(repo, d, "skill", "SKILL.md")
        if is_backup(d) or not os.path.isfile(p):
            continue
        out.append({"name": d, "skill": read_skill_name(p), "path": p, "where": "repo"})
    return out


def scan_local(local):
    out = []
    if not os.path.isdir(local):
        return out
    for d in sorted(os.listdir(local)):
        p = os.path.join(local, d, "SKILL.md")
        if is_backup(d) or not os.path.isfile(p):
            continue
        out.append({"name": d, "skill": d, "path": p, "where": "local"})
    return out


def classify(item, repo_skills):
    if item["skill"] in repo_skills:
        return "自有(仓库)"
    if item["skill"].startswith("aceld-"):
        return "自有(本地独有)"
    meta = os.path.join(os.path.dirname(item["path"]), "_meta.json")
    if os.path.isfile(meta):
        try:
            if "ownerId" in open(meta, encoding="utf-8", errors="ignore").read():
                return "三方(市场)"
        except OSError:
            pass
    return "三方"


def read_lines(path):
    try:
        return open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return []


def code_mask(lines):
    """标记「不算正文」的行：frontmatter 与围栏代码块。

    两个真实误判都出在这里：
      · description 里写了「开工前置检查」→ 被当成第 3 行就有块，假生效
      · 文档里演示哨兵语法 `<!-- aceld-rollout:begin ... -->` → 被当成真哨兵
    """
    mask = [False] * len(lines)
    i = 0
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                for k in range(0, j + 1):
                    mask[k] = True
                i = j + 1
                break
    fence = False
    for j in range(i, len(lines)):
        s = lines[j].lstrip()
        bare = s.rstrip() in ("```", "~~~")
        if not fence and (s.startswith("```") or s.startswith("~~~")):
            fence = True
            mask[j] = True
            continue
        if fence:
            mask[j] = True
            # 只有「不带信息的裸围栏」才算闭合，否则 ```markdown 里套 ```bash
            # 会在内层就提前闭合，把示例文字当成正文（踩过）
            if bare:
                fence = False
    return mask


def inspect(item, marker):
    """返回 {has, line, total, block, version, scripts, ok_pos}"""
    lines = read_lines(item["path"])
    total = len(lines)
    mask = code_mask(lines)
    begin = re.compile(r"<!--\s*aceld-rollout:begin\s+(.+?)\s*-->")
    has, line_no, block, ver = False, None, [], None
    for i, ln in enumerate(lines):
        if mask[i]:
            continue
        m = begin.search(ln)
        if m and marker in m.group(1):
            has, line_no = True, i + 1
            ver = m.group(1).replace(marker, "").strip() or "v?"
            for j in range(i, min(total, i + 80)):
                block.append(lines[j])
                if "aceld-rollout:end" in lines[j]:
                    break
            break
    if not has:
        # 没有哨兵时，退一步找裸标题（说明是手写的老块）
        for i, ln in enumerate(lines):
            if mask[i]:
                continue
            if marker in ln:
                has, line_no = True, i + 1
                ver = "无哨兵"
                for j in range(i, min(total, i + 30)):
                    block.append(lines[j])
                    if lines[j].strip() in ("---", "") and j > i + 2:
                        break
                break
    # 注意 `~` 必须在字符集里：块里写的是 `~/.workbuddy-ai/skills/.../x.py`，
    # 漏了 `~` 会被截成 `/.workbuddy-ai/...`，见 resolve_script() 的注释
    scripts = sorted(set(re.findall(r"([\w~./\\-]*scripts/[\w.-]+\.py)", " ".join(block))))
    ok_pos = bool(has and line_no <= TOP_LINES)
    return {"has": has, "line": line_no, "total": total, "block": block,
            "version": ver, "scripts": scripts, "ok_pos": ok_pos}


_WIN_ABS = re.compile(r"^[A-Za-z]:[\\/]")


def resolve_script(ref, item):
    """块里引用的脚本，按几种可能位置解析。

    两个坑（`--verify` 报 7 条假错就是这两个叠加）：
      · 块里写的是 `python ~/.workbuddy-ai/skills/.../preflight.py`，
        正则不含 `~` 就会被截成 `/.workbuddy-ai/...`；
      · Windows 上 `os.path.isabs("/.workbuddy-ai/x.py")` 返回 True
        （只要以分隔符开头就算绝对路径），于是被当成真绝对路径直接判「不存在」。
    所以：`~` 先 expanduser；绝对路径只认「盘符」或 POSIX 下的 `/`。
    """
    ref = ref.replace("\\", "/").strip()
    cands = []
    if ref.startswith("~"):
        cands.append(os.path.expanduser(ref))
    elif _WIN_ABS.match(ref) or (os.name != "nt" and ref.startswith("/")):
        cands.append(ref)
    home = os.path.expanduser("~")
    cands += [
        os.path.join(home, ".workbuddy-ai", "skills", ref.replace("scripts/", "aceld-findskill/scripts/", 1))
        if ref.startswith("scripts/") else "",
        os.path.join(home, ".workbuddy-ai", "skills", ref),
        os.path.join(os.path.dirname(os.path.dirname(item["path"])), ref),
        os.path.join(os.getcwd(), ref),
    ]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def main():
    ap = argparse.ArgumentParser(description="能力铺开审计")
    ap.add_argument("--marker", default=DEFAULT_MARKER)
    ap.add_argument("--repo", default=None)
    ap.add_argument("--local", default=LOCAL_DEFAULT)
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()

    repo = find_repo(a.repo)
    repo_items = scan_repo(repo)
    local_items = scan_local(a.local)
    items = repo_items + local_items
    if not items:
        print("!! 没扫到任何技能。检查 --repo / --local，或设 ACELD_SKILL_REPO")
        return 2
    repo_skills = {i["skill"] for i in repo_items}

    print("仓库：%s" % (repo or "（未找到，只审计本地）"))
    print("本地：%s" % a.local)
    print("能力：%s\n" % a.marker)

    rows, problems = [], []
    for it in items:
        kind = classify(it, repo_skills)
        r = inspect(it, a.marker)
        rows.append((it, kind, r))
        if kind.startswith("三方"):
            continue
        if not r["has"]:
            problems.append("%s 没有「%s」块" % (it["name"], a.marker))
        elif not r["ok_pos"]:
            problems.append("%s 的块在第 %d 行（共 %d 行），大概率不会被读到"
                            % (it["name"], r["line"], r["total"]))
        elif a.verify:
            if r["version"] == "无哨兵":
                problems.append("%s 的块没有哨兵注释，改起来容易重复插入" % it["name"])
            for ref in r["scripts"]:
                if not resolve_script(ref, it):
                    problems.append("%s 引用的脚本不存在：%s" % (it["name"], ref))

    if a.verify:
        both = repo_skills & {i["skill"] for i in local_items}
        for n in sorted(both):
            got = {it["where"]: r["has"] for it, k, r in rows if it["skill"] == n}
            if len(set(got.values())) > 1:
                problems.append("%s 仓库与本地不一致（%s）" % (n, got))
        # 备份目录留在技能目录里 → 加载器会把它们也当技能扫，
        # 同一个技能在列表里出现好几次，用户根本找不到哪个是真的（踩过）
        if os.path.isdir(a.local):
            for d in sorted(os.listdir(a.local)):
                if is_backup(d) and os.path.isdir(os.path.join(a.local, d)):
                    problems.append("备份目录留在技能目录里：%s（会被当成同名技能，"
                                    "列表出现重复；应移到 skills-backup/）" % d)

    # 表格
    print("%-34s %-14s %-6s %-12s %s" % ("技能", "归属", "有块", "位置", "版本/生效"))
    print("-" * 88)
    for it, kind, r in rows:
        if r["has"]:
            pos = "%d/%d" % (r["line"], r["total"])
            flag = "✓ 生效" if r["ok_pos"] else "✗ 太靠后"
        else:
            pos, flag = "-", ("跳过(三方)" if kind.startswith("三方") else "✗ 缺")
        label = it["name"] + (" [repo]" if it["where"] == "repo" else "")
        if it["skill"] != it["name"]:
            label += "→" + it["skill"]
        print("%-34s %-14s %-6s %-12s %s" % (
            label, kind, "✓" if r["has"] else "✗", pos,
            ("%s %s" % (r["version"], flag)) if r["has"] else flag))

    own = [(it, k, r) for it, k, r in rows if not k.startswith("三方")]
    ok = [x for x in own if x[2]["ok_pos"]]
    print("\n自有技能 %d 个（仓库 %d + 本地 %d），生效 %d 个"
          % (len(own), len(repo_items), len(local_items), len(ok)))
    third = [x for x in rows if x[1].startswith("三方")]
    if third:
        print("三方技能 %d 个已跳过（改了会被市场更新覆盖）：%s"
              % (len(third), "、".join(x[0]["name"] for x in third)))

    if problems:
        print("\n问题 %d 条：" % len(problems))
        for p in problems:
            print("  ✗ %s" % p)
        print("\n修：python inject.py --block <block.md> --marker \"%s\" --apply" % a.marker)
        return 1
    print("\n结论：全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
