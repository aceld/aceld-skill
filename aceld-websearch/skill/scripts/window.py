#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""window.py —— 时间窗唯一真源：别让模型自己算「半年内」是哪天。

为什么必须有这个脚本：
    1. 模型手算 180 天前经常算错月份/闰年，跨年时尤其离谱；
    2. 搜索引擎的 freshness 只能表达 d1..d30 / m1..m12 / y1..y5，
       「半年」只能写 m6（最近 6 个日历月），它和「今天往前 180 天」并不完全等价；
    3. 所以两道窗口取严：搜索用 freshness=m6 粗筛，脚本用 since=today-180d 硬过滤。

用法：
    python window.py                          # 文本：时间窗 + 该用的 freshness
    python window.py --json                   # JSON，供 Agent 直接读
    python window.py --days 90 --json        # 改成近 90 天
    python window.py --as-of 2026-11-05      # 固定基准日（测试/复现用）
    python window.py --check 2026-06-01 2025-01-01
    python window.py --topic "AI Agent 课程" --json   # 附带建议检索式片段
"""
import argparse
import json
import math
import sys
from datetime import date, datetime, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_DAYS = 180


def parse_day(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def freshness_hint(days):
    """把天数翻译成宿主搜索工具能接受的 freshness 值。"""
    if days <= 30:
        return "d%d" % max(1, days)
    months = min(12, max(1, int(math.ceil(days / 30.0))))
    return "m%d" % months


def build(days=DEFAULT_DAYS, as_of=None, topic=""):
    until = parse_day(as_of) if as_of else date.today()
    since = until - timedelta(days=days)
    f = freshness_hint(days)
    return {
        "schema_version": "1.0",
        "topic": topic,
        "as_of": until.isoformat(),
        "since": since.isoformat(),
        "until": until.isoformat(),
        "days": days,
        "freshness": f,
        "rule": "两道窗口取严：搜索侧 freshness=%s，脚本侧按 [%s, %s] 硬过滤；"
                "日期一律取文章页面标注的发布日期，不是搜索结果的「N 天前」、不是抓取时间。"
                % (f, since.isoformat(), until.isoformat()),
        "year_tokens": sorted({str(until.year), str(until.year - 1)}, reverse=True),
    }


def main():
    ap = argparse.ArgumentParser(description="计算「近 N 天」时间窗（默认 180 天）")
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    ap.add_argument("--as-of", default=None, help="基准日 YYYY-MM-DD，默认今天")
    ap.add_argument("--topic", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", nargs="+", metavar="DATE", help="检查若干日期是否落在窗内")
    a = ap.parse_args()

    w = build(a.days, a.as_of, a.topic)

    if a.check:
        since, until = parse_day(w["since"]), parse_day(w["until"])
        for s in a.check:
            try:
                d = parse_day(s)
            except ValueError:
                print("  ? %-12s 日期格式错误（要 YYYY-MM-DD）" % s)
                continue
            ok = since <= d <= until
            age = (until - d).days
            print("  %s %-12s %s（距今 %d 天）" % ("✓" if ok else "✗", s,
                                                 "在窗内" if ok else "超窗", age))
        return 0

    if a.json:
        print(json.dumps(w, ensure_ascii=False, indent=2))
        return 0

    print("时间窗：%s ~ %s（近 %d 天，基准日 %s）" %
          (w["since"], w["until"], w["days"], w["as_of"]))
    print("搜索侧 freshness=%s   ← 宿主 WebSearch 最长只能表达到月粒度，半年写 m6" % w["freshness"])
    print("脚本侧按 [%s, %s] 逐条硬过滤，取两者更严者" % (w["since"], w["until"]))
    print("建议检索式里带年份词：%s" % " / ".join(w["year_tokens"]))
    print("")
    print(w["rule"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
