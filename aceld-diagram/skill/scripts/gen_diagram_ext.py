#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_diagram_ext.py —— Aceld 风格「扩展图种」生成器（时序 / 类 / 泳道）

主生成器 gen_diagram.py 只有节点 / 连线 / 分组 / 便签四种基元，画不了时序、类、泳道。
本脚本补这三种，但**不另立视觉**：色板、字号、标题位置、圆角矩形、1px 描边、
小三角箭头、「主体线在盒下 + 箭头层置顶」、能直连就不折 —— 全部直接复用 gen_diagram.py
的 THEME 与 Diagram 的 classmethod，保证同一篇文章里四张图像一个人画的。

用法（spec 里必须有 kind）：
    python gen_diagram_ext.py zinx_sequence.json -o out.html --svg out.svg
    kind: sequence | class | swimlane

零依赖，只用 Python 标准库；与本脚本同目录的 gen_diagram.py 必须存在。
"""
import sys
import os
import math

import gen_diagram as gd

THEME = gd.THEME
F = gd.F
esc = gd.esc
est = gd._est_text_w
D = gd.Diagram                      # 复用 _elems / _tip_elems / _ortho_join / _arrow_marker

MARGIN = 40
INK = "#333333"
LINE = "#5a5a5a"
GRID = "#c8cdd2"


def theme(token):
    if isinstance(token, (list, tuple)):
        return token[0], token[1], (token[2] if len(token) > 2 else "#000000")
    return THEME.get(token, (token, "#36393d", "#000000"))


class Sheet:
    """一张 SVG：body 按绘制顺序，tips 是箭头层，永远最后画。"""

    def __init__(self, spec):
        self.spec = spec
        cv = spec.get("canvas") or {}
        self.w = float(cv.get("width", 900))
        self.h = float(cv.get("height", 1000))
        self.body = []
        self.tips = []
        self.markers = {}

    def add(self, s):
        self.body.append(s)

    # ---------- 基元 ----------
    def rect(self, x, y, w, h, fill="#ffffff", stroke="none", r=8, sw=1.2, dash=None, opacity=None):
        d = dash or ""
        o = "" if opacity is None else f' opacity="{opacity}"'
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                 f'rx="{r}" ry="{r}" fill="{fill}" stroke="{stroke}" '
                 f'stroke-width="{sw}" {d}{o}/>')

    def text(self, x, y, s, size=13, color=INK, anchor="middle", bold=False, baseline="central"):
        fw = " font-weight='700'" if bold else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" fill="{color}" font-size="{size}"{fw} '
                 f'font-family="{F}" text-anchor="{anchor}" '
                 f'dominant-baseline="{baseline}">{esc(s)}</text>')

    def label(self, cx, cy, s, size=12.5):
        """连线文字：白底垫一层，避免压在彩线上糊成一团。"""
        tw = est(s, size) + 10
        self.add(f'<rect x="{cx-tw/2:.1f}" y="{cy-10:.1f}" width="{tw:.1f}" height="19" '
                 f'rx="3" fill="#ffffff" stroke="none" opacity="0.96"/>')
        self.text(cx, cy, s, size)

    def dot(self, cx, cy, r, fill, stroke="none"):
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')

    def _marker_def(self, color):
        name = "ah_" + color.lstrip("#")
        if name not in self.markers:
            self.markers[name] = D._arrow_marker(None, color, name)
        return name

    def wire(self, pts, color=LINE, dashed=False, label=None, label_at=None, head=True):
        """正交连线：主体线在盒下；末段 + 箭头提到 tips 层，永不被盖。"""
        pts = D._ortho_join(pts)
        d = D._path_d(pts)
        halo, line = D._elems(d, color, dashed, marker=False)
        self.add(halo)
        self.add(line)
        if head:
            th, tl = D._tip_elems(pts, color, dashed)
            self.tips.append(th)
            self.tips.append(tl)
            self._marker_def(color)
        if label:
            cx, cy = label_at or ((pts[0][0] + pts[-1][0]) / 2, pts[0][1] - 14)
            self.label(cx, cy, label)
        return pts

    def triangle(self, tip, direction, color, filled=False):
        """UML 空心/实心三角（实现 / 继承关系），画在箭头层。"""
        x, y = tip
        k = 13
        if direction == "left":
            poly = f"{x:.1f},{y:.1f} {x+k:.1f},{y-7:.1f} {x+k:.1f},{y+7:.1f}"
        elif direction == "right":
            poly = f"{x:.1f},{y:.1f} {x-k:.1f},{y-7:.1f} {x-k:.1f},{y+7:.1f}"
        elif direction == "up":
            poly = f"{x:.1f},{y:.1f} {x-7:.1f},{y+k:.1f} {x+7:.1f},{y+k:.1f}"
        else:
            poly = f"{x:.1f},{y:.1f} {x-7:.1f},{y-k:.1f} {x+7:.1f},{y-k:.1f}"
        fill = color if filled else "#ffffff"
        self.tips.append(f'<polygon points="{poly}" fill="{fill}" stroke="{color}" '
                         f'stroke-width="1.6" stroke-linejoin="round"/>')

    def group_frame(self, x, y, w, h, title, stroke="#6c8ebf", fill="#F5F8FB"):
        self.rect(x, y, w, h, fill=fill, stroke=stroke, r=10,
                  dash="stroke-dasharray='7,5'")
        if title:
            tw = est(title, 13) + 12
            self.rect(x + 6, y + 4, tw, 19, fill=fill, stroke="none", r=3)
            self.text(x + 12, y + 15, title, 13, color="#3a4550", anchor="start", bold=True)

    # ---------- 收尾 ----------
    def title(self):
        meta = self.spec.get("meta") or {}
        ty = MARGIN + 6
        self.text(MARGIN, ty + 20, meta.get("title", "架构图"), 26, color="#000000",
                  anchor="start", bold=True)
        if meta.get("subtitle"):
            self.text(MARGIN, ty + 44, meta["subtitle"], 14, color="#888888", anchor="start")

    def svg(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w:.0f}" '
                f'height="{self.h:.0f}" viewBox="0 0 {self.w:.0f} {self.h:.0f}">'
                f'<rect width="{self.w:.0f}" height="{self.h:.0f}" fill="#ffffff"/>'
                + "".join(self.markers.values())
                + "\n".join(self.body) + "\n" + "\n".join(self.tips) + "</svg>")

    def html(self):
        return ("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
                "<style>body{margin:0;background:#f5f6f8;display:flex;justify-content:center;"
                f"padding:24px;font-family:{F}"
                "}.sheet{background:#fff;box-shadow:0 2px 14px rgba(0,0,0,.08);border-radius:8px}</style>"
                "</head><body><div class='sheet'>" + self.svg() + "</div></body></html>")


# ====================== ① 时序交互图 ======================
def render_sequence(sh, spec):
    actors = spec["actors"]
    msgs = spec.get("messages", [])
    idx = {a["id"]: i for i, a in enumerate(actors)}
    left, right = MARGIN, sh.w - MARGIN
    col_w = (right - left) / len(actors)
    cxs = [left + col_w * (i + 0.5) for i in range(len(actors))]

    head_y, head_h = 132, 46
    row0 = head_y + head_h + 56
    row_h = float(spec.get("rowHeight", 62))
    ys = [row0 + i * row_h for i in range(len(msgs))]
    bottom = (ys[-1] if ys else row0) + 58

    # 组合框（loop / opt）：边框画在最底层，标题留到最后画，
    # 否则生命线 / 激活条 / 消息线的白晕会压掉标题最后一个字。
    frame_labels = []
    for fr in spec.get("frames", []):
        lanes = fr.get("lanes") or [a["id"] for a in actors]
        xs = [cxs[idx[l]] for l in lanes]
        x0, x1 = min(xs) - col_w / 2 + 8, max(xs) + col_w / 2 - 8
        y0, y1 = ys[fr["from"]] - 30, ys[fr["to"]] + 26
        sh.rect(x0, y0, x1 - x0, y1 - y0, fill="none", stroke="#9aa0a6", r=8,
                dash="stroke-dasharray='6,4'")
        frame_labels.append((x0, y0, fr["label"]))

    # 生命线
    for cx in cxs:
        sh.add(f'<line x1="{cx:.1f}" y1="{head_y+head_h:.1f}" x2="{cx:.1f}" y2="{bottom:.1f}" '
               f'stroke="{GRID}" stroke-width="1.4" stroke-dasharray="6,5"/>')

    # 激活条
    for act in spec.get("activations", []):
        cx = cxs[idx[act["actor"]]]
        y0, y1 = ys[act["from"]] - 12, ys[act["to"]] + 12
        f, s, _ = theme(act.get("fill", "lblue"))
        sh.rect(cx - 6, y0, 12, y1 - y0, fill=f, stroke=s, r=2, sw=1.0)

    # 消息（先连线，头框与便签后画）
    for i, m in enumerate(msgs):
        y = ys[i]
        a, b = idx[m["from"]], idx[m["to"]]
        color = m.get("color", LINE)
        dashed = bool(m.get("dashed"))
        lab = m.get("label", "")
        if a == b:                                   # 自调用：右侧小 U 形
            x = cxs[a]
            pts = [(x + 7, y - 10), (x + 66, y - 10), (x + 66, y + 22), (x + 9, y + 22)]
            # 标签必须落在 U 形竖线的外侧，否则白底会把折返段盖掉一截
            lw = est(lab, 12.5) + 10
            lx = x + 66 + 12 + lw / 2
            if lx + lw / 2 > sh.w - MARGIN:          # 贴右边界时镜像到左侧
                lx = x - 20 - 12 - lw / 2
            sh.wire(pts, color, dashed, label=lab, label_at=(lx, y + 6))
        else:
            x1, x2 = cxs[a], cxs[b]
            sign = 1 if x2 > x1 else -1
            p1 = (x1 + sign * 8, y)
            p2 = (x2 - sign * 8, y)
            sh.wire([p1, p2], color, dashed, label=lab,
                    label_at=((p1[0] + p2[0]) / 2, y - 15))
        if m.get("note"):
            cx = cxs[a] if a == b else (cxs[a] + cxs[b]) / 2
            sh.rect(cx - est(m["note"], 12) / 2 - 8, y + 14, est(m["note"], 12) + 16, 24,
                    fill="#fff2cc", stroke="#d6b656", r=4, sw=1.0)
            sh.text(cx, y + 26, m["note"], 12, color="#6b5b20")

    # 参与者头框
    for i, a in enumerate(actors):
        f, s, t = theme(a.get("fill", "slate"))
        w = col_w - 20
        sh.rect(cxs[i] - w / 2, head_y, w, head_h, fill=f, stroke=s, r=8)
        sh.text(cxs[i], head_y + head_h / 2, a["label"], 14, color=t, bold=True)

    # 组合框标题必须最后落笔：盖住穿过标题的生命线与激活条
    for x0, y0, lab in frame_labels:
        sh.rect(x0 + 6, y0 - 9, est(lab, 12) + 14, 19, fill="#ffffff",
                stroke="none", r=3)
        sh.text(x0 + 13, y0 + 1, lab, 12, color="#55606a", anchor="start", bold=True)

    # 底部一行说明（可选）
    if spec.get("footer"):
        sh.text(sh.w / 2, bottom + 20, spec["footer"], 12.5, color="#888888")


# ====================== ② 类图 ======================
def class_center(c):
    return c["x"] + c["w"] / 2, c["y"] + c["h"] / 2


def render_class(sh, spec):
    groups = {g["id"]: g for g in spec.get("groups", [])}
    classes = {c["id"]: c for c in spec["classes"]}

    for g in groups.values():
        sh.group_frame(g["x"], g["y"], g["w"], g["h"], g.get("title", ""),
                       stroke=g.get("stroke", "#6c8ebf"), fill=g.get("fill", "#F5F8FB"))

    # 关系先画（主体线在类框之下）；箭头 / 三角提到 tips 层
    for r in spec.get("relations", []):
        a, b = classes[r["from"]], classes[r["to"]]
        acx, acy = class_center(a)
        bcx, bcy = class_center(b)
        color = r.get("color", LINE)
        kind = r.get("kind", "assoc")
        dashed = kind in ("realize", "depend")
        if abs(acy - bcy) <= 18:                    # 同一行 → 一条水平直线
            sign = 1 if bcx > acx else -1
            p1 = (a["x"] + a["w"] if sign > 0 else a["x"], acy)
            p2 = (b["x"] if sign > 0 else b["x"] + b["w"], bcy)
            pts = [(p1[0] + sign * 8, p1[1]), (p2[0] - sign * 8, p2[1])]
            direction = "right" if sign > 0 else "left"
        elif abs(acx - bcx) <= 18:                  # 同一列 → 一条竖直直线
            sign = 1 if bcy > acy else -1
            p1 = (acx, a["y"] + a["h"] if sign > 0 else a["y"])
            p2 = (bcx, b["y"] if sign > 0 else b["y"] + b["h"])
            pts = [(p1[0], p1[1] + sign * 8), (p2[0], p2[1] - sign * 8)]
            direction = "down" if sign > 0 else "up"
        else:                                       # 斜向：只折一次（V-H-V）
            my = (acy + bcy) / 2
            mx = (acx + bcx) / 2
            pts = [(acx, acy + (a["h"] / 2 if bcy > acy else -a["h"] / 2) + 8),
                   (acx, my), (bcx, my),
                   (bcx, bcy + (-b["h"] / 2 if bcy > acy else b["h"] / 2) - 8)]
            direction = "down" if bcy > acy else "up"
        lab_at = ((pts[0][0] + pts[-1][0]) / 2,
                  (pts[0][1] + pts[-1][1]) / 2 - 14)
        pts = sh.wire(pts, color, dashed, label=r.get("label"),
                      label_at=lab_at, head=(kind != "realize"))
        if kind == "realize":
            sh.triangle(pts[-1], direction, color, filled=False)

    # 类框
    for c in spec["classes"]:
        x, y, w, h = c["x"], c["y"], c["w"], c["h"]
        f, s, t = theme(c.get("fill", "white"))
        sh.rect(x, y, w, h, fill="#ffffff", stroke=s, r=8)
        hh = 30
        sh.rect(x, y, w, hh + 9, fill=f, stroke="none", r=8)
        sh.rect(x, y + hh - 2, w, 11, fill=f, stroke="none", r=0)
        sh.add(f'<line x1="{x:.1f}" y1="{y+hh:.1f}" x2="{x+w:.1f}" y2="{y+hh:.1f}" '
               f'stroke="{s}" stroke-width="1.0"/>')
        name = ("«interface» " if c.get("stereotype") == "interface" else "") + c["label"]
        sh.text(x + w / 2, y + hh / 2, name, 13.5 if c.get("stereotype") else 14.5,
                color=t, bold=True)

        fields = c.get("fields") or []
        methods = c.get("methods") or []
        yy = y + hh + 16
        for line in fields:
            sh.text(x + 12, yy, line, 12, color="#444", anchor="start")
            yy += 18
        if fields and methods:
            sh.add(f'<line x1="{x+8:.1f}" y1="{yy-8:.1f}" x2="{x+w-8:.1f}" y2="{yy-8:.1f}" '
                   f'stroke="#dfe3e8" stroke-width="1.0" stroke-dasharray="4,3"/>')
        for line in methods:
            sh.text(x + 12, yy, line, 12, color="#444", anchor="start")
            yy += 18


# ====================== ③ 泳道图 ======================
def render_swimlane(sh, spec):
    lanes = spec["lanes"]
    steps = spec.get("steps", [])
    idx = {l["id"]: i for i, l in enumerate(lanes)}
    left, right = MARGIN, sh.w - MARGIN
    lw = (right - left) / len(lanes)
    lx = [left + i * lw for i in range(len(lanes))]
    cx = [x + lw / 2 for x in lx]

    top = 132
    head_h = 44
    row_h = float(spec.get("rowHeight", 82))
    step_h = float(spec.get("stepHeight", 52))
    ys = [top + head_h + 34 + i * row_h for i in range(len(steps))]
    bottom = (ys[-1] if ys else top + head_h) + 62

    # 泳道底 + 竖直分隔
    for i in range(len(lanes)):
        fill = "#F7F9FC" if i % 2 == 0 else "#FFFFFF"
        sh.rect(lx[i], top, lw, bottom - top, fill=fill, stroke="#e1e5ea", r=0, sw=1.0)

    # 连线（先画，步骤框后画盖住线尾）
    for i in range(len(steps) - 1):
        a, b = steps[i], steps[i + 1]
        ia, ib = idx[a["lane"]], idx[b["lane"]]
        y1 = ys[i] + step_h / 2
        y2 = ys[i + 1] - step_h / 2
        color = b.get("color", LINE)
        if ia == ib:                                # 同列 → 一条竖线，不折
            pts = [(cx[ia], y1 + 8), (cx[ia], y2 - 8)]
            lab_at = (cx[ia] + 62, (y1 + y2) / 2)
        else:                                       # 跨列 → 只折一次（V-H-V）
            my = (y1 + y2) / 2
            pts = [(cx[ia], y1 + 8), (cx[ia], my), (cx[ib], my), (cx[ib], y2 - 8)]
            lab_at = ((cx[ia] + cx[ib]) / 2, my - 13)
        sh.wire(pts, color, dashed=bool(b.get("dashed")),
                label=b.get("label"), label_at=lab_at)

    # 泳道标题条
    for i, l in enumerate(lanes):
        f, s, t = theme(l.get("fill", "slate"))
        sh.rect(lx[i] + 4, top + 4, lw - 8, head_h - 8, fill=f, stroke=s, r=6)
        sh.text(cx[i], top + head_h / 2, l["label"], 14, color=t, bold=True)

    # 步骤框 + 序号
    for i, st in enumerate(steps):
        i_lane = idx[st["lane"]]
        x, w = lx[i_lane] + 16, lw - 32
        y, h = ys[i] - step_h / 2, step_h
        f, s, t = theme(st.get("fill", "white"))
        sh.rect(x, y, w, h, fill=f, stroke=s, r=8)
        sh.dot(x + 20, y + h / 2, 13, "#ffffff", stroke=s)
        sh.text(x + 20, y + h / 2, str(i + 1), 12, color=t if f != "#ffffff" else INK,
                bold=True)
        sh.text(x + 40 + (w - 50) / 2, y + h / 2, st["text"], 13,
                color=t, bold=True)


RENDERERS = {
    "sequence": render_sequence,
    "class": render_class,
    "swimlane": render_swimlane,
}


def main():
    if len(sys.argv) < 2:
        print("usage: python gen_diagram_ext.py <spec.json> [-o out.html] [--svg out.svg]")
        print("       spec.kind = sequence | class | swimlane")
        sys.exit(1)
    inp = sys.argv[1]
    out_html = out_svg = None
    args = sys.argv[2:]
    for i, a in enumerate(args):
        if a == "-o" and i + 1 < len(args):
            out_html = args[i + 1]
        elif a == "--svg" and i + 1 < len(args):
            out_svg = args[i + 1]
    if out_html is None:
        out_html = os.path.splitext(inp)[0] + ".html"
    if out_svg is None:
        out_svg = os.path.splitext(inp)[0] + ".svg"
    spec = gd.load_spec(inp)
    kind = spec.get("kind")
    render = RENDERERS.get(kind)
    if not render:
        print("!! spec.kind 必须是 sequence / class / swimlane，当前：%r" % kind)
        sys.exit(2)
    sh = Sheet(spec)
    render(sh, spec)
    sh.title()
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(sh.html())
    with open(out_svg, "w", encoding="utf-8") as f:
        f.write(sh.svg())
    print("OK [%s] -> %s / %s  (%.0fx%.0f)" %
          (kind, out_html, out_svg, sh.w, sh.h))


if __name__ == "__main__":
    main()
