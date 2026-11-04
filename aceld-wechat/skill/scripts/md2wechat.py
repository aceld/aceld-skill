# -*- coding: utf-8 -*-
"""markdown → 微信公众号内联样式 HTML

为什么必须内联样式：微信编辑器会剥掉 <style> 标签和 class 属性，
只保留元素上的 style。所以这里不用 CSS 类，每个元素都写死 style。

用法：
    python md2wechat.py --src 文章.md --out 公众号版.html --img-dir ./文章配图
    python md2wechat.py --src 文章.md --theme assets/theme-aceld.json --no-banner

设计要点：
  · 主题全部走 JSON（assets/theme-*.json），换配色不用改代码
  · 文章里的图片先写成本地 URL 占位（--img-base），发布脚本再换成 base64
  · 禁止 linear-gradient —— 微信 darkmode 规范会拦，粘贴会静默失败（见 references）
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
DEFAULT_THEME = os.path.join(SKILL, "assets", "theme-aceld.json")

# ---------- 默认主题（theme JSON 缺失时的兜底） ----------
FALLBACK = {
    "colors": {
        "ink": "#1f2733", "title": "#0f172a", "dim": "#5b6b7f",
        "accent": "#1b7fb8", "accent2": "#e07a00", "slate": "#647687",
        "bold": "#0e5f8a", "bgSoft": "#f4f7fa", "border": "#e3e9f0",
        "hlBg": "#fff3c4", "hlTxt": "#7a4d00", "pageBg": "#f6f9fc",
        "cardBg": "#edf4fa", "cardBg2": "#fdf6e9", "cardBorder": "#e4eef6",
    },
    "banner": None, "footer": None,
    "divider": None, "topBand": None,
}


def load_theme(path):
    th = json.loads(json.dumps(FALLBACK))          # deep copy
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        th["colors"].update(user.get("colors") or {})
        for k in ("banner", "footer", "divider", "topBand"):
            if k in user:
                th[k] = user[k]
    return th


class Renderer:
    def __init__(self, theme, img_base, img_prefix):
        self.t = theme
        self.c = theme["colors"]
        self.img_base = img_base
        self.img_prefix = img_prefix
        self.cjk_h2 = re.compile(r"^([一二三四五六七八九十]+)、\s*(.+)$")
        self.cn = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
                   "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

    # ---------- 基础 ----------
    @staticmethod
    def esc(t):
        return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def inline(self, text):
        c = self.c
        text = self.esc(text)
        # ==高亮==
        text = re.sub(
            r"==(.+?)==",
            r'<span style="background:%s;color:%s;padding:1px 4px;'
            r'border-radius:4px;font-weight:700;">\1</span>' % (c["hlBg"], c["hlTxt"]),
            text)
        # **加粗**
        text = re.sub(r"\*\*(.+?)\*\*",
                      r'<strong style="color:%s;font-weight:700;">\1</strong>' % c["bold"],
                      text)
        # `行内代码`
        text = re.sub(
            r"`([^`]+)`",
            r'<code style="background:%s;border:1px solid %s;border-radius:4px;'
            r'padding:1px 5px;font-size:14px;color:#c2410c;'
            r'font-family:Consolas,Menlo,monospace;">\1</code>'
            % (c["bgSoft"], c["border"]), text)
        return text

    def img_url(self, path):
        rel = path.replace("\\", "/")
        if self.img_prefix and rel.startswith(self.img_prefix):
            rel = rel[len(self.img_prefix):]
        return self.img_base + rel.lstrip("/")

    # ---------- 装饰块 ----------
    def divider(self):
        d = self.t.get("divider")
        if not d:
            return ""
        return ('<p style="margin:8px 0 6px;text-align:center;line-height:0;">'
                '<img src="%s%s" style="width:%dpx;max-width:100%%;" /></p>'
                % (self.img_base, d["img"], d.get("width", 520)))

    def top_band(self):
        d = self.t.get("topBand")
        if not d:
            return ""
        return ('<p style="margin:6px 0 10px;text-align:center;line-height:0;">'
                '<img src="%s%s" style="width:100%%;max-width:%dpx;" /></p>'
                % (self.img_base, d["img"], d.get("maxWidth", 640)))

    def banner(self):
        b = self.t.get("banner")
        if not b:
            return ""
        tags = ""
        for i, tg in enumerate(b.get("tags") or []):
            tags += ('<span style="display:inline-block;font-size:12px;font-weight:700;'
                     'color:%s;background:%s;border-radius:999px;padding:4px 12px;'
                     'margin-right:8px;">%s</span>'
                     % (tg.get("fg", "#04121c"), tg.get("bg", "#22d3ee"), self.esc(tg["text"])))
        eyebrow = ""
        if b.get("eyebrow"):
            eyebrow = ('<p style="margin:0;font-size:12px;letter-spacing:4px;color:%s;'
                       'font-weight:600;">%s</p>'
                       % (b.get("eyebrowColor", "#7dd3fc"), self.esc(b["eyebrow"])))
        sub = ""
        if b.get("sub"):
            sub = ('<p style="margin:10px 0 0;font-size:14px;color:%s;line-height:1.75;">%s</p>'
                   % (b.get("subColor", "#c7d6e6"), b["sub"]))
        return (
            '<section style="margin:0 0 26px;padding:0;border-radius:16px;overflow:hidden;'
            'background:%s;box-shadow:0 10px 30px rgba(15,23,42,0.26);">'
            '<section style="padding:24px 24px 22px;">%s'
            '<p style="margin:12px 0 0;font-size:23px;font-weight:800;color:#ffffff;'
            'letter-spacing:1px;">%s</p>%s'
            '<p style="margin:16px 0 0;">%s</p>'
            '</section></section>'
            % (b.get("bg", "#0f2b3d"), eyebrow, self.esc(b.get("title", "")), sub, tags)
        )

    def footer(self):
        f = self.t.get("footer")
        if not f:
            return ""
        c = self.c
        body = "".join(
            '<p style="margin:0 0 10px;font-size:14px;line-height:1.85;color:#41505f;">%s</p>'
            % self.inline(p) for p in (f.get("paras") or []))
        tail = ""
        if f.get("tail"):
            tail = ('<p style="margin:24px 0 0;text-align:center;font-size:13px;'
                    'color:#9aa8b8;letter-spacing:1px;">%s</p>' % self.esc(f["tail"]))
        return (
            self.divider() +
            '<section style="margin:14px 0 0;padding:22px 24px;border-radius:14px;'
            'background:#f3f8fc;border:1px solid %s;">'
            '<p style="margin:0 0 10px;font-size:15px;font-weight:700;color:%s;'
            'letter-spacing:0.5px;">%s</p>%s</section>%s'
            % (c["border"], c["title"], self.esc(f.get("sign", "")), body, tail)
        )

    # ---------- 块级 ----------
    def cn_to_int(self, s):
        if s == "十":
            return 10
        if s.startswith("十"):
            return 10 + self.cn.get(s[1:], 0)
        if "十" in s:
            a, b = s.split("十", 1)
            return self.cn.get(a, 0) * 10 + (self.cn.get(b, 0) if b else 0)
        return self.cn.get(s, 0)

    def h2(self, text):
        c = self.c
        m = self.cjk_h2.match(text)
        label = ""
        if m:
            badge, ttl = m.group(1), m.group(2)
            g, card_bg = c["accent"], c["cardBg"]
            label = "PART %02d" % self.cn_to_int(badge)
        elif "写在最后" in text:
            badge, ttl = "终", text
            g, card_bg = c["accent2"], c["cardBg2"]
            label = "EPILOGUE"
        elif text.startswith("开场"):
            badge, ttl = "序", text
            g, card_bg = c["accent2"], c["cardBg2"]
            label = "PROLOGUE"
        elif "下节预告" in text:
            badge, ttl = "预告", text
            g, card_bg = c["slate"], "#f2f4f6"
            label = "NEXT"
        else:
            badge, ttl = "◆", text
            g, card_bg = c["accent"], c["cardBg"]

        label_html = ""
        if label:
            label_html = ('<p style="margin:0 0 8px;font-size:10.5px;letter-spacing:2.5px;'
                          'color:#8ea6b8;font-weight:700;">%s</p>' % label)
        inner = (
            '<h2 style="margin:0;padding:0;font-size:19px;font-weight:800;color:%s;'
            'line-height:1.5;letter-spacing:0.3px;">'
            '<span style="display:inline-block;min-width:32px;height:32px;line-height:32px;'
            'padding:0 6px;text-align:center;border-radius:16px;background:%s;color:#ffffff;'
            'font-size:15px;font-weight:800;vertical-align:middle;margin-right:11px;">%s</span>'
            '<span style="display:inline-block;vertical-align:middle;">%s</span></h2>'
            % (c["title"], g, badge, self.inline(ttl))
        )
        return (
            '<section style="margin:52px 0 22px;padding:13px 16px;border-radius:14px;'
            'background:%s;border:1px solid %s;">%s%s</section>'
            % (card_bg, c["cardBorder"], label_html, inner)
        )

    def h3(self, text):
        c = self.c
        return (
            '<h3 style="margin:30px 0 14px;padding:0 0 0 12px;border-left:3px solid %s;'
            'font-size:17px;font-weight:700;color:%s;line-height:1.6;'
            'letter-spacing:0.3px;">'
            '<span style="color:%s;font-size:12px;margin-right:7px;">◆</span>%s</h3>'
            % (c["accent2"], c["title"], c["accent2"], self.inline(text))
        )

    def p(self, text):
        c = self.c
        return ('<p style="margin:0 0 18px;font-size:16px;line-height:1.9;color:%s;'
                'letter-spacing:0.3px;text-align:justify;word-break:break-word;">%s</p>'
                % (c["ink"], self.inline(text)))

    def lead(self, text):
        """小节首段做成导语块：左侧竖条 + 浅底 + 加粗上色。"""
        c = self.c
        return (
            '<section style="margin:0 0 20px;padding:12px 16px;'
            'background:#f4f9fc;border-left:3px solid %s;border-radius:0 10px 10px 0;">'
            '<p style="margin:0;font-size:16px;line-height:1.9;color:#22303f;'
            'letter-spacing:0.3px;text-align:justify;"><strong style="color:%s;'
            'font-weight:700;">%s</strong></p></section>'
            % (c["accent"], c["bold"], self.inline(text))
        )

    def blockquote(self, lines):
        c = self.c
        inner, buf = [], []
        for ln in lines:
            if ln.strip() == "":
                if buf:
                    inner.append(self.inline("".join(buf)))
                    buf = []
            else:
                buf.append(ln)
        if buf:
            inner.append(self.inline("".join(buf)))
        paras = "".join(
            '<p style="margin:0 0 %s;font-size:15.5px;line-height:1.9;color:#3d4b5a;'
            'letter-spacing:0.3px;text-align:justify;">%s</p>'
            % ("0" if i == len(inner) - 1 else "12px", t)
            for i, t in enumerate(inner))
        return (
            '<section style="margin:0 0 24px;padding:18px 22px;background:#f1f7fb;'
            'border-left:4px solid %s;border-radius:0 12px 12px 0;">%s</section>'
            % (c["accent"], paras))

    def ul(self, items):
        c = self.c
        st = ("margin:7px 0;font-size:16px;line-height:1.9;color:%s;"
              "letter-spacing:0.3px;text-align:justify;" % c["ink"])
        lis = "".join('<li style="%s">%s</li>' % (st, self.inline(it)) for it in items)
        return ('<ul style="margin:0 0 20px;padding-left:24px;list-style-type:disc;">'
                '%s</ul>' % lis)

    def ol(self, items):
        c = self.c
        st = ("margin:7px 0;font-size:16px;line-height:1.9;color:%s;"
              "letter-spacing:0.3px;text-align:justify;" % c["ink"])
        lis = "".join('<li style="%s">%s</li>' % (st, self.inline(it)) for it in items)
        return '<ol style="margin:0 0 20px;padding-left:24px;">%s</ol>' % lis

    def table(self, rows):
        c = self.c
        header = rows[0]
        th = "".join(
            '<th style="border:1px solid %s;background:#e9f1f7;padding:10px 12px;'
            'font-size:14px;font-weight:700;color:%s;text-align:left;'
            'line-height:1.6;">%s</th>' % (c["border"], c["title"], self.inline(x))
            for x in header)
        trs = []
        for idx, r in enumerate(rows[1:]):
            bg = "#ffffff" if idx % 2 == 0 else "#fafcfe"
            tds = "".join(
                '<td style="border:1px solid %s;background:%s;padding:10px 12px;'
                'font-size:14px;color:#41505f;line-height:1.7;vertical-align:top;">%s</td>'
                % (c["border"], bg, self.inline(x)) for x in r)
            trs.append("<tr>%s</tr>" % tds)
        return ('<table style="width:100%%;border-collapse:collapse;margin:0 0 24px;'
                'font-size:14px;"><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
                % (th, "".join(trs)))

    def image(self, alt, path):
        c = self.c
        cap = ""
        if alt and alt.strip():
            cap = ('<span style="display:block;margin-top:9px;font-size:13px;'
                   'color:%s;text-align:center;letter-spacing:0.5px;">%s</span>'
                   % (c["dim"], self.esc(alt)))
        return ('<p style="margin:10px 0 28px;text-align:center;">'
                '<img src="%s" style="max-width:100%%;border-radius:8px;'
                'border:1px solid #e8edf2;" />%s</p>' % (self.img_url(path), cap))

    # ---------- 代码高亮 ----------
    def codeblock(self, lang, lines):
        c = self.c
        inner = self.highlight(lang, "\n".join(lines))
        return ('<pre style="margin:0 0 22px;padding:15px 18px;background:#f8fafc;'
                'border:1px solid %s;border-radius:10px;overflow-x:auto;'
                'font-size:13.5px;line-height:1.85;color:#0f172a;'
                'font-family:Consolas,Menlo,monospace;white-space:pre-wrap;'
                'word-break:break-word;"><code>%s</code></pre>' % (c["border"], inner))

    def highlight(self, lang, code):
        """pygments → 内联 span style。没有 pygments 就原样输出（照样能贴）。"""
        try:
            from pygments import highlight as _hl
            from pygments.formatters import HtmlFormatter
            from pygments.lexers import get_lexer_by_name
        except ImportError:
            return self.esc(code)
        try:
            lexer = get_lexer_by_name((lang or "text").strip() or "text", stripall=True)
        except Exception:
            lexer = get_lexer_by_name("text", stripall=True)
        fm = HtmlFormatter(nowrap=True, style="friendly", cssclass="h")
        raw = _hl(code, lexer, fm)
        rules = self._hl_rules()
        return re.sub(r'<span class="([^"]+)">', lambda m: rules.get(m.group(1), m.group(0)), raw)

    _RULES = None

    def _hl_rules(self):
        if Renderer._RULES is not None:
            return Renderer._RULES
        from pygments.formatters import HtmlFormatter
        css = HtmlFormatter(style="friendly", cssclass="h").get_style_defs(".h")
        rules = {}
        for m in re.compile(r"\.h\s+\.(\w+)\s*\{([^}]*)\}").finditer(css):
            cm = re.search(r"color:\s*([^;]+)", m.group(2))
            if cm:
                style = "color:%s" % cm.group(1).strip()
                if "bold" in m.group(2):
                    style += ";font-weight:bold"
                rules[m.group(1)] = '<span style="%s">' % style
        Renderer._RULES = rules
        return rules


def parse(r, md):
    lines = md.split("\n")
    out, i, n = [], 0, len(lines)
    title, in_section = "", False

    def push_divider():
        d = r.divider()
        if d and (not out or d not in out[-1]):
            out.append(d)

    while i < n:
        s = lines[i].strip()

        if s.startswith("```"):
            lang = s[3:].strip()
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append(r.codeblock(lang, buf))
            continue

        if s.startswith("# "):
            title = s[2:].strip()
            i += 1
            continue
        if s.startswith("### "):
            out.append(r.h3(s[4:].strip()))
            in_section = True
            i += 1
            continue
        if s.startswith("## "):
            htext = s[3:].strip()
            if r.cjk_h2.match(htext):
                push_divider()
            out.append(r.h2(htext))
            in_section = False
            i += 1
            continue

        if s in ("---", "***", "___"):
            push_divider()
            i += 1
            continue

        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                t = lines[i].strip()[1:]
                buf.append(t[1:] if t.startswith(" ") else t)
                i += 1
            out.append(r.blockquote(buf))
            in_section = False
            continue

        if s.startswith("|"):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            rows = [x for x in rows
                    if not all(re.fullmatch(r":?-{2,}:?", c or "-") for c in x)]
            if rows:
                out.append(r.table(rows))
            continue

        m = re.match(r"^!\[(.*?)\]\((.*?)\)\s*$", s)
        if m:
            out.append(r.image(m.group(1), m.group(2)))
            i += 1
            continue

        if re.match(r"^[-*]\s+", s):
            buf = []
            while i < n and re.match(r"^[-*]\s+", lines[i].strip()):
                buf.append(re.sub(r"^[-*]\s+", "", lines[i].strip()))
                i += 1
            out.append(r.ul(buf))
            in_section = False
            continue

        if re.match(r"^\d+\.\s+", s):
            buf = []
            while i < n and re.match(r"^\d+\.\s+", lines[i].strip()):
                buf.append(re.sub(r"^\d+\.\s+", "", lines[i].strip()))
                i += 1
            out.append(r.ol(buf))
            in_section = False
            continue

        if s == "":
            i += 1
            continue

        out.append(r.lead(s) if in_section else r.p(s))
        in_section = False
        i += 1

    return title, "\n".join(out)


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def main():
    ap = argparse.ArgumentParser(description="markdown → 微信公众号内联样式 HTML")
    ap.add_argument("--src", required=True, help="源 markdown 文件")
    ap.add_argument("--out", required=True, help="输出 html")
    ap.add_argument("--meta", default=None, help="输出 meta.json（标题+图片清单），默认与 out 同目录")
    ap.add_argument("--theme", default=DEFAULT_THEME, help="主题 JSON")
    ap.add_argument("--img-base", default="http://127.0.0.1:8792/",
                    help="图片占位 URL 前缀，发布时会被替换成 base64")
    ap.add_argument("--img-prefix", default="文章配图/", help="md 里图片路径要剥掉的前缀")
    ap.add_argument("--no-banner", action="store_true")
    ap.add_argument("--no-footer", action="store_true")
    a = ap.parse_args()

    theme = load_theme(a.theme)
    if a.no_banner:
        theme["banner"] = None
    if a.no_footer:
        theme["footer"] = None

    r = Renderer(theme, a.img_base, a.img_prefix)
    with open(a.src, encoding="utf-8") as f:
        md = f.read()
    title, body = parse(r, md)

    full = ('<section style="background:%s;padding:16px 12px 22px;">'
            % theme["colors"]["pageBg"]
            + r.top_band() + "\n" + r.banner() + "\n"
            + body + "\n" + r.footer() + '</section>')

    with open(a.out, "w", encoding="utf-8") as f:
        f.write(full)

    imgs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", md)
    meta_path = a.meta or os.path.join(os.path.dirname(os.path.abspath(a.out)), "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"title": title, "images": imgs}, f, ensure_ascii=False, indent=2)

    # 自检：渐变是微信明令禁止的，出现在这里说明主题或代码写错了
    grad = full.count("linear-gradient")
    print("TITLE     :", title)
    print("HTML_LEN  :", len(full))
    print("H2/H3     :", full.count("<h2"), "/", full.count("<h3"))
    print("IMG_REF   :", len(imgs), " IMG_TAG:", full.count("<img "))
    print("TABLE/BQ  :", full.count("<table"), "/", full.count("border-left:4px solid"))
    print("GRADIENT  :", grad, "（必须为 0，微信会拦渐变）")
    print("OUT       :", a.out)
    print("META      :", meta_path)
    if grad:
        print("!! 发现 linear-gradient —— 粘贴会被「内容结构检测」拦掉，改成纯色")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
