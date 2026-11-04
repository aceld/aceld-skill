# -*- coding: utf-8 -*-
"""发布前自检：端口 → 登录 → 编辑页 → 选择器 → 按钮。

微信后台改版时选择器会失效。先跑这个，比在 publish.py 里看一堆 WAIT 日志快。

用法：
    python doctor.py
    python doctor.py --cdp http://127.0.0.1:9222
"""
import argparse
import json
import re
import sys

BODY_PM = "#ueditor_0 .ProseMirror"
TITLE_PM = "#js_title_main .ProseMirror"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cdp", default="http://127.0.0.1:9222")
    a = ap.parse_args()

    from playwright.sync_api import sync_playwright

    problems = []
    with sync_playwright() as p:
        try:
            b = p.chromium.connect_over_cdp(a.cdp)
        except Exception as e:
            print("[X] 连不上调试端口 %s" % a.cdp)
            print("    %s" % str(e).split("\n")[0][:120])
            print("    启动方式见 SKILL.md「第一次使用」")
            return 1
        print("[OK] 调试端口已连通")

        ctx = b.contexts[0]
        tabs = []
        for pg in ctx.pages:
            try:
                tabs.append(pg.url)
            except Exception:
                pass
        print("[..] 标签页 %d 个" % len(tabs))
        for t in tabs[:8]:
            print("     " + t[:110])

        tok = None
        for t in tabs:
            m = re.search(r"token=(\d+)", t)
            if m:
                tok = m.group(1)
                break
        if not tok:
            print("[X] 未登录（地址栏没有 token）→ 在浏览器里扫码登录")
            b.close()
            return 2
        print("[OK] 已登录 token=%s" % tok)

        ed = None
        for pg in ctx.pages:
            try:
                if "appmsg_edit" in pg.url:
                    ed = pg
                    break
            except Exception:
                continue
        if ed is None:
            print("[X] 没有编辑页 → 加 --new 让 publish.py 自己开，或手动打开「新建图文」")
            b.close()
            return 3
        print("[OK] 编辑页 %s" % ed.url[:110])

        st = ed.evaluate("""(sel)=>{
            var pm=document.querySelector(sel.body);
            var tp=document.querySelector(sel.title);
            var ta=document.querySelector('#title');
            var btn=[].slice.call(document.querySelectorAll('button, span, a'))
                .filter(function(e){return e.offsetParent && (e.textContent||'').trim()==='保存为草稿';});
            return {body:!!pm, title:!!tp, ta:!!ta, saveBtn:btn.length,
                    pmAll:document.querySelectorAll('.ProseMirror').length,
                    gradientInDoc:(document.body.innerHTML.match(/linear-gradient/g)||[]).length};}""",
                            {"body": BODY_PM, "title": TITLE_PM})
        print("[..] 选择器探测 %s" % json.dumps(st, ensure_ascii=False))
        if not st["body"]:
            problems.append("正文选择器失效：%s" % BODY_PM)
        if not st["title"]:
            problems.append("标题选择器失效：%s（微信可能又改版了，重新找 ProseMirror）" % TITLE_PM)
        if not st["ta"]:
            problems.append("找不到 #title 隐藏域，保存后标题可能丢")
        if st["saveBtn"] == 0:
            problems.append("找不到「保存为草稿」按钮")

        try:
            ed.screenshot(path="doctor.png")
            print("[OK] 截图 doctor.png")
        except Exception:
            pass
        b.close()

    if problems:
        print("\n发现 %d 个问题：" % len(problems))
        for x in problems:
            print("  - " + x)
        return 4
    print("\n[OK] 一切正常，可以跑 publish.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
