# -*- coding: utf-8 -*-
"""把本地 HTML 粘进微信公众号编辑器 → 等图片自动上传 → 保存为草稿。

设计前提（很重要）：
  · **零凭据**。脚本不读、不存任何 AppID / AppSecret / Cookie / 密码。
    登录态完全复用你已登录的那个 Chrome，token 每次从地址栏现抓。
  · **绝不点「发表」**。只点「保存为草稿」，把发布这一步留给人。

用法：
    # 1. 先用调试端口启动 Chrome 并登录 mp.weixin.qq.com（见 SKILL.md）
    python publish.py --html 公众号版.html --meta meta.json --img-dir ../文章配图
    python publish.py --html 公众号版.html --new      # 自动开一个新建图文页
    python publish.py --html 公众号版.html --dry-run  # 只算体积、检查图片，不动浏览器

前置：Chrome 以 --remote-debugging-port=9222 启动，且已登录公众号后台。
"""
import argparse
import base64
import io
import json
import os
import re
import sys

CDP_DEFAULT = "http://127.0.0.1:9222"
MAXW_DEFAULT = 1400

# 新版编辑器（2026-11 实测）
BODY_PM = "#ueditor_0 .ProseMirror"      # 正文（位于 .mock-iframe 内）
TITLE_PM = "#js_title_main .ProseMirror"  # 标题（textarea#title 是隐藏数据载体，h=0）
NEW_URL = ("https://mp.weixin.qq.com/cgi-bin/appmsg"
           "?t=media/appmsg_edit_v2&action=edit&isNew=1&type=77"
           "&token={tok}&lang=zh_CN")


def log(*a):
    print(*a, flush=True)


# ---------------- 图片 ----------------
def data_uri(path, maxw):
    from PIL import Image
    im = Image.open(path)
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    if im.width > maxw:
        im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    if im.mode == "RGBA":
        im.save(buf, format="PNG", optimize=True)
        mime = "image/png"
    else:
        im.save(buf, format="JPEG", quality=90, optimize=True)
        mime = "image/jpeg"
    return "data:%s;base64,%s" % (mime, base64.b64encode(buf.getvalue()).decode())


def build_html(html_path, img_dir, img_base, maxw):
    html = open(html_path, encoding="utf-8").read()
    pat = re.compile(r'src="' + re.escape(img_base) + r'([^"]+)"')
    names = sorted(set(pat.findall(html)))
    log("IMG_REFS", len(names))
    cache, missing = {}, []
    html_dir = os.path.dirname(html_path)
    for n in names:
        fp = os.path.join(img_dir, n.replace("/", os.sep))
        if not os.path.isfile(fp):
            # 装饰图（分隔线、顶部装饰带）通常和 html 放一起，不在配图目录
            fp = os.path.join(html_dir, os.path.basename(n))
        if not os.path.isfile(fp):
            missing.append(n)
            continue
        cache[n] = data_uri(fp, maxw)
    if missing:
        log("!! 缺图", missing)
    total = sum(len(v) for v in cache.values())
    log("B64_TOTAL_MB", round(total / 1024 / 1024, 2))
    return pat.sub(lambda m: 'src="%s"' % cache.get(m.group(1), m.group(0)), html)


# ---------------- 浏览器 ----------------
def get_token(ctx):
    for x in ctx.pages:
        try:
            m = re.search(r"token=(\d+)", x.url)
        except Exception:
            continue
        if m:
            return m.group(1)
    return None


def find_editor(ctx):
    best = None
    for x in ctx.pages:
        try:
            u = x.url
        except Exception:
            continue
        if "appmsg_edit" in u:
            if "appmsgid=" in u:
                return x
            best = best or x
    return best


def close_dialogs(pg):
    """残留的模态框会盖住编辑器，下一次粘贴就会静默失败。"""
    for _ in range(4):
        r = pg.evaluate("""()=>{
            var d=[].slice.call(document.querySelectorAll('.weui-desktop-dialog, .weui-dialog'))
                     .filter(function(x){return x.offsetParent;});
            if(!d.length) return 'none';
            var btns=[].slice.call(d[0].querySelectorAll('button, a')).filter(function(x){return x.offsetParent;});
            var cancel=btns.find(function(x){var t=(x.textContent||'').trim();
                return t==='取消'||t==='关闭'||t==='我知道了';});
            if(cancel){cancel.click(); return 'cancel';}
            var cl=d[0].querySelector('.weui-desktop-dialog__close, .weui-dialog__close, i[class*="close"]');
            if(cl){cl.click(); return 'x';}
            return 'stuck';}""")
        log("CLOSE_DLG", r)
        if r == "none":
            return
        pg.wait_for_timeout(800)


def body_state(pg):
    return pg.evaluate("""()=>{
        var pm=document.querySelector('%s');
        if(!pm) return {pm:false};
        var imgs=[].slice.call(pm.querySelectorAll('img'));
        return {pm:true,
                textLen:(pm.innerText||'').trim().length,
                imgs:imgs.length,
                h2:pm.querySelectorAll('h2').length,
                mmbiz:imgs.filter(function(x){return (x.src||'').indexOf('mmbiz')>=0;}).length,
                data:imgs.filter(function(x){return (x.src||'').indexOf('data:')===0;}).length};}"""
                            % BODY_PM)


def set_title(pg, title):
    """标题是 ProseMirror，textarea#title 只是隐藏的数据载体（高度 0）。
    坑：点中心点会被 .title-editor-overlay 吃掉焦点，要点靠左的位置。
    三路兜底：真实输入 → execCommand → 直接给 textarea 赋值派事件。"""
    box = pg.evaluate("""()=>{
        var pm=document.querySelector('%s');
        if(!pm) return null;
        pm.scrollIntoView({block:'center'});
        var r=pm.getBoundingClientRect();
        return {x:Math.round(r.x+30), y:Math.round(r.y+r.height/2)};}""" % TITLE_PM)
    if box:
        pg.mouse.click(box["x"], box["y"])
        pg.wait_for_timeout(500)
        pg.keyboard.press("Control+A")
        pg.wait_for_timeout(120)
        pg.keyboard.insert_text(title)
        pg.wait_for_timeout(700)
        if read_title(pg)["ta"]:
            return read_title(pg)

    pg.evaluate("""(t)=>{
        var pm=document.querySelector('%s');
        if(!pm) return;
        pm.focus();
        var sel=window.getSelection(), r=document.createRange();
        r.selectNodeContents(pm); sel.removeAllRanges(); sel.addRange(r);
        document.execCommand('insertText', false, t);}""" % TITLE_PM, title)
    pg.wait_for_timeout(700)
    if read_title(pg)["ta"]:
        return read_title(pg)

    pg.evaluate("""(t)=>{
        var el=document.querySelector('#title'); if(!el) return;
        el.value=t;
        el.dispatchEvent(new Event('input',{bubbles:true}));
        el.dispatchEvent(new Event('change',{bubbles:true}));}""", title)
    pg.wait_for_timeout(700)
    return read_title(pg)


def read_title(pg):
    return pg.evaluate("""()=>{
        var t=document.querySelector('#title');
        var pm=document.querySelector('%s');
        return {ta:t?t.value:'', pm:pm?(pm.innerText||'').trim():''};}""" % TITLE_PM)


def save_draft(pg):
    sb = pg.evaluate("""()=>{
        var els=[].slice.call(document.querySelectorAll('button, span, a'));
        for(const e of els){ if(e.offsetParent && (e.textContent||'').trim()==='保存为草稿'){
            var r=e.getBoundingClientRect();
            return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)}; } }
        return null;}""")
    log("SAVE_BTN", json.dumps(sb))
    if not sb:
        return False
    pg.mouse.click(sb["x"], sb["y"])
    pg.wait_for_timeout(2500)
    for _ in range(4):
        cf = pg.evaluate("""()=>{
            var b=[].slice.call(document.querySelectorAll('button, a')).find(function(x){
                return x.offsetParent && ((x.textContent||'').includes('确定')
                       || (x.textContent||'').includes('继续保存')) && !x.disabled;});
            if(!b) return null; var r=b.getBoundingClientRect();
            return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2),
                    t:(b.textContent||'').trim()};}""")
        if not cf:
            break
        log("CONFIRM", json.dumps(cf, ensure_ascii=False))
        pg.mouse.click(cf["x"], cf["y"])
        pg.wait_for_timeout(1800)
    pg.wait_for_timeout(3000)
    return True


# ---------------- 主流程 ----------------
def main():
    ap = argparse.ArgumentParser(description="把 HTML 粘进公众号编辑器并存为草稿（绝不发表）")
    ap.add_argument("--html", required=True)
    ap.add_argument("--meta", default=None, help="含 title 的 meta.json")
    ap.add_argument("--title", default=None, help="直接指定标题，优先于 meta")
    ap.add_argument("--img-dir", default=None, help="图片根目录，默认 html 所在目录")
    ap.add_argument("--img-base", default="http://127.0.0.1:8792/")
    ap.add_argument("--cdp", default=CDP_DEFAULT)
    ap.add_argument("--maxw", type=int, default=MAXW_DEFAULT)
    ap.add_argument("--new", action="store_true", help="自动打开一个新建图文页")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    html_path = os.path.abspath(a.html)
    img_dir = os.path.abspath(a.img_dir or os.path.dirname(html_path))
    title = a.title
    if not title and a.meta:
        title = json.load(open(a.meta, encoding="utf-8")).get("title", "")
    if not title:
        log("!! 没有标题：用 --title 或 --meta 指定")
        return 1

    html = build_html(html_path, img_dir, a.img_base, a.maxw)
    expected = html.count("<img ")
    log("FINAL_HTML_MB", round(len(html) / 1024 / 1024, 2), "EXPECTED_IMGS", expected)
    log("TITLE", title)
    if a.dry_run:
        log("DRY_RUN ok")
        return 0

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(a.cdp)
        ctx = b.contexts[0]
        try:
            ctx.grant_permissions(["clipboard-read", "clipboard-write"],
                                  origin="https://mp.weixin.qq.com")
        except Exception as e:
            log("GRANT", e)

        tok = get_token(ctx)
        log("TOKEN", tok)
        if not tok:
            log("!! 没登录：请在调试浏览器里登录 mp.weixin.qq.com")
            b.close()
            return 2

        ed = find_editor(ctx)
        if ed is None and a.new:
            ed = ctx.new_page()
            ed.goto(NEW_URL.format(tok=tok), wait_until="domcontentloaded")
            log("OPENED", ed.url[:140])
        if ed is None:
            log("!! 没有编辑页：加 --new，或手动打开「新建图文」")
            b.close()
            return 2
        log("EDITOR", ed.url[:140])

        is_draft = "appmsgid=" in ed.url
        close_dialogs(ed)
        if is_draft:
            # 老草稿 reload 一次，清掉可能残留的模态框状态
            ed.reload(wait_until="domcontentloaded")
        st = None
        for i in range(45):
            try:
                st = body_state(ed)
            except Exception:
                st = {"pm": False}
            if st.get("pm") and (not is_draft or st.get("textLen", 0) > 200):
                break
            ed.wait_for_timeout(1200)
        log("EDITOR_READY", json.dumps(st, ensure_ascii=False))
        if not st or not st.get("pm"):
            log("!! 编辑器没就绪")
            b.close()
            return 3
        close_dialogs(ed)

        # 全选替换 + 剪贴板写入 + 粘贴
        ed.evaluate("""()=>{var pm=document.querySelector('%s');if(pm)pm.focus();}""" % BODY_PM)
        ed.wait_for_timeout(300)
        ed.keyboard.press("Control+A")
        ed.wait_for_timeout(350)
        ed.evaluate("""async (a)=>{
            const item=new ClipboardItem({'text/html':new Blob([a.html],{type:'text/html'}),
                                          'text/plain':new Blob([a.plain],{type:'text/plain'})});
            await navigator.clipboard.write([item]); return 'OK';}""",
                    {"html": html, "plain": re.sub(r"<[^>]+>", "", html)[:300000]})
        ed.keyboard.press("Control+V")
        ed.wait_for_timeout(4000)

        chk = body_state(ed)
        log("AFTER_PASTE", json.dumps(chk, ensure_ascii=False))
        if chk.get("imgs", 0) == 0:
            log("PASTE_RETRY")
            ed.evaluate("""()=>{var pm=document.querySelector('%s');if(pm)pm.focus();}""" % BODY_PM)
            ed.wait_for_timeout(400)
            ed.keyboard.press("Control+A")
            ed.wait_for_timeout(300)
            ed.keyboard.press("Control+V")
            ed.wait_for_timeout(4000)
            chk = body_state(ed)
            log("AFTER_PASTE_2", json.dumps(chk, ensure_ascii=False))

        if chk.get("imgs", 0) == 0:
            # 关键保护：粘贴失败就退出，绝不用空文覆盖已有草稿
            log("PASTE_FAILED_ABORT（不保存，避免覆盖草稿）")
            try:
                ed.screenshot(path=os.path.join(os.path.dirname(html_path), "paste_failed.png"))
            except Exception:
                pass
            b.close()
            return 4

        log("TITLE_SET", json.dumps(set_title(ed, title), ensure_ascii=False))

        # 等 base64 → mmbiz（微信在粘贴后异步上传）
        ok, last = False, None
        for i in range(90):
            st2 = body_state(ed)
            if st2 != last:
                log("IMG_POLL", i, json.dumps(st2, ensure_ascii=False))
                last = st2
            if st2.get("mmbiz", 0) >= expected and st2.get("data", 0) == 0:
                ok = True
                log("IMGS_OK", json.dumps(st2, ensure_ascii=False))
                break
            ed.wait_for_timeout(2000)
        if not ok:
            log("IMG_TIMEOUT", json.dumps(last, ensure_ascii=False))

        save_draft(ed)
        fin = ed.evaluate("""()=>{
            var t=document.body.innerText||'';
            var pm=document.querySelector('%s');
            var ti=document.querySelector('#title');
            return {url:location.href.slice(0,150),
                    title:ti?ti.value:'',
                    mmbiz:pm?pm.querySelectorAll('img[src*="mmbiz"]').length:0,
                    data:pm?pm.querySelectorAll('img[src^="data:"]').length:0,
                    h2:pm?pm.querySelectorAll('h2').length:0,
                    saved:t.indexOf('保存成功')>=0||t.indexOf('已保存')>=0,
                    failed:t.indexOf('保存失败')>=0};}""" % BODY_PM)
        log("FINAL", json.dumps(fin, ensure_ascii=False))
        try:
            ed.screenshot(path=os.path.join(os.path.dirname(html_path), "after_save.png"))
        except Exception:
            pass
        b.close()
        return 0 if fin.get("saved") and not fin.get("failed") else 5


if __name__ == "__main__":
    sys.exit(main())
