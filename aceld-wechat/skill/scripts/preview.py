# -*- coding: utf-8 -*-
"""
把 md2wechat.py 产出的 HTML 渲染成手机宽度效果图。

两个用途：
  1) 发布前肉眼检查排版 —— 不用真的粘进微信，先看有没有溢出、断行、图片糊掉
  2) 给 README / 文章归档出效果图 —— 截图里只有文章内容，没有账号、后台、token

不联网、不连 CDP、不碰编辑器：只把占位图片 URL 换成本地文件的 data URI，
再用一个独立的 headless Chrome 按公众号手机宽度渲染。

    python scripts/preview.py \
        --html work/公众号版.html \
        --img-dir 文章配图 \
        --out-dir docs/screenshots

依赖：playwright、pillow（与 publish.py 相同）。
"""
import argparse
import base64
import io
import os
import re
import sys

DEFAULT_IMG_BASE = "http://127.0.0.1:8792/"

# 微信正文里图片会被压到容器宽度，渲染时必须模拟，否则 940px 的架构图会撑破视口
PAGE_CSS = (
    "html,body{margin:0;padding:0;background:#ffffff;}"
    "img{max-width:100% !important;height:auto !important;}"
    "*{box-sizing:border-box;}"
)


def log(*a):
    print(*a, flush=True)


def data_uri(path, maxw):
    from PIL import Image
    im = Image.open(path)
    if im.width > maxw:
        im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    if im.mode in ("RGBA", "LA", "P") and "transparency" in im.info:
        im.save(buf, "PNG", optimize=True)
        mime = "image/png"
    else:
        im.convert("RGB").save(buf, "JPEG", quality=90, optimize=True)
        mime = "image/jpeg"
    return "data:%s;base64,%s" % (mime, base64.b64encode(buf.getvalue()).decode("ascii"))


def find_img(name, dirs):
    rel = name.replace("/", os.sep).replace("\\", os.sep)
    for d in dirs:
        if not d:
            continue
        p = os.path.join(d, rel)
        if os.path.isfile(p):
            return p
    return None


def inline_images(html, img_dirs, img_base, maxw):
    """占位 URL → 本地图片 data URI，同时给 img 打上 data-shot-name 便于定位锚点。"""
    pat = re.compile(r'src="' + re.escape(img_base) + r'([^"]+)"')
    names = sorted(set(pat.findall(html)))
    cache, missing = {}, []
    for n in names:
        fp = find_img(n, img_dirs)
        if not fp:
            missing.append(n)
            continue
        cache[n] = data_uri(fp, maxw)
    if missing:
        log("MISSING_IMG", len(missing), missing[:8])
        log("提示：用 --img-dir 指定图片根目录；装饰图会在 HTML 所在目录里再找一次")
        sys.exit(2)

    def repl(m):
        n = m.group(1)
        return 'src="%s" data-shot-name="%s"' % (cache[n], n)

    return pat.sub(repl, html), len(names)


def wrap(html):
    return ('<!doctype html><html><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<style>' + PAGE_CSS + '</style></head><body>' + html + '</body></html>')


def pick_shots(info, page_h, height):
    """挑三段最有代表性的：开头 / 配图+图注 / 代码块+上下文。

    起点对齐到「块级元素的顶部」，不要固定减一个偏移 —— 否则上边缘会切在
    表格单元格或半行文字中间，截图看着像坏掉了。
    """
    figs = [e for e in info["imgs"]
            if "divider" not in e["name"] and "/fig" in "/" + e["name"]]
    tables = [e["y"] for e in info["tables"]]
    pres = info["pres"]

    def clamp(y):
        return max(0, min(int(y), max(0, page_h - height)))

    # 开头：顶部装饰带 + 封面卡 + 导语 + 第一个章节卡
    plans = [("01-header", clamp(0))]

    # 中段：第一张正文配图所在段落的顶部（跳过封面附近的图）
    anchor2 = None
    for e in figs:
        if e["block_y"] > height * 0.8:
            anchor2 = e["block_y"]
            break
    if anchor2 is None and tables:
        anchor2 = tables[0]
    if anchor2 is None and figs:
        anchor2 = figs[0]["block_y"]
    plans.append(("02-figure", clamp(anchor2 - 24) if anchor2 else clamp(height)))

    # 后段：代码块前一段的顶部，让代码块带一句上下文
    anchor3 = pres[0]["block_y"] if pres else (tables[-1] if tables else page_h - height)
    plans.append(("03-code", clamp(anchor3 - 24)))

    # 三段别撞在同一处
    used = []
    for name, y in plans:
        if any(abs(y - u) < height * 0.5 for u in used):
            y = clamp(y + height * 0.8)
        used.append(y)
        yield name, y


def main():
    ap = argparse.ArgumentParser(description="公众号文章手机端效果图 / 发布前预览")
    ap.add_argument("--html", required=True, help="md2wechat.py 产出的 HTML")
    ap.add_argument("--img-dir", default=None, help="图片根目录（对应 --img-base 之后的相对路径）")
    ap.add_argument("--img-base", default=DEFAULT_IMG_BASE)
    ap.add_argument("--out-dir", default="preview", help="输出目录")
    ap.add_argument("--width", type=int, default=414, help="手机宽度 CSS px，默认 414")
    ap.add_argument("--height", type=int, default=760, help="每张截图高度 CSS px，默认 760")
    ap.add_argument("--scale", type=int, default=2, help="设备像素比，默认 2")
    ap.add_argument("--maxw", type=int, default=1000, help="内嵌图片最大宽度，默认 1000")
    ap.add_argument("--quality", type=int, default=86, help="输出 JPEG 质量")
    ap.add_argument("--channel", default="chrome", help="Chromium 通道，默认复用系统 Chrome")
    a = ap.parse_args()

    html_path = os.path.abspath(a.html)
    if not os.path.isfile(html_path):
        log("HTML_NOT_FOUND", html_path)
        sys.exit(2)
    html = open(html_path, encoding="utf-8").read()

    here = os.path.dirname(html_path)
    img_dirs = [a.img_dir, here, os.path.join(a.img_dir or here, ".."), os.path.dirname(here)]
    html, n_img = inline_images(html, img_dirs, a.img_base, a.maxw)
    log("IMG_INLINED", n_img)

    os.makedirs(a.out_dir, exist_ok=True)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("需要 playwright：pip install playwright")
        sys.exit(2)

    from PIL import Image
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel=a.channel, headless=True)
        except Exception as e:
            log("CHROME_LAUNCH_FAILED", str(e)[:200])
            log("可试 --channel msedge，或改用已安装 chromium")
            sys.exit(2)
        page = b.new_page(viewport={"width": a.width, "height": a.height},
                          device_scale_factor=a.scale)
        page.set_content(wrap(html), wait_until="load")
        page.wait_for_timeout(400)
        info = page.evaluate("""() => {
            const box = el => { const r = el.getBoundingClientRect();
                                return {y: Math.round(r.top + window.scrollY), h: Math.round(r.height)}; };
            // 图片通常包在 <p> 里；用这个 p 的顶边当「块边界」，比 img 顶边更好对齐
            const imgs = [...document.querySelectorAll('img')].map(el => {
                const b = box(el);
                b.name = el.getAttribute('data-shot-name') || '';
                b.block_y = box(el.parentElement || el).y;
                return b; });
            const pres = [...document.querySelectorAll('pre')].map(el => {
                const b = box(el);
                const prev = el.previousElementSibling;
                b.block_y = prev ? box(prev).y : b.y;   // 带上代码块前面那句话
                return b; });
            // 块级元素的「底边」候选：截图终点吸附到这里，就不会切在半行文字中间
            const ends = [...new Set(
                [...document.querySelectorAll('p,table,pre,section,blockquote,h1,h2,h3,ul,ol')]
                    .map(box).filter(b => b.h > 0 && b.h < %d)
                    .map(b => b.y + b.h))].sort((a, b) => a - b);
            return {
                page_h: document.documentElement.scrollHeight,
                scroll_w: document.documentElement.scrollWidth,
                imgs, pres, ends,
                tables: [...document.querySelectorAll('table')].map(box)
            };
        }""" % a.height)
        page_h, scroll_w = info["page_h"], info["scroll_w"]
        log("PAGE", "%dx%d" % (scroll_w, page_h),
            "OVERFLOW_X" if scroll_w > a.width + 2 else "NO_OVERFLOW")

        # clip 的坐标是相对视口的；不把视口拉到整页高，第二、三张就会落到视口外
        page.set_viewport_size({"width": a.width, "height": max(page_h + 20, a.height)})
        page.wait_for_timeout(150)

        full_h = a.height * a.scale
        ends = info["ends"]
        for name, y in pick_shots(info, page_h, a.height):
            # 终点向上吸附到最近的块底边，宁可少截一点也不切半行字
            want = y + a.height
            cand = [e for e in ends if y + a.height * 0.5 < e <= want]
            h_css = (max(cand) - y) if cand else min(a.height, page_h - y)
            raw = page.screenshot(clip={"x": 0, "y": y, "width": a.width, "height": h_css})
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            if im.height < full_h:      # 补白到统一高度，README 里并排才齐
                from collections import Counter
                row = max(0, im.height - 2)
                samples = [im.getpixel((int(im.width * f), row))
                           for f in (0.1, 0.3, 0.5, 0.7, 0.9)]
                bg = Counter(samples).most_common(1)[0][0]   # 取背景色，别取到文字
                canvas = Image.new("RGB", (im.width, full_h), bg)
                canvas.paste(im, (0, 0))
                im = canvas
            out = os.path.join(a.out_dir, name + ".jpg")
            im.save(out, "JPEG", quality=a.quality, optimize=True, progressive=True)
            log("SHOT", out, "%dx%d" % im.size, "%d KB" % (os.path.getsize(out) // 1024))
        b.close()
    log("DONE")


if __name__ == "__main__":
    main()
