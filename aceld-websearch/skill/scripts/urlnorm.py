#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""urlnorm.py —— 「可读链接」的守门员：规范化 + 域名分级 + 黑名单 + 原文回溯提示。

可读链接的定义（缺一不可）：
    1. http/https、能直接打开、不需要登录/付费/App；
    2. 是**原文**（不是转载、不是聚合页、不是短链跳转、不是快照）；
    3. 去掉跟踪参数后仍然指向同一篇内容；
    4. 由 WebFetch 实际抓到 >=2 段正文才最终算数（这一步不在本脚本，见 SKILL.md 阶段 ④）。

用法：
    python urlnorm.py "https://mp.weixin.qq.com/s/xxx?utm_source=foo" --profile tech --json
    python urlnorm.py --check-list candidates.json --profile tech
"""
import argparse
import json
import os
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.path.normpath(os.path.join(HERE, "..", "assets", "sources.json"))

# 纯跟踪参数：删掉不影响定位到同一篇内容。
# 注意：B站 ?p=、知乎 ?utm_psn=、微信 __biz/mid/sn/idx 等定位参数一律保留，只删确认为跟踪的。
TRACK_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "fbclid", "gclid", "gbraid", "wbraid", "msclkid", "igshid", "mkt_tok", "mc_cid", "mc_eid",
    "spm", "scm", "from_source", "share_token", "share_source", "ref_src", "ref", "referrer",
    "from", "source", "channel", "cid", "s", "_hsenc", "vero_id", "yclid", "si", "feature",
}
SHORTENERS = {"t.cn", "bit.ly", "dwz.cn", "s.id", "url.cn", "tinyurl.com", "goo.gl",
              "is.gd", "suo.im", "m.tb.cn", "v.douyin.com", "b23.tv", "x.cn"}
# 出现这些路径/参数特征，说明大概率不是原文或是中间页 → 必须回溯
NOT_ORIGINAL_HINTS = [
    (r"/amp/?$", "AMP 镜像页"),
    (r"(^|/)(redirect|jump|goto|link|url)(/|\?|$)", "跳转中间页"),
    (r"(^|/)s/", "短链/分享中间页"),
    (r"baidu\.com/link", "百度跳转页"),
    (r"(^|/)cache/|webcache|snapshot", "快照页"),
    (r"\?.*\b(from|share_?from)=(timeline|group|search|copy)", "分享来源页"),
]
# 微信公众号文章的**永久原文链接**格式就是 /s/<id>：它既不是短链，也不是分享中间页，
# 更没有别的官方 URL 可以回溯。之前的 (^|/)s/ 规则会把它误杀，导致官方一手原文被判 blocked。
# 这里只对 mp.weixin.qq.com 的 /s/<id> 形态豁免「短链/分享中间页」这一条 hint，
# 其余 hint（AMP / 跳转 / 快照 / 分享来源）照常生效，不放宽任何硬门槛。
WX_PERMALINK_HOST = "mp.weixin.qq.com"
WX_PERMALINK_PATH = re.compile(r"^/s/[A-Za-z0-9_-]{8,}$", re.I)


def load_cfg(path=SOURCES):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def domain_of(url):
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def match_domain(host, listed):
    """精确命中或子域命中：blog.cloudflare.com 命中 cloudflare.com。"""
    for d in listed:
        d = d.lower().lstrip(".")
        if host == d or host.endswith("." + d):
            return d
    return None


def normalize(url):
    """返回 (规范 URL, 改动说明列表)。保持 ASCII 引号与 UTF-8 安全。"""
    notes = []
    u = url.strip().replace(" ", "")
    if u.startswith("//"):
        u = "https:" + u
        notes.append("补 scheme")
    p = urlparse(u)
    if p.scheme not in ("http", "https"):
        return u, ["! 非 http(s) 链接，不可直接读"]
    # 统一小写域名；path/query 保持原样（大小写可能敏感）
    host = (p.hostname or "").lower()
    netloc = host
    if p.port and p.port not in (80, 443):
        netloc += ":%d" % p.port
    if netloc != p.netloc:
        notes.append("规范化 host")
    pairs = parse_qsl(p.query, keep_blank_values=True)
    kept = [(k, v) for k, v in pairs if k.lower() not in TRACK_PARAMS]
    if len(kept) != len(pairs):
        notes.append("去掉 %d 个跟踪参数" % (len(pairs) - len(kept)))
    path = p.path.rstrip("/") or "/"
    if path != p.path:
        notes.append("去尾部斜杠")
    out = urlunparse((p.scheme, netloc, path, "", urlencode(kept), ""))
    if p.fragment:
        notes.append("去 fragment（锚点不构成可读链接）")
    return out, notes


def inspect(url, cfg, profile="tech"):
    prof = cfg["profiles"].get(profile) or cfg["profiles"][cfg["default_profile"]]
    norm, notes = normalize(url)
    host = domain_of(norm)
    blocked = match_domain(host, prof.get("blocked_domains", []))
    short = match_domain(host, SHORTENERS)
    tier = "T3"
    matched = None
    for t in ("T1", "T2", "T3"):
        m = match_domain(host, prof["domains"].get(t, []))
        if m:
            tier, matched = t, m
            break
    if not matched:
        tier = "UNKNOWN"
    hints = [label for pat, label in NOT_ORIGINAL_HINTS
             if re.search(pat, norm, re.I)]
    # 微信 /s/<id> 是官方永久原文链接，只豁免「短链/分享中间页」这一个误判标签。
    if (host == WX_PERMALINK_HOST and WX_PERMALINK_PATH.match(urlparse(norm).path)):
        hints = [h for h in hints if h != "短链/分享中间页"]
    reasons = []
    if blocked:
        reasons.append("黑名单域名 %s（付费墙/聚合/短链）" % blocked)
    if short:
        reasons.append("短链 %s，必须展开后再判定" % short)
    if not host:
        reasons.append("解析不出域名")
    if hints:
        reasons.append("疑似非原文：%s" % "、".join(hints))
    return {
        "original": url,
        "canonical": norm,
        "domain": host,
        "tier": tier,
        "matched_domain": matched,
        "allow_t3": prof.get("allow_t3", False),
        "blocked": bool(reasons),
        "reasons": reasons,
        "notes": notes,
        "needs_original_lookup": bool(hints or short),
    }


def main():
    ap = argparse.ArgumentParser(description="URL 规范化 + 权威分层 + 可读性预检")
    ap.add_argument("url", nargs="?", help="待检查的链接")
    ap.add_argument("--profile", default="tech")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check-list", default="", help="candidates.json，批量看每条 url")
    a = ap.parse_args()
    cfg = load_cfg()

    if a.check_list:
        with open(a.check_list, encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("candidates", data if isinstance(data, list) else [])
        bad = 0
        for it in items:
            r = inspect(it.get("url", ""), cfg, a.profile)
            flag = "✗" if r["blocked"] else "✓"
            bad += bool(r["blocked"])
            print("%s [%s] %-28s %s" % (flag, r["tier"], r["domain"],
                                        (it.get("title") or "")[:40]))
            for x in r["reasons"]:
                print("      ! " + x)
        print("\n共 %d 条，%d 条需处理；域名分级只是起点，最终以页面核验为准。"
              % (len(items), bad))
        return 0

    if not a.url:
        ap.print_help()
        return 2
    r = inspect(a.url, cfg, a.profile)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print("规范链接：%s" % r["canonical"])
        print("域名：%s   层级：%s（命中 %s）" %
              (r["domain"], r["tier"], r["matched_domain"] or "无"))
        for n in r["notes"]:
            print("  · " + n)
        for x in r["reasons"]:
            print("  ! " + x)
        if not r["reasons"]:
            print("  ✓ 预检通过；仍需 WebFetch 抓到正文才算「可读」")
    return 0


if __name__ == "__main__":
    sys.exit(main())
