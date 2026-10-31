#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preflight.py —— 开工前置检查：本地有没有能用的技能？线上有没有更好的？

用法：
    python preflight.py "竖版视频 抖音 版式重排"
    python preflight.py "pdf 表单填充" --top 5
    python preflight.py --check-updates          # 只查已登记来源的上游更新
    python preflight.py --list                   # 只看本地技能清单

设计目标：**30 秒出结论，三选一**——
    ① 直接用本地技能 X
    ② 本地没有，线上有 N 个候选（最高安装量 X）→ 走 vet
    ③ 上游有新提交 / 线上有更强同类 → 先对比再决定

不自动安装、不改任何技能。只读。
"""
import argparse
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request

SKILLS_DIR = os.path.expanduser("~/.workbuddy-ai/skills")
SOURCES = os.path.join(SKILLS_DIR, ".findskill-sources.json")
UA = {"User-Agent": "aceld-findskill/1.0 (+https://github.com/aceld/aceld-skill)"}
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".aceld-skill-inbox", ".cache")
CACHE_TTL = 6 * 3600

# 中文停用词：不参与匹配，避免「的/和/做/一个」把分数抬起来
STOP = set("的 了 和 与 或 把 被 在 是 有 个 一 这 那 我 你 他 要 做 用 就 都 也 还 但 而 对 从 到 让 给 能 会 上 下 里".split())


# ── 通用 ──────────────────────────────────────────────────────────────
def get_json(url, timeout=20):
    import hashlib
    key = hashlib.sha1(url.encode()).hexdigest()[:20]
    p = os.path.join(CACHE_DIR, key + ".json")
    try:
        if time.time() - os.path.getmtime(p) <= CACHE_TTL:
            return json.load(open(p, encoding="utf-8"))
    except Exception:
        pass
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as f:
            v = json.loads(f.read().decode("utf-8", "replace"))
        os.makedirs(CACHE_DIR, exist_ok=True)
        json.dump(v, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        return v
    except Exception:
        return None


def parse_frontmatter(path):
    try:
        t = open(path, encoding="utf-8").read()
    except OSError:
        return None
    if not t.startswith("---"):
        return {"name": os.path.basename(os.path.dirname(path)),
                "description": "", "path": path, "_body": t.lower()}
    end = t.find("\n---", 3)
    if end < 0:
        return None
    meta, cur = {}, None
    for line in t[3:end].splitlines():
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", line)
        if m and not line.startswith(" "):
            k, v = m.group(1), m.group(2).strip()
            if v in ("", "|", ">"):
                meta[k] = ""
                cur = k
            else:
                meta[k] = v.strip("'\"")
                cur = None
        elif cur and line.startswith(" "):
            meta[cur] = (meta.get(cur, "") + " " + line.strip()).strip()
    meta["path"] = path
    meta["_body"] = t[end + 4:].lower()
    return meta


# ── 本地技能 ──────────────────────────────────────────────────────────
def scan_local():
    out = []
    if not os.path.isdir(SKILLS_DIR):
        return out
    for d in sorted(os.listdir(SKILLS_DIR)):
        p = os.path.join(SKILLS_DIR, d, "SKILL.md")
        if not os.path.isfile(p):
            continue
        m = parse_frontmatter(p)
        if not m:
            continue
        m["dir"] = d
        m["mtime"] = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(p)))
        out.append(m)
    return out


def build_tokens(q):
    """整串拆成短语（权重 2）+ 短语内的中文 2-gram / 英文词（权重 1）。

    只切 2-gram 会产生「式重」「版视」这种跨词垃圾，所以短语本身也当 token，
    命中短语比命中碎片更值钱。
    """
    toks = {}
    for ph in re.split(r"[\s,，、/|]+", q.strip()):
        if not ph:
            continue
        toks[ph.lower()] = max(toks.get(ph.lower(), 0), 2.0)
        for w in re.findall(r"[A-Za-z][A-Za-z0-9+#._-]{1,}", ph):
            toks[w.lower()] = max(toks.get(w.lower(), 0), 1.0)
        for seg in re.findall(r"[\u4e00-\u9fff]+", ph):
            for i in range(len(seg) - 1):
                g = seg[i:i + 2]
                if g not in STOP:
                    toks[g] = max(toks.get(g, 0), 1.0)
    return toks


def score_skill(meta, toks):
    """name ×1.5 / description ×1.2 / 正文 ×0.8，按总权重归一。

    正文必须参与：像「竖版」这种词只出现在 SKILL.md 的章节里，
    description 永远不会写，只看 description 会把最该选的技能漏掉。
    但**只靠正文命中时封顶 20 分**——SKILL.md 很长，例子文字极容易造成假匹配
    （「pdf」曾靠课程技能里的「处理 PDF 讲稿」一句把自己顶到 34 分）。
    """
    if not toks:
        return 0.0
    name = (meta.get("name") or "").lower()
    desc = (meta.get("description") or "").lower()
    body = meta.get("_body") or ""
    total = sum(toks.values())
    got = strong = 0.0
    for t, w in toks.items():
        if t in name:
            got += w * 1.5; strong += w * 1.5
        elif t in desc:
            got += w * 1.2; strong += w * 1.2
        elif t in body:
            got += w * 0.8
    s = min(100.0, 100.0 * got / total)
    if strong == 0:
        s = min(s, 20.0)
    return s


def weight_tokens(local, toks):
    """IDF 加权：只在 1 个技能里出现的词，比在 6 个里都出现的词更值钱。

    不要用硬过滤——小语料库里「音色」这类词会因为出现 4 次被误杀，
    结果「配音」任务里 aceld-voice 和 aceld-course 打平，选错技能。
    """
    n = max(1, len(local))
    df = {t: 0 for t in toks}
    for m in local:
        blob = ((m.get("name") or "") + " " + (m.get("description") or "")
                + " " + (m.get("_body") or "")).lower()
        for t in toks:
            if t in blob:
                df[t] += 1
    out, everywhere = {}, []
    for t, w in toks.items():
        if df[t] >= n:                      # 所有技能都有 → 没有区分度
            everywhere.append(t)
            continue
        out[t] = w * (1.0 + math.log(1.0 + n / max(1, df[t])) / 2.0)
    return (out or toks), everywhere


# ── 线上候选 ──────────────────────────────────────────────────────────
def online(query, top=5):
    """整串命中率低（中文长句经常 0 结果），所以拆成短语分别查再合并。"""
    variants = [query]
    phrases = [p for p in re.split(r"[\s,，、/|]+", query.strip()) if p]
    if len(phrases) > 1:
        variants += phrases
    seen = {}
    for v in variants[:4]:
        d = get_json("https://skills.sh/api/search?q=" + urllib.parse.quote(v))
        if not d:
            continue
        for s in d.get("skills", []):
            i = s.get("id")
            if not i:
                continue
            seen[i] = max(seen.get(i, 0), int(s.get("installs") or 0))
    rows = [{"id": k, "installs": v} for k, v in seen.items()]
    rows.sort(key=lambda x: -x["installs"])
    return rows[:top]


# ── 更新检查 ──────────────────────────────────────────────────────────
def load_sources():
    try:
        return json.load(open(SOURCES, encoding="utf-8"))
    except Exception:
        return {}


def repo_meta(owner, repo):
    d = get_json("https://api.github.com/repos/%s/%s" % (owner, repo))
    if d and "pushed_at" in d:
        return {"pushed": d["pushed_at"][:10],
                "stars": d.get("stargazers_count", 0)}
    d = get_json("https://ungh.cc/repos/%s/%s" % (owner, repo))
    if d and d.get("repo"):
        return {"pushed": (d["repo"].get("pushedAt") or "")[:10],
                "stars": d["repo"].get("stars", 0)}
    return None


def check_updates():
    src = load_sources()
    if not src:
        print("还没登记任何来源。装技能时用 install.sh 会自动登记，或手工建：")
        print("  %s" % SOURCES)
        print('  形如 {"aceld-course": {"source": "aceld/aceld-skill", "checked": "2026-10-31"}}')
        return 0
    print("检查 %d 个已登记技能的上游更新\n" % len(src))
    hits = 0
    for name, info in sorted(src.items()):
        s = info.get("source") or ""
        if "/" not in s:
            continue
        o, r = s.split("/")[:2]
        m = repo_meta(o, r)
        if not m:
            print("  ? %-28s 查不到 %s" % (name, s))
            continue
        checked = info.get("checked") or ""
        newer = m["pushed"] > checked if checked else True
        if newer:
            hits += 1
            print("  ↑ %-28s 上游 %s 有新提交（本地检查于 %s）★%d"
                  % (name, m["pushed"], checked or "-", m["stars"]))
        else:
            print("  ✓ %-28s 无更新（上游 %s / 本地 %s）" % (name, m["pushed"], checked))
    print("\n%d 个技能有上游更新。看差异：python absorb.py <owner/repo/skill> --force 后比对指纹。"
          % hits)
    return 0


def main():
    ap = argparse.ArgumentParser(description="开工前置检查")
    ap.add_argument("query", nargs="*", help="任务关键词")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--online", action="store_true", help="强制联网（默认也会查）")
    ap.add_argument("--no-online", action="store_true", help="只查本地，不联网")
    ap.add_argument("--check-updates", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    local = scan_local()

    if a.list:
        print("本地技能 %d 个：\n" % len(local))
        for m in local:
            print("  %-32s %s" % (m["dir"], (m.get("description") or "")[:52]))
        return 0

    if a.check_updates:
        return check_updates()

    q = " ".join(a.query).strip()
    if not q:
        print("给个任务关键词，例如：python preflight.py \"竖版视频 版式\"")
        return 2

    toks = build_tokens(q)
    # 自己是「找技能的工具」，不该被当成答案推荐
    pool = [m for m in local if (m.get("name") or m["dir"]) != "aceld-findskill"]
    toks, dropped = weight_tokens(pool, toks)
    # 同分时优先「更专注」的技能：正文短的通常专门干这件事，
    # 正文长的是流水线大技能，什么都能沾一点（如「配音」时 course 和 voice 都 100 分）
    ranked = sorted(((score_skill(m, toks), m) for m in pool),
                    key=lambda x: (-round(x[0], 1), len(x[1].get("_body") or "")))
    top_local = [(s, m) for s, m in ranked if s > 0][:3]

    print("任务：%s" % q)
    print("关键词：%s" % " / ".join(sorted(toks)[:14]))
    if dropped:
        print("        已忽略（所有技能都有，无区分度）：%s" % " / ".join(dropped[:8]))
    print()

    print("【本地】")
    if not top_local:
        print("  没有相关技能")
    for s, m in top_local:
        print("  %5.1f  %-30s %s" % (s, m["dir"], (m.get("description") or "")[:46]))

    rows = []
    if not a.no_online:
        print("\n【线上】skills.sh 按安装量")
        rows = online(q, a.top)
        if not rows:
            print("  查不到（网络不通或关键词太窄；国内先设 https_proxy）")
        for r in rows:
            print("  %8s  %s" % ("%.1fk" % (r["installs"] / 1000.0)
                                 if r["installs"] >= 1000 else r["installs"], r["id"]))

    # ── 结论 ──────────────────────────────────────────────────────────
    print("\n【结论】")
    best = top_local[0] if top_local else None
    best_online = rows[0] if rows else None
    if best and best[0] >= 35:
        print("  → 直接用本地 `%s`（匹配度 %.0f）。" % (best[1]["dir"], best[0]))
        if best_online and best_online["installs"] >= 20000:
            print("    线上 `%s` 安装量 %s，若本地流程不顺手可对比一下。"
                  % (best_online["id"], best_online["installs"]))
    elif best and best[0] >= 15:
        print("  → 本地 `%s` 沾边（匹配度 %.0f），但可能不够贴。"
              % (best[1]["dir"], best[0]))
        if best_online:
            print("    先花 2 分钟 vet 一下线上 `%s`（安装量 %s）再决定。"
                  % (best_online["id"], best_online["installs"]))
        else:
            print("    先按本地技能做，遇到具体缺口再用 find.py 搜。")
    elif best_online:
        print("  → 本地没有能覆盖的技能。线上最高：`%s`（安装量 %s）。"
              % (best_online["id"], best_online["installs"]))
        print("    下一步：python vet.py %s" % best_online["id"])
    else:
        print("  → 本地线上都没有。写清缺口再用 find.py 换关键词搜，或自己写一个。")
    print("\n（preflight 只读不改：不安装、不动任何技能文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
