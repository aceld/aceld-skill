#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""register_source.py —— 把「这个技能从哪来」记到 ~/.workbuddy-ai/skills/.findskill-sources.json

用法：
    python register_source.py <技能名> <owner/repo>

作用：preflight.py --check-updates 靠这份登记去查上游有没有新提交。
install.sh / install.ps1 装完会自动调一次，一般不用手动跑。
"""
import json
import os
import sys
import time

P = os.path.expanduser("~/.workbuddy-ai/skills/.findskill-sources.json")


def main():
    if len(sys.argv) < 3:
        print("用法：python register_source.py <技能名> <owner/repo>", file=sys.stderr)
        return 2
    name, src = sys.argv[1].strip(), sys.argv[2].strip().strip("/")
    if "/" not in src:
        print("来源要写成 owner/repo，收到：%r" % src, file=sys.stderr)
        return 2
    d = {}
    if os.path.exists(P):
        try:
            d = json.load(open(P, encoding="utf-8"))
        except Exception:
            d = {}
    d[name] = {"source": src, "checked": time.strftime("%Y-%m-%d")}
    os.makedirs(os.path.dirname(P), exist_ok=True)
    with open(P, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print("==> 已登记来源：%s ← %s" % (name, src))
    print("    查上游更新：python preflight.py --check-updates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
