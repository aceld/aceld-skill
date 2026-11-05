#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rank.py —— 候选池 → 资料包：硬门槛过滤 → 评分 → 去重/域名分散 → pack.md + pack.json

分工（很重要）：
    联网检索、打开页面、读计数，交给宿主的 WebSearch / WebFetch；
    本脚本只做**确定性的离线判定**，不联网、不猜数字、不编指标。
    Agent 把逐条核验过的事实写进 candidates.json，脚本负责「不过线就淘汰」。

用法：
    python rank.py --template > candidates.json          # 先拿模板
    python rank.py -i candidates.json -o research/ai-agent
    python rank.py -i candidates.json -o out --profile wechat --top 10
    python rank.py -i candidates.json -o out --days 90 --allow-waiver

硬门槛（不过线一律淘汰，不会「悄悄放宽」）：
    ① 发布日期落在 [today-180d, today] 内，且来自页面标注
    ② 权威层级 T1/T2（T3 默认淘汰），黑名单/短链/非原文淘汰
    ③ 指标可核验：metrics_verified=true 且主指标、评论数达到该 profile 阈值
    ④ 可读：readable=true（WebFetch 真抓到正文）
"""
import argparse
import json
import math
import os
import re
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from urlnorm import inspect as url_inspect, load_cfg, normalize  # noqa: E402
from window import build as build_window, parse_day  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.normpath(os.path.join(HERE, "..", "assets"))
EXAMPLE = os.path.join(ASSETS, "candidates.example.json")

TEMPLATE = {
    "topic": "（必填）一句话主题，例如：AI Agent 工程化落地",
    "profile": "tech",
    "window": {"since": "", "until": "", "days": 180, "freshness": "m6",
               "note": "留空时由 window.py 按 today-180d 自动生成"},
    "queries": [
        {"query": "（中英双语关键词 + 年份词）", "engine": "WebSearch",
         "freshness": "m6", "allowed_domains": [], "hits": 0, "note": ""}
    ],
    "candidates": [
        {
            "title": "文章标题（原文标题，不要改写）",
            "url": "https://原文可读链接",
            "author": "作者 / 机构（可识别）",
            "source": "站点 / 媒体名",
            "published": "YYYY-MM-DD（页面标注的发布日期）",
            "kind": "article",
            "tier": "T1",
            "tier_reason": "覆盖域名表时必填理由",
            "metrics": {"views": 0, "likes": 0, "comments": 0, "shares": 0, "favorites": 0},
            "metric_source": "页面公开计数 / 平台榜单 / 第三方可见数据（写清口径）",
            "metrics_verified": False,
            "readable": False,
            "readable_evidence": "WebFetch 抓到正文 N 段，无需登录/付费",
            "summary": "基于正文写的一句话（不是搜索摘要）",
            "value_for": "下游能拿它干嘛：课程案例 / 数据 / 反例 / 行文角度",
            "cross_refs": 0,
            "is_original": True,
            "heat_waiver": False
        }
    ]
}

KIND_LABEL = {"article": "文章", "video": "视频", "post": "帖子",
              "thread": "讨论串", "repo": "仓库", "paper": "论文"}
METRIC_CN = {"views": "阅读/播放", "likes": "点赞", "comments": "评论",
             "shares": "转发", "favorites": "收藏", "stars": "star",
             "upvotes": "赞同", "citations": "引用", "coins": "投币",
             "danmaku": "弹幕"}


def fmt_num(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "0"
    if n >= 100000000:
        return "%.2f亿" % (n / 100000000)
    if n >= 10000:
        return "%.1f万" % (n / 10000)
    return "%d" % int(n)


def parse_published(s):
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m", "%Y/%m"):
        try:
            d = datetime.strptime(s, fmt)
            return d.date().replace(day=1) if fmt in ("%Y-%m", "%Y/%m") else d.date()
        except ValueError:
            continue
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)  # ISO datetime / 带时区
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def norm_title(t):
    return re.sub(r"[\s\W_]+", "", (t or "").lower())


def score_one(it, prof, cfg, until, days):
    tier = it.get("_tier", "T3")
    authority = {"T1": 35, "T2": 24, "T3": 8}.get(tier, 8)
    kind = it.get("kind", "article")
    primary_field = cfg["primary_metric"].get(kind, "views")
    metrics = it.get("metrics") or {}
    thr = (prof["min_metrics"].get(kind) or {}).get(primary_field, 1) or 1
    ratio = max(0.0, float(metrics.get(primary_field) or 0)) / thr
    heat = 18 * min(1.0, math.log10(1 + ratio) / math.log10(101))
    interaction = 0
    for k in ("comments", "likes", "shares", "favorites", "upvotes", "coins"):
        if float(metrics.get(k) or 0) > 0:
            interaction += 2.5
    heat = min(35, heat + min(10, interaction))

    age = max(0, (until - parse_published(it.get("published"))).days)
    fresh = 20 * (max(0.0, 1 - age / float(days)) ** 0.7)

    read = (6 if it.get("is_original", True) else 0) + \
           (4 if it.get("readable_evidence") else 0)
    bonus = min(5, 2 * int(it.get("cross_refs") or 0)) + \
            (3 if len([v for v in metrics.values() if float(v or 0) > 0]) >= 3 else 0)

    total = min(100, authority + heat + fresh + read + bonus)
    return {
        "total": round(total, 1),
        "authority": round(authority, 1),
        "heat": round(heat, 1),
        "freshness": round(fresh, 1),
        "readability": round(read, 1),
        "bonus": round(bonus, 1),
        "age_days": age,
        "primary_field": primary_field,
    }


def filter_one(raw, cfg, prof, profile, win, allow_t3, allow_waiver):
    """返回 (条目, 淘汰原因列表, 是否 waived)。"""
    it = dict(raw)
    reasons = []
    since, until = parse_day(win["since"]), parse_day(win["until"])
    url = it.get("url", "")

    u = url_inspect(url, cfg, profile)
    it["canonical_url"] = it.get("canonical_url") or u["canonical"]
    it["domain"] = u["domain"]
    if u["blocked"]:
        reasons.append("URL 不可读：" + "；".join(u["reasons"]))
    if u["needs_original_lookup"]:
        hint = "、".join(x for x in u["reasons"] if "原文" in x or "短链" in x) or "跳转 / 分享 / 快照页"
        reasons.append("疑似非原文/中间页（%s）：回溯原文链接后再填" % hint)

    manual = (raw.get("tier") or "").upper()
    listed = u["tier"]
    if manual in ("T1", "T2", "T3"):
        if manual != listed and not raw.get("tier_reason"):
            reasons.append("tier 覆盖了域名判定（%s→%s）但没写 tier_reason" % (listed, manual))
        tier = manual
    elif listed == "UNKNOWN":
        tier = "T3"
        if not (allow_t3 or prof.get("allow_t3")):
            reasons.append("域名未分类且未手工给 tier → 按 T3 处理")
    else:
        tier = listed
    it["_tier"] = tier
    if tier == "T3" and not (allow_t3 or prof.get("allow_t3")):
        reasons.append("T3 一般 UGC/聚合站，默认不收（%s）" % (u["matched_domain"] or "未分类域名"))

    d = parse_published(it.get("published"))
    if not d:
        reasons.append("缺页面标注的发布日期（或格式不对）")
    else:
        it["published"] = d.isoformat()
        if d > until:
            reasons.append("发布日期 %s 晚于基准日 %s" % (d, until))
        elif d < since:
            reasons.append("超窗：%s 早于 %s（距今 %d 天 > %d 天）"
                           % (d, since, (until - d).days, win["days"]))

    kind = it.get("kind", "article")
    if kind not in prof["min_metrics"]:
        reasons.append("未知 kind=%s" % kind)
        kind = "article"
        it["kind"] = kind
    minm = prof["min_metrics"].get(kind, {})
    pm = cfg["primary_metric"].get(kind, "views")
    metrics = it.get("metrics") or {}
    if not it.get("metrics_verified"):
        reasons.append("指标未核验（禁止用搜索摘要里的数字凑数）")
    else:
        v = float(metrics.get(pm) or 0)
        need = float(minm.get(pm) or 0)
        if v < need:
            reasons.append("主指标不足：%s %s < 门槛 %s" % (METRIC_CN.get(pm, pm), fmt_num(v), fmt_num(need)))
        cneed = float(minm.get("comments") or 0)
        cval = float(metrics.get("comments") or 0)
        if cneed and cval < cneed:
            reasons.append("评论数不足：%s < 门槛 %s" % (fmt_num(cval), fmt_num(cneed)))
        if not it.get("metric_source"):
            reasons.append("缺 metric_source：热度数字没写口径/出处")
    if not it.get("readable"):
        reasons.append("未验证可读（WebFetch 没抓到正文，或需登录/付费/App）")
    if not it.get("summary"):
        reasons.append("缺基于正文的一句话摘要")

    # heat_waiver：官方 RFC / 刚发的论文这类一手权威，平台往往没有公开计数。
    # 默认不收（用户要的就是高指标）；--allow-waiver 才单列，且永不占 Top N。
    waived = False
    if it.get("heat_waiver"):
        if allow_waiver or prof.get("allow_waiver"):
            waived = True
            it["waiver_reason"] = "一手权威但平台不公开热度计数（不计入入选名额）"
            reasons = [r for r in reasons
                       if not ("主指标不足" in r or "评论数不足" in r
                               or "指标未核验" in r or "缺 metric_source" in r)]
        else:
            reasons.append("无公开热度（heat_waiver）：默认不收；确需一手权威时加 --allow-waiver 单列")
    return it, reasons, waived


def pick_top(valid, top_n, max_share):
    """排序 + 去重 + 同域名限流，返回 (items, alternates, drop_notes)。"""
    valid = sorted(valid, key=lambda x: (x["score"]["total"], x["published"]), reverse=True)
    items, alternates, seen_url, seen_title = [], [], set(), set()
    per_domain = {}
    cap = max(1, int(math.ceil(top_n * max_share)))
    for it in valid:
        key_u, key_t = it["canonical_url"], norm_title(it.get("title"))
        if key_u in seen_url:
            it["_drop"] = "重复链接"
            continue
        if key_t in seen_title:
            it["_drop"] = "同题重复（保留分数更高的）"
            continue
        d = it["domain"]
        if per_domain.get(d, 0) >= cap:
            alternates.append(dict(it, _drop="同域名占比上限（%d 条）" % cap))
            continue
        items.append(it)
        seen_url.add(key_u)
        seen_title.add(key_t)
        per_domain[d] = per_domain.get(d, 0) + 1
        if len(items) >= top_n:
            break
    started = {id(x) for x in items}
    for it in valid:
        if id(it) in started or it.get("_drop"):
            continue
        alternates.append(dict(it, _drop="达标但 Top %d 已满" % top_n))
    return items, alternates


def render_md(pack):
    w, st, prof = pack["window"], pack["stats"], pack["profile"]
    L = []
    L.append("# 资料包：%s" % pack["topic"])
    L.append("")
    L.append("> **给下游 skill 的输入**：本文件是可读链接清单。直接使用「入选链接」里的链接，"
             "机器消费请读同目录 `pack.json`（字段契约见 `aceld-websearch` 技能的 "
             "`references/04-contract.md`）。")
    L.append("")
    L.append("- 生成时间：`%s`" % pack["generated_at"])
    L.append("- 时间窗：`%s ~ %s`（近 %d 天，硬性）｜搜索侧 freshness=`%s`"
             % (w["since"], w["until"], w["days"], w["freshness"]))
    L.append("- 画像：`%s`｜检索式 %d 条｜候选 %d → 入选 %d / 备选 %d / 淘汰 %d"
             % (prof, len(pack["queries"]), st["candidates"], len(pack["items"]),
                len(pack["alternates"]), len(pack["rejected"])))
    L.append("- 硬门槛：页面发布日期在窗内 · T1/T2 权威源 · 指标可核验且达阈值 · 链接真能读到正文")
    th = pack.get("thresholds", {})
    relax = []
    if th.get("allow_t3"):
        relax.append("`--allow-t3`（允许 T3 源入选）")
    if th.get("allow_waiver"):
        relax.append("`--allow-waiver`（一手权威但平台无公开热度，单列且不占入选名额）")
    if int(w.get("days") or 180) != 180:
        relax.append("`--days %s`（时间窗已改为近 %s 天）" % (w["days"], w["days"]))
    if relax:
        L.append("- **已显式放宽**：%s；其余硬门槛一律未放宽。" % "、".join(relax))
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 入选链接（按综合分排序）")
    L.append("")
    for i, it in enumerate(pack["items"], 1):
        s = it["score"]
        L.append("### %d. %s" % (i, it.get("title", "（无标题）")))
        L.append("")
        L.append("- 🔗 **可读链接**：<%s>" % it["canonical_url"])
        L.append("- 来源：%s｜层级：%s｜类型：%s｜发布：%s（%d 天前）"
                 % (it.get("source") or it.get("domain"), it.get("tier", "?"),
                    KIND_LABEL.get(it.get("kind"), it.get("kind")),
                    it["published"], s["age_days"]))
        heat = " · ".join("%s %s" % (METRIC_CN.get(k, k), fmt_num(v))
                         for k, v in (it.get("metrics") or {}).items() if float(v or 0) > 0)
        L.append("- 热度：**%s**（口径：%s）" % (heat or "无", it.get("metric_source") or "未标注"))
        L.append("- 评分：`%.1f`（权威 %.1f / 热度 %.1f / 新鲜 %.1f）"
                 % (s["total"], s["authority"], s["heat"], s["freshness"]))
        L.append("- 摘要：%s" % it.get("summary"))
        L.append("- 可用作：%s" % (it.get("value_for") or "未标注"))
        L.append("- 可读核验：%s" % (it.get("readable_evidence") or "未记录"))
        L.append("")
    if pack["waived"]:
        L.append("## 权威一手（无公开热度，单独列出、不占入选名额）")
        L.append("")
        for it in pack["waived"]:
            L.append("- [%s] <%s> — %s（%s）"
                     % (it.get("title"), it["canonical_url"], it.get("source"), it["published"]))
        L.append("")
    if pack["alternates"]:
        L.append("## 备选（过了硬门槛，但没进 Top N）")
        L.append("")
        for it in pack["alternates"]:
            L.append("- %.1f ｜ [%s](%s) — %s"
                     % (it["score"]["total"], it.get("title"), it["canonical_url"], it.get("_drop")))
        L.append("")
    if pack["rejected"]:
        L.append("## 淘汰留痕（每条都给原因，方便回头补检索）")
        L.append("")
        for it in pack["rejected"]:
            L.append("- %s — %s" % ((it.get("title") or it.get("url") or "?")[:50],
                                    "；".join(it["reject_reasons"])))
        L.append("")
    L.append("## 检索留痕")
    L.append("")
    for q in pack["queries"]:
        L.append("- `%s`｜%s｜freshness=`%s`｜限定域：%s｜命中 %s"
                 % (q.get("query"), q.get("engine", "WebSearch"), q.get("freshness", "m6"),
                    ",".join(q.get("allowed_domains") or []) or "不限", q.get("hits", "-")))
    L.append("")
    L.append("---")
    L.append("")
    L.append("> 指标全部来自页面公开可见计数，未做任何估算。若某平台不公开阅读量，"
             "该条会被淘汰或降级，绝不用搜索摘要里的数字代替。")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description="候选池 → 可读链接资料包")
    ap.add_argument("-i", "--input", default="candidates.json")
    ap.add_argument("-o", "--out", default="research/pack")
    ap.add_argument("--profile", default="")
    ap.add_argument("--days", type=int, default=0, help="覆盖时间窗天数（默认 180）")
    ap.add_argument("--as-of", default=None, help="固定基准日，测试用")
    ap.add_argument("--top", type=int, default=0)
    ap.add_argument("--allow-t3", action="store_true")
    ap.add_argument("--allow-waiver", action="store_true",
                    help="允许无公开热度的一手权威单列（仍不占 Top N）")
    ap.add_argument("--template", action="store_true", help="打印 candidates.json 模板并退出")
    a = ap.parse_args()

    if a.template:
        print(json.dumps(TEMPLATE, ensure_ascii=False, indent=2))
        return 0

    cfg = load_cfg()
    with open(a.input, encoding="utf-8") as f:
        data = json.load(f)
    profile = a.profile or data.get("profile") or cfg["default_profile"]
    if profile not in cfg["profiles"]:
        print("!! 未知 profile：%s（可选 %s）" % (profile, ", ".join(cfg["profiles"])))
        return 2
    prof = cfg["profiles"][profile]
    days = a.days or (data.get("window") or {}).get("days") or 180
    win = build_window(days, a.as_of, data.get("topic", ""))
    # 允许 candidates.json 显式给窗口（复现历史资料包时用），但必须自洽
    ext = data.get("window") or {}
    if ext.get("since") and ext.get("until") and not a.as_of and not a.days:
        win["since"], win["until"] = ext["since"], ext["until"]
    win["days"] = days
    top_n = a.top or prof["top_n"]

    valid, rejected, waived = [], [], []
    for raw in data.get("candidates", []):
        it, reasons, is_waived = filter_one(raw, cfg, prof, profile, win,
                                            a.allow_t3, a.allow_waiver)
        if is_waived and not reasons:
            waived.append(it)
            continue
        if reasons:
            rejected.append(dict(it, reject_reasons=reasons))
            continue
        it["score"] = score_one(it, prof, cfg, parse_day(win["until"]), days)
        if it["score"]["total"] < prof["min_score"]:
            rejected.append(dict(it, reject_reasons=[
                "综合分 %.1f < %s 门槛 %.1f" % (it["score"]["total"], profile, prof["min_score"])]))
            continue
        valid.append(it)

    items, alternates = pick_top(valid, top_n, prof["max_domain_share"])
    pack = {
        "schema_version": "1.0",
        "skill": "aceld-websearch",
        "topic": data.get("topic", ""),
        "profile": profile,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "window": win,
        "thresholds": {
            "min_metrics": prof["min_metrics"],
            "min_score": prof["min_score"],
            "top_n": top_n,
            "max_domain_share": prof["max_domain_share"],
            "allow_t3": a.allow_t3 or prof["allow_t3"],
            "allow_waiver": a.allow_waiver or prof["allow_waiver"],
        },
        "queries": data.get("queries", []),
        "items": [{k: v for k, v in it.items() if not k.startswith("_drop")}
                  for it in items],
        "alternates": alternates,
        "waived": [{k: v for k, v in it.items() if k != "reject_reasons"}
                   for it in waived],
        "rejected": rejected,
        "stats": {"candidates": len(data.get("candidates", [])),
                  "valid": len(valid), "selected": len(items),
                  "alternates": len(alternates), "rejected": len(rejected),
                  "waived": len(waived)},
    }
    # tier 写进正式字段，方便下游读
    for it in pack["items"] + pack["alternates"] + pack["waived"] + pack["rejected"]:
        if "_tier" in it:
            it["tier"] = it.pop("_tier")

    out = a.out
    os.makedirs(out, exist_ok=True)
    pj, pm = os.path.join(out, "pack.json"), os.path.join(out, "pack.md")
    with open(pj, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)
    with open(pm, "w", encoding="utf-8") as f:
        f.write(render_md(pack))

    print("资料包：%s" % out)
    print("  窗口 %s ~ %s（%d 天）｜profile=%s" % (win["since"], win["until"], days, profile))
    print("  候选 %d → 入选 %d / 备选 %d / 权威免热度 %d / 淘汰 %d"
          % (pack["stats"]["candidates"], len(items), len(alternates),
             len(waived), len(rejected)))
    for i, it in enumerate(items, 1):
        print("  %d. %5.1f  [%s] %s" % (i, it["score"]["total"], it["tier"],
                                       it.get("title", "")[:44]))
    if rejected:
        print("\n  淘汰原因（前 8 条）：")
        for it in rejected[:8]:
            print("    - %s → %s" % ((it.get("title") or "?")[:32],
                                    "；".join(it["reject_reasons"])[:110]))
    if not items:
        print("\n!! 入选 0 条：不要改阈值硬凑，回去补检索或换检索式（见 references/03-workflow.md）")
    print("\n  下一步：python verify.py %s" % pj)
    return 0 if items else 1


if __name__ == "__main__":
    sys.exit(main())
