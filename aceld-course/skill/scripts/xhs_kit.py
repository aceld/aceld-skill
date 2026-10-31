# -*- coding: utf-8 -*-
"""小红书图卡组件（1080×1440）

用法：
    from xhs_kit import page, li, card, write, render_all

    pages = [
        page("— 01 · 封面", "大模型不是笨<br>是**记不住**你", "<p>…</p>",
             "看完你就知道它为什么忘事", 1, "#22d3ee"),
        page("— 02 · 第 0 代", "窗口就是全部", li(1, "…", "…"),
             "…", 2, "#a78bfa"),
    ]
    write("dist/xhs", pages, "xhs")
    render_all("dist/xhs", "dist/xhs_png", "xhs", len(pages))
"""
import os

W, H = 1080, 1440
PAD_X, PAD_TOP, PAD_BOT = 88, 96, 96

CSS = """
*{margin:0;padding:0;box-sizing:border-box;}
body{width:%(W)dpx;height:%(H)dpx;overflow:hidden;
  font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#0b1020;}
.page{position:relative;width:%(W)dpx;height:%(H)dpx;padding:%(PT)dpx %(PX)dpx %(PB)dpx;
  display:flex;flex-direction:column;justify-content:center;
  background:radial-gradient(900px 700px at 80%% 8%%,rgba(34,211,238,.13),transparent 62%%),
             radial-gradient(800px 700px at 12%% 92%%,rgba(167,139,250,.13),transparent 62%%),
             linear-gradient(158deg,#070b16,#0d1428 50%%,#141d38);}
.kick{font-size:26px;font-weight:700;letter-spacing:3px;color:var(--ac);display:flex;
  align-items:center;gap:14px;}
.kick::before{content:"";width:26px;height:3px;background:var(--ac);border-radius:2px;}
.big{margin-top:34px;font-size:88px;font-weight:800;line-height:1.2;color:#fff;letter-spacing:1px;}
.big em{font-style:normal;color:var(--ac);}
.body{margin-top:44px;font-size:34px;line-height:1.72;color:#c8d4ea;}
.body p{margin:14px 0;}
.body strong{color:#fff;font-weight:800;}
.one{margin-top:34px;padding-left:18px;border-left:6px solid var(--ac);
  font-size:31px;line-height:1.6;color:#9fb0cc;}
.card{margin-top:20px;padding:26px 30px;border-radius:18px;
  background:rgba(140,175,255,.07);border:1px solid rgba(140,170,255,.18);}
.card .lb{font-size:26px;color:#8ea3cc;letter-spacing:1px;}
.card .v{margin-top:8px;font-size:52px;font-weight:800;color:#fff;}
.card .n{margin-top:6px;font-size:26px;color:#8ea3cc;}
.li{display:flex;gap:20px;margin-top:26px;}
.li .no{font-size:30px;font-weight:800;color:var(--ac);min-width:56px;}
.li .tx{font-size:36px;font-weight:700;color:#e2e8f0;line-height:1.45;}
.li .sb{margin-top:6px;font-size:26px;color:#8ea3cc;font-weight:400;}
.foot{position:absolute;left:%(PX)dpx;right:%(PX)dpx;bottom:52px;display:flex;
  justify-content:space-between;font-size:24px;color:#5f7093;letter-spacing:1px;}
""" % {"W": W, "H": H, "PT": PAD_TOP, "PB": PAD_BOT, "PX": PAD_X}

TPL = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}</style></head><body>
<div class="page" style="--ac:{c}">
{kick}
<div class="big">{big}</div>
<div class="body">{body}</div>
<div class="one">{one}</div>
<div class="foot"><span>{author}</span><span>{n:02d} / {total:02d}</span></div>
</div></body></html>"""


def page(kick, big, body="", one="", n=1, c="#22d3ee", total=10, author="", kick_label=None):
    """一页图卡。big / body 里的 **文字** 会被染成 accent 色（body 用 strong 标签亦可）"""
    big = big.replace("**", "\x00")
    out, gold = [], False
    for part in big.split("\x00"):
        out.append("<em>%s</em>" % part if gold else part)
        gold = not gold
    return TPL.format(
        css=CSS,
        c=c,
        kick='<div class="kick">%s</div>' % (kick_label or kick),
        big="".join(out),
        body=body,
        one=one,
        author=author,
        n=n,
        total=total,
    )


def li(no, text, sub=""):
    return ('<div class="li"><div class="no">%02d</div><div>'
            '<div class="tx">%s</div>%s</div></div>'
            % (no, text, '<div class="sb">%s</div>' % sub if sub else ""))


def card(label, value, note="", color=""):
    return ('<div class="card"><div class="lb">%s</div>'
            '<div class="v" style="color:%s">%s</div>'
            '<div class="n">%s</div></div>'
            % (label, color or "inherit", value, note))


def write(outdir, pages, prefix="xhs"):
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for i, html in enumerate(pages, 1):
        p = os.path.join(outdir, "%s_%02d.html" % (prefix, i))
        open(p, "w", encoding="utf-8").write(html)
        paths.append(p)
    print("写出 %d 个 HTML → %s" % (len(paths), outdir))
    return paths


def render_all(html_dir, png_dir, prefix="xhs", count=10, channel="chrome", scale=2):
    """批量截图：viewport 1080×1440 + device_scale_factor=2 → 缩回 1080×1440"""
    from playwright.sync_api import sync_playwright
    from PIL import Image

    os.makedirs(png_dir, exist_ok=True)
    html_dir = os.path.abspath(html_dir)
    png_dir = os.path.abspath(png_dir)
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel=channel)
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=scale)
        for i in range(1, count + 1):
            src = os.path.join(html_dir, "%s_%02d.html" % (prefix, i))
            if not os.path.exists(src):
                continue
            pg.goto("file:///" + src.replace("\\", "/"))
            pg.wait_for_timeout(500)
            raw = os.path.join(png_dir, "_raw_%02d.png" % i)
            pg.screenshot(path=raw)
            dst = os.path.join(png_dir, "%s_%02d.png" % (prefix, i))
            Image.open(raw).convert("RGB").resize((W, H), Image.LANCZOS).save(dst, quality=92)
            os.remove(raw)
            print("OK", dst)
        b.close()
