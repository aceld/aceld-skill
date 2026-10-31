#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""find.py —— 多源检索 Agent Skill 候选

用法：
    python find.py "pdf form filling"
    python find.py "kubernetes manifest review" --source github --min-stars 500
    python find.py "小红书 图卡 排版" --limit 20 --min-installs 1000

输出：终端候选表 + .findskill/candidates.json

依赖：仅标准库。走 https_proxy / http_proxy 环境变量。
GitHub 匿名 API 限 60 次/小时，量大时 export GITHUB_TOKEN=xxx。
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "aceld-findskill/1.0 (+https://github.com/aceld/aceld-skill)",
      "Accept": "application/json"}
OUTDIR = os.path.join(os.path.expanduser("~"), ".aceld-skill-inbox", ".findskill")


def jget(url, tries=3, timeout=25):
    """带重试的 JSON GET；403/429 时退避。"""
    last = None
    for k in range(tries):
        req = urllib.request.Request(url, headers=UA)
        tok = os.environ.get("GITHUB_TOKEN")
        if tok and "api.github.com" in url:
            req.add_header("Authorization", "Bearer " + tok)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as f:
                return json.load(f)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 429) and k + 1 < tries:
                time.sleep(3 * (k + 1))
                continue
            if e.code == 404:
                return None
            break
        except Exception as e:                       # 网络抖动
            last = e
            if k + 1 < tries:
                time.sleep(1.5 * (k + 1))
    print("  ! 请求失败 %s (%s)" % (url[:90], type(last).__name__), file=sys.stderr)
    return None


# ── 源 1：skills.sh（有真实安装量，最可信的「被用过」信号）───────────────
def search_skills_sh(query, limit=30):
    url = "https://skills.sh/api/search?q=" + urllib.parse.quote(query)
    d = jget(url)
    if not d:
        return []
    out = []
    for s in d.get("skills", [])[:limit]:
        out.append({
            "id": s.get("id"),
            "source": s.get("source"),
            "skill": s.get("skillId"),
            "name": s.get("name"),
            "installs": int(s.get("installs") or 0),
            "stars": None,
            "license": None,
            "pushed": None,
            "origin": "skills.sh",
        })
    return out


# ── 源 2：GitHub 仓库搜索（找「技能合集仓库」，再从里面挑具体技能）──────
def search_github(query, limit=10):
    """只保留看起来是「技能合集」的仓库：名字/描述里带 skill / agent / plugin。"""
    q = urllib.parse.quote(query + " in:name,description")
    url = ("https://api.github.com/search/repositories?q=%s"
           "&sort=stars&order=desc&per_page=%d" % (q, max(limit * 3, 20)))
    d = jget(url)
    if not d:
        return []
    out = []
    for r in d.get("items", []):
        blob = (r["full_name"] + " " + (r.get("description") or "")).lower()
        if not re.search(r"skill|agent|plugin|prompt", blob):
            continue
        out.append({
            "id": r["full_name"],
            "source": r["full_name"],
            "skill": None,
            "name": r["full_name"].split("/")[-1],
            "installs": None,
            "stars": r["stargazers_count"],
            "license": (r.get("license") or {}).get("spdx_id"),
            "pushed": (r.get("pushed_at") or "")[:10],
            "origin": "github",
            "desc": (r.get("description") or "")[:110],
        })
        if len(out) >= limit:
            break
    return out


# ── 源 3：npx skills find（本地 CLI，装了就顺带用）─────────────────────
def search_npx(query, limit=20):
    import shutil
    import subprocess
    if not shutil.which("npx"):
        return []
    try:
        r = subprocess.run(["npx", "-y", "skills", "find", query],
                           capture_output=True, text=True, timeout=120)
    except Exception:
        return []
    out, seen = [], set()
    for line in (r.stdout or "").splitlines():
        # 形如：owner/repo/skill  installs:1.2k  description
        m = re.search(r"\b([\w.-]+/[\w.-]+(?:/[\w.-]+)?)\b", line)
        if not m or m.group(1) in seen:
            continue
        sid = m.group(1)
        seen.add(sid)
        inst = None
        mi = re.search(r"([\d.]+)\s*([kK])?\s*(?:installs|安装)", line)
        if mi:
            inst = int(float(mi.group(1)) * (1000 if mi.group(2) else 1))
        parts = sid.split("/")
        out.append({
            "id": sid,
            "source": "/".join(parts[:2]),
            "skill": parts[2] if len(parts) > 2 else None,
            "name": parts[-1],
            "installs": inst,
            "stars": None,
            "license": None,
            "pushed": None,
            "origin": "npx",
        })
    return out[:limit]


# ── 合并排序 ──────────────────────────────────────────────────────────
def score(c):
    """粗排：安装量为主，星标为辅。仅用于决定先看谁，不替代 vet。"""
    s = 0.0
    if c.get("installs"):
        s += min(60.0, 12.0 * (c["installs"] ** 0.25))
    if c.get("stars"):
        s += min(30.0, 10.0 * (c["stars"] ** 0.22))
    if c.get("pushed") and c["pushed"] >= time.strftime("%Y-%m-%d",
                                                        time.localtime(time.time() - 180 * 86400)):
        s += 10.0
    return s


def merge(groups):
    by = {}
    for g in groups:
        for c in g:
            k = c["id"]
            if k not in by:
                by[k] = dict(c)
                continue
            for f in ("installs", "stars", "license", "pushed"):
                if not by[k].get(f) and c.get(f):
                    by[k][f] = c[f]
            by[k]["origin"] += "+" + c["origin"]
    return sorted(by.values(), key=score, reverse=True)


def fmt_num(n):
    if n is None:
        return "-"
    if n >= 1000:
        return "%.1fk" % (n / 1000.0)
    return str(n)


def main():
    ap = argparse.ArgumentParser(description="多源检索 Agent Skill 候选")
    ap.add_argument("query", nargs="+", help="能力描述（英文关键词效果最好）")
    ap.add_argument("--source", default="all", choices=["all", "skills.sh", "github", "npx"])
    ap.add_argument("--limit", type=int, default=15, help="每源取多少条")
    ap.add_argument("--min-installs", type=int, default=0)
    ap.add_argument("--min-stars", type=int, default=0)
    ap.add_argument("--json", default=None, help="额外写出 JSON 的路径")
    a = ap.parse_args()

    queries = [" ".join(a.query)]
    if len(a.query) > 1:
        queries.append(" ".join(a.query))          # 保底：整串也当一次查询
    groups = []
    for q in queries:
        if a.source in ("all", "skills.sh"):
            print("· skills.sh  ← %r" % q, file=sys.stderr)
            groups.append(search_skills_sh(q, a.limit))
        if a.source in ("all", "github"):
            print("· github     ← %r" % q, file=sys.stderr)
            groups.append(search_github(q, max(6, a.limit // 2)))
        if a.source in ("all", "npx"):
            print("· npx skills ← %r" % q, file=sys.stderr)
            groups.append(search_npx(q, a.limit))

    cands = merge(groups)
    cands = [c for c in cands
             if (c.get("installs") or 0) >= a.min_installs
             and (c.get("stars") or 0) >= a.min_stars]

    skills = [c for c in cands if c["origin"] != "github" or c.get("skill")]
    repos = [c for c in cands if c not in skills]

    if not cands:
        print("\n没找到候选。换更窄的能力词（「pdf 表单填充」而不是「pdf」），"
              "或 --source github 看仓库层面。", file=sys.stderr)
        return 1

    if skills:
        skills.sort(key=lambda c: -(c.get("installs") or 0))
        print("\n【技能候选】按安装量排序 —— 直接用 vet.py 体检")
        print("%-44s %8s %-10s %s" % ("owner/repo/skill", "installs", "src", "说明"))
        print("-" * 92)
        for c in skills[:a.limit * 2]:
            print("%-44s %8s %-10s %s" % ((c["id"] or "")[:44],
                                          fmt_num(c.get("installs")),
                                          c["origin"],
                                          (c.get("desc") or "")[:34]))

    if repos:
        repos.sort(key=lambda c: -(c.get("stars") or 0))
        print("\n【技能合集仓库】按星标排序 —— 进去按目录找具体技能，再 vet.py owner/repo/技能名")
        print("%-40s %8s %-12s %-11s %s" % ("repo", "stars", "license", "pushed", "说明"))
        print("-" * 100)
        for c in repos[:max(6, a.limit // 2)]:
            print("%-40s %8s %-12s %-11s %s" % ((c["id"] or "")[:40],
                                                fmt_num(c.get("stars")),
                                                (c.get("license") or "-")[:12],
                                                c.get("pushed") or "-",
                                                (c.get("desc") or "")[:32]))

    os.makedirs(OUTDIR, exist_ok=True)
    path = a.json or os.path.join(OUTDIR, "candidates.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"query": queries, "candidates": cands}, f,
                  ensure_ascii=False, indent=1)
    print("\n候选 %d 条（技能 %d / 仓库 %d）→ %s"
          % (len(cands), len(skills), len(repos), path))
    print("下一步：python vet.py <owner/repo/skill>   过五条硬性淘汰线 + 安全扫描")
    return 0


if __name__ == "__main__":
    sys.exit(main())
