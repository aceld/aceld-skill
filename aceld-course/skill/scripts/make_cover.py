# -*- coding: utf-8 -*-
"""封面生成：横版 1146×717（B站）+ 竖版 1080×1920（抖音/视频号）

用法示例：
  python scripts/make_cover.py \
    --no "第一课 · 入门篇" \
    --title "不会写代码，<br/>也能做**AI 应用**" \
    --hook "30 分钟，从**聊天框**到真正的 Agent" \
    --sub  "装环境 · 填 API Key · 说人话 —— 剩下的它自己写、自己改" \
    --tags "0 行代码|4 毛钱成本|全程本地|一台电脑就够" \
    --rows "第 1 步 · 装环境：一个安装包;第 2 步 · 填 Key：粘贴一次;第 3 步 · 说需求：用人话讲" \
    --payoff "会用工具的才叫「Agent」<br/>只会聊天的叫「**聊天框**」" \
    --out 第一课

约定：
  - 文案里用 **文字** 标记金色强调
  - 标题用 <br/> 或 \n 换行，最多两行，第二行不超过 10 个汉字
  - 竖版内容会自动收在整图 ~78% 高度内（避开 App 底部 UI）
"""
import os
import sys
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from config import cfg                          # noqa: E402


def md(s):
    """**文字** → 金色 span（标题 / 列表 / 点题框通用）"""
    out, gold = [], False
    for part in (s or "").split("**"):
        out.append('<span class="y">%s</span>' % part if gold else part)
        gold = not gold
    return "".join(out)


def em(s):
    """hook 里的 **文字** → 金色 em"""
    out, gold = [], False
    for part in (s or "").split("**"):
        out.append("<em>%s</em>" % part if gold else part)
        gold = not gold
    return "".join(out)


BASE_CSS = """
  *{margin:0;padding:0;box-sizing:border-box;}
  body{overflow:hidden;font-family:"Microsoft YaHei","PingFang SC",sans-serif;
       -webkit-font-smoothing:antialiased;}
  .grid{position:absolute;inset:0;opacity:.30;
    background-image:linear-gradient(rgba(120,160,220,.13) 1px,transparent 1px),
                     linear-gradient(90deg,rgba(120,160,220,.13) 1px,transparent 1px);
    background-size:64px 64px;}
  .badge{font-size:22px;font-weight:700;color:#7dd3fc;letter-spacing:2px;
    border:2px solid rgba(125,211,252,.55);border-radius:999px;padding:6px 20px;
    background:rgba(14,165,183,.12);}
  .no{font-size:22px;font-weight:700;color:#fbbf24;letter-spacing:1px;}
  h1{font-weight:900;letter-spacing:2px;color:#fff;text-shadow:0 6px 30px rgba(34,211,238,.32);}
  h1 .y{color:#fbbf24;}
  .hook{font-weight:800;color:#e8eeff;letter-spacing:1px;}
  .hook em{font-style:normal;color:#fbbf24;}
  .tag{font-weight:800;color:#04121c;background:#22d3ee;border-radius:12px;letter-spacing:1px;}
  .tag.g{background:#fbbf24;}
  .tag.v{background:#a78bfa;color:#0b0620;}
  .tag.o{background:transparent;color:#cbd5e1;border:2px solid rgba(203,213,225,.5);}
"""

BG_BILI = """
      radial-gradient(900px 500px at 12% 8%, rgba(34,211,238,.20), transparent 62%),
      radial-gradient(820px 520px at 92% 96%, rgba(167,139,250,.24), transparent 62%),
      radial-gradient(700px 420px at 78% 12%, rgba(251,191,36,.16), transparent 60%),
      linear-gradient(140deg,#070b16 0%,#0d1428 48%,#141d38 100%)"""

BG_VERT = """
      radial-gradient(900px 620px at 14% 6%, rgba(34,211,238,.22), transparent 62%),
      radial-gradient(820px 620px at 90% 96%, rgba(167,139,250,.26), transparent 62%),
      radial-gradient(700px 480px at 80% 8%, rgba(251,191,36,.16), transparent 60%),
      linear-gradient(155deg,#070b16 0%,#0d1428 46%,#141d38 100%)"""


def tags_html(tags, vert=False):
    cls = ["", " g", " v", " o"]
    out = []
    for i, t in enumerate(tags):
        out.append('<span class="tag%s">%s</span>' % (cls[i % 4], t.strip()))
    return "\n      ".join(out)


def fill(tpl, **kw):
    """模板填充：用 {{key}} 占位，避开 CSS 里 % 和 {} 的冲突"""
    for k, v in kw.items():
        tpl = tpl.replace("{{%s}}" % k, v or "")
    return tpl


def bili_html(spec, series):
    tags = tags_html(spec["tags"])
    return fill("""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  body{width:1146px;height:717px;}
""" + BASE_CSS + """
  .wrap{position:relative;width:1146px;height:717px;background:""" + BG_BILI + """;}
  .inner{position:relative;z-index:3;height:100%;padding:48px 58px 42px;display:flex;flex-direction:column;}
  .top{display:flex;align-items:center;gap:14px;}
  h1{margin-top:30px;font-size:94px;line-height:1.08;}
  .hook{margin-top:26px;font-size:40px;}
  .sub{margin-top:16px;font-size:23px;font-weight:600;color:#94a3b8;letter-spacing:1px;}
  .tags{margin-top:auto;display:flex;gap:15px;align-items:center;}
  .tag{font-size:25px;padding:9px 21px;}
</style></head><body>
<div class="wrap">
  <div class="grid"></div>
  <div class="inner">
    <div class="top">
      <span class="badge">《{{series}}》系列</span>
      <span class="no">{{no}}</span>
    </div>
    <h1>{{title}}</h1>
    <div class="hook">{{hook}}</div>
    <div class="sub">{{sub}}</div>
    <div class="tags">
      {{tags}}
    </div>
  </div>
</div></body></html>""", series=series, no=spec["no"], title=md(spec["title"]),
        hook=em(spec["hook"]), sub=spec["sub"], tags=tags)


def vert_html(spec, series):
    tags = tags_html(spec["tags"])
    rows = ""
    if spec["rows"]:
        items = [r.strip() for r in spec["rows"].split(";") if r.strip()]
        rows = ('<div class="list">' +
                "".join('<div class="li">%s</div>' % md(r) for r in items) +
                "</div>")
    payoff = ""
    if spec["payoff"]:
        payoff = '<div class="payoff">%s</div>' % md(spec["payoff"])
    return fill("""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  body{width:1080px;height:1920px;}
""" + BASE_CSS + """
  .wrap{position:relative;width:1080px;height:1920px;background:""" + BG_VERT + """;}
  .grid{background-size:74px 74px;}
  .inner{position:relative;z-index:3;height:100%;padding:104px 76px 92px;display:flex;flex-direction:column;}
  .top{display:flex;align-items:center;gap:16px;}
  .badge{font-size:30px;padding:8px 28px;}
  .no{font-size:30px;}
  h1{margin-top:44px;font-size:92px;line-height:1.1;}
  .hook{margin-top:28px;font-size:44px;line-height:1.25;}
  .list{position:relative;margin-top:48px;padding-left:44px;display:flex;flex-direction:column;gap:34px;}
  .list::before{content:"";position:absolute;left:9px;top:24px;bottom:24px;width:2px;
    background:linear-gradient(180deg,#22d3ee,#a78bfa,rgba(251,191,36,.55));}
  .li{position:relative;font-size:41px;font-weight:700;color:#e2e8f0;letter-spacing:1px;line-height:1.25;}
  .li::before{content:"";position:absolute;left:-44px;top:14px;width:19px;height:19px;border-radius:50%;
    background:#22d3ee;box-shadow:0 0 20px rgba(34,211,238,.95);}
  .li:nth-child(2)::before{background:#38bdf8;box-shadow:0 0 20px rgba(56,189,248,.95);}
  .li:nth-child(3)::before{background:#a78bfa;box-shadow:0 0 20px rgba(167,139,250,.95);}
  .li:nth-child(4)::before{background:#fbbf24;box-shadow:0 0 20px rgba(251,191,36,.95);}
  .li:nth-child(5)::before{background:#34d399;box-shadow:0 0 20px rgba(52,211,153,.95);}
  .li:nth-child(6)::before{background:#f472b6;box-shadow:0 0 20px rgba(244,114,182,.95);}
  .li .y{color:#fbbf24;}
  .payoff{margin-top:62px;padding:34px;border-radius:18px;
    background:linear-gradient(90deg,rgba(251,191,36,.18),rgba(251,191,36,.02));
    border-left:6px solid #fbbf24;font-size:42px;font-weight:800;color:#fff;
    letter-spacing:1px;line-height:1.4;}
  .payoff .y{color:#fbbf24;}
  .tags{margin-top:56px;display:grid;grid-template-columns:1fr 1fr;gap:22px;}
  .tag{font-size:32px;padding:14px 26px;text-align:center;border-radius:16px;}
</style></head><body>
<div class="wrap">
  <div class="grid"></div>
  <div class="inner">
    <div class="top">
      <span class="badge">《{{series}}》系列</span>
      <span class="no">{{no}}</span>
    </div>
    <h1>{{title}}</h1>
    <div class="hook">{{hook}}</div>
    {{rows}}
    {{payoff}}
    <div class="tags">
      {{tags}}
    </div>
  </div>
</div></body></html>""", series=series, no=spec["no"].split("·")[0].strip(),
        title=md(spec["title"]), hook=em(spec["hook"]), rows=rows, payoff=payoff, tags=tags)


def render(html, png, w, h, tmp, channel="chrome"):
    from playwright.sync_api import sync_playwright
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)
    with sync_playwright() as p:
        b = p.chromium.launch(channel=channel)
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        pg.goto("file:///" + tmp.replace("\\", "/"))
        pg.wait_for_timeout(1500)          # ★等字体加载，否则字变方框
        pg.screenshot(path=png)
        b.close()
    print("OK %s  %.0f KB" % (png, os.path.getsize(png) / 1024))


def main():
    ap = argparse.ArgumentParser(description="生成横版/竖版封面")
    ap.add_argument("--no", default="", help="课次标签，如「第一课 · 入门篇」")
    ap.add_argument("--title", required=True, help="主标题，用 ** 标金色，<br/> 换行")
    ap.add_argument("--hook", default="", help="副标题（含数字）")
    ap.add_argument("--sub", default="", help="横版第三行，罗列具体内容")
    ap.add_argument("--tags", default="", help="标签，用 | 分隔，最多 4 个")
    ap.add_argument("--rows", default="", help="竖版列表，用 ; 分隔")
    ap.add_argument("--payoff", default="", help="竖版点题框，用 ** 标金色")
    ap.add_argument("--out", default="cover", help="输出文件名前缀")
    ap.add_argument("--dir", default="", help="输出目录，默认 root/dist")
    ap.add_argument("--only", default="both", choices=["both", "bili", "vert"])
    a = ap.parse_args()

    c = cfg()
    series = c.text("course_title", "Course")
    out_dir = a.dir or os.path.join(c.root, c.text("output.dir", "dist"))
    os.makedirs(out_dir, exist_ok=True)
    channel = c.text("paths.chrome_channel", "chrome")

    spec = {
        "no": a.no or "",
        "title": a.title,
        "hook": a.hook,
        "sub": a.sub,
        "tags": [t for t in a.tags.split("|") if t.strip()],
        "rows": a.rows,
        "payoff": a.payoff,
    }

    if a.only in ("both", "bili"):
        render(bili_html(spec, series), os.path.join(out_dir, a.out + "-B站封面-横版.png"),
               1146, 717, os.path.join(out_dir, "_bili_cover.html"), channel)
    if a.only in ("both", "vert"):
        render(vert_html(spec, series), os.path.join(out_dir, a.out + "-抖音封面-竖版.png"),
               1080, 1920, os.path.join(out_dir, "_douyin_cover.html"), channel)


if __name__ == "__main__":
    main()
