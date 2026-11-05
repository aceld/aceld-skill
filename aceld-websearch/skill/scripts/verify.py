#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify.py —— 交付前自检：硬门槛有没有被绕过、pack.md 和 pack.json 是否一致。

存在 ≠ 生效：rank.py 跑完不等于资料包能用。这一步专抓三类事故：
    ① 为了凑数偷偷放宽了时间/权威/热度门槛；
    ② 指标字段写了数字但没写口径，或干脆是模型估的；
    ③ pack.md 里漏了链接 / 链接和 pack.json 对不上，下游 skill 拿到的是空壳。

用法：
    python verify.py research/ai-agent/pack.json
    python verify.py research/ai-agent/pack.json --today   # 额外检查窗口是否已过期
"""
import argparse
import json
import math
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from urlnorm import domain_of, load_cfg  # noqa: E402
from rank import METRIC_CN, parse_published  # noqa: E402
from window import build as build_window  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser(description="资料包交付前校验")
    ap.add_argument("pack", help="pack.json 路径")
    ap.add_argument("--today", action="store_true", help="检查窗口是否仍然新鲜")
    a = ap.parse_args()

    with open(a.pack, encoding="utf-8") as f:
        pack = json.load(f)
    cfg = load_cfg()
    profile = pack.get("profile", cfg["default_profile"])
    prof = cfg["profiles"].get(profile)
    if not prof:
        print("FAIL 未知 profile=%s" % profile)
        return 1

    problems, warns = [], []
    w = pack.get("window", {})
    since, until, days = w.get("since"), w.get("until"), int(w.get("days") or 180)
    if not (since and until):
        problems.append("缺时间窗 since/until")
    else:
        chk = build_window(days, until)
        if chk["since"] != since:
            problems.append("窗口自洽性：until=%s 往前 %d 天应是 %s，实际写 %s"
                            % (until, days, chk["since"], since))
        if a.today:
            age = (date.today() - date.fromisoformat(until)).days
            if age > 7:
                warns.append("资料包基准日是 %d 天前，建议重跑检索" % age)

    items = pack.get("items", [])
    th = pack.get("thresholds", {})
    top_n = int(th.get("top_n") or prof["top_n"])
    min_score = float(th.get("min_score") or prof["min_score"])
    if not items:
        problems.append("入选 0 条：不能拿空资料包喂给下游 skill")
    if len(items) > top_n:
        problems.append("入选 %d 条 > top_n %d" % (len(items), top_n))

    md_path = os.path.join(os.path.dirname(os.path.abspath(a.pack)), "pack.md")
    md = ""
    if not os.path.isfile(md_path):
        problems.append("缺 pack.md（下游读的是它）")
    else:
        with open(md_path, encoding="utf-8") as f:
            md = f.read()
        if len(md) < 200:
            problems.append("pack.md 内容过短，疑似空壳")

    seen, dom = set(), {}
    for i, it in enumerate(items, 1):
        tag = "#%d %s" % (i, (it.get("title") or "?")[:28])
        url = it.get("canonical_url") or it.get("url") or ""
        if not url.startswith(("http://", "https://")):
            problems.append("%s 链接不是 http(s)：%s" % (tag, url))
        if url in seen:
            problems.append("%s 链接重复" % tag)
        seen.add(url)
        if md and url not in md:
            problems.append("%s 链接没出现在 pack.md 里" % tag)

        d = parse_published(it.get("published"))
        if not d:
            problems.append("%s 发布日期缺失/格式错" % tag)
        elif since and until and not (since <= d.isoformat() <= until):
            problems.append("%s 发布日期 %s 超出窗口" % (tag, d))

        tier = it.get("tier")
        if tier == "T3" and not th.get("allow_t3"):
            problems.append("%s 是 T3 却进了入选" % tag)
        if tier not in ("T1", "T2", "T3"):
            problems.append("%s tier 非法：%s" % (tag, tier))
        if not it.get("metrics_verified"):
            problems.append("%s metrics_verified 不是 true（指标不可核验）" % tag)
        if not it.get("metric_source"):
            problems.append("%s 缺指标口径/出处" % tag)
        if not it.get("readable"):
            problems.append("%s readable 不是 true（没验证真能读）" % tag)
        if not it.get("summary"):
            problems.append("%s 缺正文摘要" % tag)
        kind = it.get("kind", "article")
        pm = cfg["primary_metric"].get(kind, "views")
        minm = (th.get("min_metrics") or prof["min_metrics"]).get(kind, {})
        m = it.get("metrics") or {}
        if float(m.get(pm) or 0) < float(minm.get(pm) or 0):
            problems.append("%s 主指标 %s 未达门槛 %s"
                            % (tag, METRIC_CN.get(pm, pm), minm.get(pm)))
        cneed = float(minm.get("comments") or 0)
        if cneed and float(m.get("comments") or 0) < cneed:
            problems.append("%s 评论数未达门槛 %d" % (tag, cneed))
        s = float((it.get("score") or {}).get("total") or 0)
        if s < min_score:
            problems.append("%s 综合分 %.1f < %.1f" % (tag, s, min_score))
        dm = domain_of(url)
        dom[dm] = dom.get(dm, 0) + 1

    cap = max(1, int(math.ceil(
        top_n * float(th.get("max_domain_share") or prof["max_domain_share"]))))
    for d, n in dom.items():
        if n > cap:
            problems.append("域名 %s 占 %d 条 > 上限 %d" % (d, n, cap))

    if pack.get("waived"):
        warns.append("有 %d 条「权威一手但无公开热度」单列，不占入选名额" % len(pack["waived"]))
    if not pack.get("queries"):
        warns.append("没记检索留痕（queries 为空），下次无法复现")

    print("资料包：%s" % a.pack)
    print("  入选 %d / 备选 %d / 淘汰 %d ｜窗口 %s ~ %s ｜profile=%s"
          % (len(items), len(pack.get("alternates", [])), len(pack.get("rejected", [])),
             since, until, profile))
    for x in warns:
        print("  WARN  " + x)
    if problems:
        for x in problems:
            print("  FAIL  " + x)
        print("\n结论：FAIL（%d 项）→ 修完再交付，别把不合格链接喂给下游技能" % len(problems))
        return 1
    print("\n结论：PASS ✓ 每条都满足「近 %d 天 + T1/T2 权威 + 可核验高指标 + 可读原文链接」"
          % days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
