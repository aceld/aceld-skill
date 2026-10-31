#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""absorb.py —— 把候选技能拉进 inbox 并生成阅读报告（不安装、不执行）

用法：
    python absorb.py anthropics/skills/pdf
    python absorb.py owner/repo/skill --out ~/.aceld-skill-inbox

做的事：
    1. 先跑 vet 的结论（REJECT 直接拒绝拉取，除非 --force）
    2. 下载该技能目录下的文本文件到 inbox/<owner>__<repo>__<skill>/
    3. 生成 INBOX_REPORT.md：frontmatter、正文大纲、脚本清单、外部调用点、
       可吸收点（留空由人或 Agent 填）、来源与 commit hash
    4. 打印「吸收五问」

绝不：写 ~/.workbuddy-ai/skills/、执行下载来的任何脚本、pip/npm install。
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "aceld-findskill/1.0 (+https://github.com/aceld/aceld-skill)"}
TEXT_EXT = {".md", ".py", ".sh", ".ps1", ".js", ".ts", ".json", ".yaml", ".yml",
            ".toml", ".txt", ".go", ".rb", ".bat"}
MAX_BYTES = 300_000
DEFAULT_OUT = os.path.expanduser("~/.aceld-skill-inbox")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def get(url, raw=False, tries=2, timeout=25):
    for k in range(tries):
        req = urllib.request.Request(url, headers=UA)
        tok = os.environ.get("GITHUB_TOKEN")
        if tok and "api.github.com" in url:
            req.add_header("Authorization", "Bearer " + tok)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as f:
                b = f.read()
            return b.decode("utf-8", "replace") if raw else json.loads(b.decode("utf-8", "replace"))
        except Exception:
            if k + 1 < tries:
                time.sleep(1.5)
    return None


def outline(md):
    """抽取一级/二级标题做结构速览。"""
    out = []
    for line in md.splitlines():
        m = re.match(r"^(#{1,3})\s+(.+)$", line)
        if m:
            out.append("  " * (len(m.group(1)) - 1) + "- " + m.group(2).strip())
    return out[:60]


def ext_calls(text):
    """脚本里的外部调用点：网络 / 进程 / 文件写入。"""
    pats = [
        (r"(https?://[^\s'\"\)]+)", "URL"),
        (r"subprocess\.\w+\(([^)]{0,80})", "进程"),
        (r"os\.system\(([^)]{0,80})", "shell"),
        (r"(open\([^)]{0,60},\s*['\"](w|a|wb)['\"])", "写文件"),
        (r"(pip install[^\n]{0,80}|npm i(nstall)?[^\n]{0,80})", "装包"),
    ]
    hits = []
    for pat, kind in pats:
        for m in re.finditer(pat, text):
            s = m.group(1).strip()
            if s not in [h[1] for h in hits]:
                hits.append((kind, s[:110]))
    return hits[:40]


def main():
    ap = argparse.ArgumentParser(description="拉取技能到 inbox 并生成阅读报告")
    ap.add_argument("id", help="owner/repo/skill")
    ap.add_argument("--skill", default=None)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--force", action="store_true", help="vet 结论为 REJECT 也拉取")
    a = ap.parse_args()

    parts = a.id.strip().strip("/").split("/")
    if len(parts) < 2:
        print("!! id 格式应为 owner/repo 或 owner/repo/skill", file=sys.stderr)
        return 2
    owner, repo = parts[0], parts[1]
    skill = a.skill or (parts[2] if len(parts) > 2 else repo)

    # ── 先体检 ────────────────────────────────────────────────────
    import vet as V
    rm = get("https://api.github.com/repos/%s/%s" % (owner, repo))
    if not rm:
        print("!! 仓库不存在或限流", file=sys.stderr); return 2
    branch = rm.get("default_branch") or "main"
    path, content = V.locate(owner, repo, branch, skill)
    if not content:
        print("!! 找不到 SKILL.md", file=sys.stderr); return 2
    meta, body, _ = V.parse_frontmatter(content)
    sdir = os.path.dirname(path)
    hits = []
    for p in (V.list_skill_files(owner, repo, branch, sdir) or [path]):
        t = get("https://raw.githubusercontent.com/%s/%s/%s/%s" % (owner, repo, branch, p), raw=True)
        if t:
            for h in V.scan_text(t):
                h["file"] = p; hits.append(h)
    high = [h for h in hits if h["level"] == "HIGH"]
    if high and not a.force:
        print("!! 安全扫描命中 HIGH，拒绝拉取（确要拉取加 --force，并先逐条读）:")
        for h in high[:6]:
            print("   [%s] %s  %s" % (h["level"], h["file"], h["why"]))
        return 1

    # ── 下载 ──────────────────────────────────────────────────────
    tag = "%s__%s__%s" % (owner, repo, skill)
    dest = os.path.join(os.path.expanduser(a.out), tag)
    os.makedirs(dest, exist_ok=True)
    files = V.list_skill_files(owner, repo, branch, sdir) or [path]
    got, digest = [], []
    for p in files:
        t = get("https://raw.githubusercontent.com/%s/%s/%s/%s" % (owner, repo, branch, p), raw=True)
        if t is None:
            continue
        rel = p[len(sdir):].lstrip("/") if sdir and p.startswith(sdir) else os.path.basename(p)
        lp = os.path.join(dest, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(lp), exist_ok=True)
        with open(lp, "w", encoding="utf-8", newline="\n") as f:
            f.write(t)
        got.append((rel, len(t)))
        digest.append((rel, hashlib.sha256(t.encode("utf-8")).hexdigest()[:12]))

    head = get("https://api.github.com/repos/%s/%s/commits/%s" % (owner, repo, branch))
    commit = (head or {}).get("sha", "")[:12] or "-"

    # ── 报告 ──────────────────────────────────────────────────────
    L = []
    L.append("# INBOX · %s/%s/%s\n" % (owner, repo, skill))
    L.append("> 来源：https://github.com/%s/%s/tree/%s/%s  \n> commit `%s` · 拉取时间 %s  \n"
             "> **本目录仅作阅读，未安装、未执行任何脚本。**\n"
             % (owner, repo, branch, sdir or ".", commit,
                time.strftime("%Y-%m-%d %H:%M")))
    L.append("## 1. frontmatter\n")
    for k in ("name", "description", "license", "compatibility", "allowed-tools"):
        if meta.get(k):
            L.append("- **%s**: %s" % (k, meta[k]))
    L.append("\n## 2. 正文大纲（%d 行 / 约 %d tokens）\n"
             % (body.count("\n") + 1, int(len(body) / 2.2)))
    L += outline(body) or ["（无标题）"]
    L.append("\n## 3. 文件清单\n")
    for rel, n in got:
        L.append("- `%s`（%d 字）" % (rel, n))
    L.append("\n## 4. 外部调用点（吸收时要重点看这些）\n")
    calls = []
    for rel, _ in got:
        lp = os.path.join(dest, rel.replace("/", os.sep))
        try:
            t = open(lp, encoding="utf-8").read()
        except OSError:
            continue
        for kind, s in ext_calls(t):
            calls.append("- `%s` [%s] `%s`" % (rel, kind, s))
    L += calls or ["（无）"]
    L.append("\n## 5. 安全扫描\n")
    if not hits:
        L.append("✓ 规则未命中（**不等于安全**，带脚本的必须人工读）")
    for h in hits:
        L.append("- `[%s]` %s · %s" % (h["level"], h["file"], h["why"]))
    L.append("\n## 6. 吸收五问（必须逐条写答案，写不出就别吸收）\n")
    L.append("1. **它解决的缺口**，用一句话说清（输入 → 输出）是什么？")
    L.append("2. **它的核心方法**是什么？（不是它调了什么库，是它的判断顺序与检查项）")
    L.append("3. **哪些能进我的流程**？对应到我哪个技能的哪一节 / 哪个 reference？")
    L.append("4. **哪些必须改写**？（路径、模型、账号、平台约定、语言）")
    L.append("5. **我比它强在哪 / 它比我强在哪**？吸收后我的流程具体变短还是变强了？")
    L.append("\n## 7. 吸收结论（人填）\n")
    L.append("- 结论：`吸收` / `部分吸收` / `不吸收`")
    L.append("- 写入了：`（技能名 / reference 文件名）`")
    L.append("- 改写点：")
    L.append("- 来源登记：`%s/%s/%s@%s`" % (owner, repo, skill, commit))
    L.append("\n## 8. 指纹（防更新漂移，下次比对用）\n")
    L.append("```")
    for rel, h in digest:
        L.append("%s  %s" % (h, rel))
    L.append("```")

    rp = os.path.join(dest, "INBOX_REPORT.md")
    with open(rp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))

    print("已拉取 %d 个文件 → %s" % (len(got), dest))
    print("阅读报告 → %s" % rp)
    print("\n提醒：inbox 里的东西不执行、不安装。读懂后按「吸收五问」写结论，")
    print("      再把方法重写进自己的技能。原始来源记得登记：%s/%s/%s@%s"
          % (owner, repo, skill, commit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
