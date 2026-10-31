# -*- coding: utf-8 -*-
"""零依赖 Markdown → HTML（只处理课程长文用到的语法）

用法：
  python md2html.py 第1课（文字版）.md
  python md2html.py 第1课（文字版）.md -o preview.html --title "我的课（第1课）"
"""
import re
import html
import os
import sys
import argparse


def inline(s):
    parts = re.split(r"(`[^`]+`)", s)
    res = []
    for p in parts:
        if len(p) > 2 and p.startswith("`") and p.endswith("`"):
            res.append("<code>" + html.escape(p[1:-1]) + "</code>")
        else:
            p = html.escape(p)
            p = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", p)
            p = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img alt="\1" src="\2">', p)
            p = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank">\1</a>', p)
            res.append(p)
    return "".join(res)


def convert(md):
    lines = md.split("\n")
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        s = line.strip()

        if s.startswith("```"):
            lang = s[3:].strip()
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(html.escape(lines[i]))
                i += 1
            i += 1
            cls = ' class="language-%s"' % lang if lang else ""
            out.append("<pre><code%s>%s</code></pre>" % (cls, "\n".join(buf)))
            continue

        if not s:
            i += 1
            continue

        if re.match(r"^-{3,}$", s):
            out.append("<hr>")
            i += 1
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (lvl, inline(m.group(2)), lvl))
            i += 1
            continue

        if s.startswith("|") and i + 1 < n and re.match(r"^\s*\|[\s:\-|]+\|\s*$", lines[i + 1]):
            header = [c.strip() for c in s.strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            th = "".join("<th>%s</th>" % inline(c) for c in header)
            trs = "".join(
                "<tr>" + "".join("<td>%s</td>" % inline(c) for c in r) + "</tr>" for r in rows)
            out.append("<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (th, trs))
            continue

        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>%s</blockquote>" % convert("\n".join(buf)))
            continue

        if re.match(r"^\s*[-*]\s+", line):
            buf = []
            while i < n and re.match(r"^\s*[-*]\s+", lines[i]):
                buf.append(re.sub(r"^\s*[-*]\s+", "", lines[i]))
                i += 1
            out.append("<ul>%s</ul>" % "".join("<li>%s</li>" % inline(x) for x in buf))
            continue

        if re.match(r"^\s*\d+\.\s+", line):
            buf = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                buf.append(re.sub(r"^\s*\d+\.\s+", "", lines[i]))
                i += 1
            out.append("<ol>%s</ol>" % "".join("<li>%s</li>" % inline(x) for x in buf))
            continue

        buf = [line]
        i += 1
        while i < n:
            nxt = lines[i]
            ns = nxt.strip()
            if not ns:
                break
            if ns.startswith(("```", "|", ">", "#")) or re.match(r"^-{3,}$", ns) \
               or re.match(r"^\s*[-*]\s+", nxt) or re.match(r"^\s*\d+\.\s+", nxt):
                break
            buf.append(nxt)
            i += 1
        out.append("<p>%s</p>" % "<br>".join(inline(x) for x in buf))
    return "\n".join(out)


CSS = """
* { box-sizing: border-box; }
body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
  max-width: 880px; margin: 0 auto; padding: 48px 28px 80px; line-height: 1.95;
  color: #2c3440; background: #fbfbfc; font-size: 16px; }
h1 { font-size: 30px; line-height: 1.4; margin: 0 0 8px; color: #10151d; letter-spacing: -.3px; }
h2 { font-size: 23px; margin: 46px 0 16px; color: #10151d; padding-bottom: 10px;
  border-bottom: 2px solid #eaecef; }
h3 { font-size: 18.5px; margin: 30px 0 12px; color: #1a6fe0; }
p { margin: 14px 0; }
strong { color: #0b0f15; font-weight: 700; }
a { color: #1a6fe0; }
img { max-width: 100%; height: auto; border-radius: 12px; display: block; margin: 22px auto;
  box-shadow: 0 6px 28px rgba(16,21,29,.14); border: 1px solid #e6e9ee; }
blockquote { border-left: 4px solid #1a6fe0; background: #f2f7ff; margin: 20px 0;
  padding: 14px 22px; border-radius: 0 10px 10px 0; color: #3a4a63; }
blockquote p { margin: 8px 0; }
pre { background: #1c2230; color: #dbe3f0; padding: 16px 20px; border-radius: 10px;
  overflow-x: auto; font-size: 14px; line-height: 1.65; }
code { font-family: "JetBrains Mono", Consolas, Monaco, monospace; font-size: 13.5px; }
pre code { color: #dbe3f0; }
p code, li code, td code { background: #eef1f6; color: #c7254e; padding: 2px 6px;
  border-radius: 5px; font-size: .9em; }
table { border-collapse: collapse; width: 100%; margin: 20px 0; font-size: 15px; }
th, td { border: 1px solid #e3e7ee; padding: 10px 14px; text-align: left; vertical-align: top; }
th { background: #f5f7fa; font-weight: 700; color: #10151d; }
tr:nth-child(even) td { background: #fafbfc; }
ul, ol { margin: 14px 0; padding-left: 26px; }
li { margin: 7px 0; }
hr { border: none; border-top: 1px solid #e6e9ee; margin: 36px 0; }
"""

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>"""


def build(src, dst=None, title=None):
    md = open(src, encoding="utf-8").read()
    body = convert(md)
    if title is None:
        m = re.search(r"^#\s+(.+)$", md, re.M)
        title = m.group(1).strip() if m else os.path.splitext(os.path.basename(src))[0]
    page = PAGE.format(title=html.escape(title), css=CSS, body=body)
    dst = dst or os.path.splitext(src)[0] + ".html"
    open(dst, "w", encoding="utf-8").write(page)
    print("HTML 已生成:", dst, len(page), "bytes")
    return dst


def main():
    ap = argparse.ArgumentParser(description="Markdown → 带样式的 HTML 预览")
    ap.add_argument("src", help="Markdown 文件路径")
    ap.add_argument("-o", "--out", default=None, help="输出 HTML 路径")
    ap.add_argument("--title", default=None, help="页面标题（默认取第一个 # 标题）")
    a = ap.parse_args()
    build(a.src, a.out, a.title)


if __name__ == "__main__":
    main()
