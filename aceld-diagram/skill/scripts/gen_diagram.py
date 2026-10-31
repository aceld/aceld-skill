#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_diagram.py —— 生成「Aceld 风格」架构图 (SVG)

复刻刘丹冰(Aceld) 在 draw.io 里沉淀的架构图风格：白底、扁平、draw.io 默认主题配色
（蓝/绿/浅蓝/红/黄/灰/橙/紫/石板蓝…配对应描边）、圆角矩形模块、虚线分组、数据库用圆柱、
便签做标注、1px 细线 + 小箭头、左侧「鹰眼」监控列。

声明式 spec（JSON 优先；YAML 需装 PyYAML），节点/边/面板可自由摆放或自动布局。

用法：
    python gen_diagram.py spec.json                 # 生成 spec.html + spec.svg
    python gen_diagram.py spec.json -o out.html     # 指定 html 输出
    python gen_diagram.py spec.yaml --svg out.svg   # 同时导出 svg

spec 字段见 skill/assets/diagram.example.json
"""
import sys
import os
import json


# ====================== draw.io 默认主题配色 ======================
# (fill, stroke, 默认文字色) —— Aceld 实测高频色来自 draw.io 默认调色板
THEME = {
    "blue":   ("#1ba1e2", "#006EAF", "#ffffff"),
    "lblue":  ("#dae8fc", "#6c8ebf", "#000000"),
    "cyan":   ("#b1ddf0", "#10739e", "#000000"),
    "green":  ("#d5e8d4", "#82b366", "#000000"),
    "sgreen": ("#60a917", "#2D7600", "#ffffff"),
    "red":    ("#f8cecc", "#b85450", "#000000"),
    "crimson":("#FF3333", "#C73500", "#ffffff"),
    "yellow": ("#fff2cc", "#d6b656", "#000000"),
    "amber":  ("#FFCC99", "#FF8000", "#000000"),
    "orange": ("#fa6800", "#C73500", "#ffffff"),
    "purple": ("#e1d5e7", "#9673a6", "#000000"),
    "gray":   ("#E6E6E6", "#666666", "#000000"),
    "lgray":  ("#f5f5f5", "#666666", "#000000"),
    "slate":  ("#647687", "#314354", "#ffffff"),
    "dark":   ("#36393d", "#000000", "#ffffff"),
    "white":  ("#FFFFFF", "#36393d", "#000000"),
    "black":  ("#000000", "#000000", "#ffffff"),
}


# ====================== 极简 YAML（兜底） ======================
def _strip_comment(line):
    out, in_q, q = [], False, ""
    i = 0
    while i < len(line):
        c = line[i]
        if in_q:
            out.append(c)
            if c == q:
                in_q = False
        elif c in ("'", '"'):
            in_q, q = True, c
            out.append(c)
        elif c == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        else:
            out.append(c)
        i += 1
    return "".join(out).rstrip()


def _scalar(v):
    v = v.strip()
    if v == "" or v in ("~", "null", "None"):
        return None
    if (v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'"):
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x) for x in _split_inline(inner)] if inner else []
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return float(v) if "." in v else int(v)
    except ValueError:
        return v


def _split_inline(s):
    parts, depth, cur, in_q, q = [], 0, [], False, ""
    for c in s:
        if in_q:
            cur.append(c)
            if c == q:
                in_q = False
        elif c in ("'", '"'):
            in_q, q = True, c
            cur.append(c)
        elif c in "[{":
            depth += 1
            cur.append(c)
        elif c in "]}":
            depth -= 1
            cur.append(c)
        elif c == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(c)
    if cur:
        parts.append("".join(cur))
    return [p for p in parts if p.strip() != ""]


def _mini_yaml(text):
    lines = text.split("\n")
    root, stack = {}, [(-1, root, False)]

    def parent_for(indent):
        while len(stack) > 1 and stack[-1][0] >= indent:
            stack.pop()
        return stack[-1]

    i, n = 0, len(lines)
    while i < n:
        raw = _strip_comment(lines[i])
        if not raw.strip():
            i += 1
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        content = raw.strip()
        pindent, pnode, _ = parent_for(indent)
        if content.startswith("- "):
            item = content[2:].strip()
            if isinstance(pnode, list):
                if ":" in item and not item.startswith("["):
                    k, v = item.split(":", 1)
                    d = {k.strip(): _scalar(v)}
                    pnode.append(d)
                    stack.append((indent, d, False))
                else:
                    pnode.append(_scalar(item))
            else:
                (pnode if isinstance(pnode, dict) else root).setdefault("_items", []).append(_scalar(item))
        else:
            k, v = content.split(":", 1)
            k, v = k.strip(), v.strip()
            if isinstance(pnode, list):
                target = pnode[-1] if pnode and isinstance(pnode[-1], dict) else pnode
                if isinstance(target, dict):
                    if v == "":
                        target[k] = {}
                        stack.append((indent, target[k], False))
                    else:
                        target[k] = _scalar(v)
                else:
                    root.setdefault("_items", []).append({k: _scalar(v) if v else {}})
            else:
                if v == "":
                    pnode[k] = {}
                    stack.append((indent, pnode[k], False))
                else:
                    pnode[k] = _scalar(v)
        i += 1
    return root


def load_spec(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if path.lower().endswith(".json"):
        return json.loads(text)
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text)
    except ImportError:
        return _mini_yaml(text)


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _hex2rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _luminance(hexcolor):
    try:
        r, g, b = _hex2rgb(hexcolor)
    except Exception:
        return 1.0
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def _est_text_w(s, fs=13):
    return sum(fs if ord(ch) > 0x2E80 else fs * 0.55 for ch in str(s))


F = "Helvetica, Arial, PingFang SC, Microsoft YaHei, sans-serif"


# ====================== 渲染 ======================
class Diagram:
    def __init__(self, spec):
        self.spec = spec
        self.pal = dict(THEME)
        self.pal.update(spec.get("palette", {}) or {})
        self.MARGIN = 40
        self.parts = []
        self.nodes = {}
        self.groups = []
        self.panels = []
        self.min_x = self.MARGIN
        self.min_y = self.MARGIN
        self.max_x = 0
        self.max_y = 0
        self._build()
        self._render()

    def _resolve_theme(self, obj):
        fill = obj.get("fill", "white")
        if fill in self.pal:
            f, s, t = self.pal[fill]
        elif isinstance(fill, (list, tuple)) and len(fill) >= 2:
            f, s = fill[0], fill[1]
            t = fill[2] if len(fill) > 2 else None
        elif isinstance(fill, str) and fill.startswith("#"):
            f = fill
            s = obj.get("stroke", "#36393d")
            t = None
        else:
            f, s, t = self.pal.get(fill, self.pal["white"])
        if t is None:
            t = obj.get("text_color") or ("#ffffff" if _luminance(f) < 0.62 else "#000000")
        return f, s, t

    def _track(self, x, y, w, h):
        self.min_x = min(self.min_x, x)
        self.min_y = min(self.min_y, y)
        self.max_x = max(self.max_x, x + w)
        self.max_y = max(self.max_y, y + h)

    def _build(self):
        spec = self.spec
        for p in spec.get("panels", []):
            x, y = float(p["x"]), float(p["y"])
            w, h = float(p.get("w", 220)), float(p.get("h", 160))
            f, s, t = self._resolve_theme(p)
            self.panels.append({"x": x, "y": y, "w": w, "h": h, "fill": f,
                                "stroke": s, "label": p.get("label", ""), "text": t})
            self._track(x, y, w, h)

        for nd in spec.get("nodes", []):
            x, y = float(nd["x"]), float(nd["y"])
            w = float(nd.get("w", 130))
            h = float(nd.get("h", 48))
            f, s, t = self._resolve_theme(nd)
            self.nodes[nd["id"]] = {
                "id": nd["id"], "x": x, "y": y, "w": w, "h": h,
                "fill": f, "stroke": s, "text": t, "label": nd.get("label", nd["id"]),
                "shape": nd.get("shape", "rect"), "fontSize": nd.get("fontSize", 15),
                "bold": nd.get("bold", True),
            }
            self._track(x, y, w, h)

        for g in spec.get("groups", []):
            ids = g.get("nodes", [])
            if not ids:
                continue
            xs = [self.nodes[i]["x"] for i in ids if i in self.nodes]
            ys = [self.nodes[i]["y"] for i in ids if i in self.nodes]
            xe = [self.nodes[i]["x"] + self.nodes[i]["w"] for i in ids if i in self.nodes]
            ye = [self.nodes[i]["y"] + self.nodes[i]["h"] for i in ids if i in self.nodes]
            pad = 22
            bx, by = min(xs) - pad, min(ys) - pad - 18
            bw, bh = (max(xe) - min(xs)) + pad * 2, (max(ye) - min(ys)) + pad * 2 + 28
            self.groups.append({"x": bx, "y": by, "w": bw, "h": bh,
                               "title": g.get("title", ""), "stroke": g.get("stroke", "#666666")})
            self._track(bx, by, bw, bh)

        mon = spec.get("monitor")
        self.monitor_box = None
        if mon:
            top = min(self.min_y, (spec.get("panels") and min(p["y"] for p in spec["panels"]) or self.min_y)) - 10
            bottom = self.max_y + 10
            mw = 54
            if isinstance(mon, dict):
                m = dict(mon)
                if "fill" not in m:
                    m["fill"] = "blue"
                f, s, t = self._resolve_theme(m)
                label = m.get("label", "鹰眼")
            else:
                f, s, t = self.pal["blue"][0], self.pal["blue"][1], "#ffffff"
                label = "鹰眼"
            mx = self.min_x - mw - 14
            self.monitor_box = {"x": mx, "y": top, "w": mw, "h": bottom - top,
                                "fill": f, "stroke": s, "text": t, "label": label}
            self._track(mx, top, mw, bottom - top)

        # 左侧鹰眼列可能超出画布左界 → 整体右移
        left = self.min_x
        if self.monitor_box:
            left = min(left, self.monitor_box["x"])
        if left < self.MARGIN:
            sh = self.MARGIN - left
            for p in self.panels:
                p["x"] += sh
            for n in self.nodes.values():
                n["x"] += sh
            for g in self.groups:
                g["x"] += sh
            if self.monitor_box:
                self.monitor_box["x"] += sh
            self.min_x += sh
            self.max_x += sh

        self.width = self.max_x + self.MARGIN
        self.height = self.max_y + self.MARGIN
        cv = spec.get("canvas")
        if cv:
            self.width = max(self.width, cv.get("width", self.width))
            self.height = max(self.height, cv.get("height", self.height))

    # ---------- 图形基元 ----------
    def _add(self, s):
        self.parts.append(s)

    def _arrow_marker(self, color, name):
        return (f'<marker id="{name}" markerWidth="11" markerHeight="11" refX="8.5" refY="3.6" '
                f'orient="auto" markerUnits="userSpaceOnUse">'
                f'<path d="M0,0 L9,3.6 L0,7.2 Z" fill="{color}"/></marker>')

    def _rounded(self, x, y, w, h, r=8, fill="#fff", stroke="#36393d", sw=1.0, dash=None):
        d = dash or ""
        return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" ry="{r}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {d}/>')

    def _cylinder(self, x, y, w, h, fill, stroke, sw=1.0):
        ry = min(h * 0.16, w * 0.5, 13)
        body = (f'<path d="M{x:.1f},{y+ry:.1f} '
                f'L{x:.1f},{y+h-ry:.1f} '
                f'A{ry:.1f},{ry:.1f} 0 0 0 {x+w:.1f},{y+h-ry:.1f} '
                f'L{x+w:.1f},{y+ry:.1f} Z" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
        top = (f'<ellipse cx="{x+w/2:.1f}" cy="{y+ry:.1f}" rx="{w/2:.1f}" ry="{ry:.1f}" '
               f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
        return body + top

    def _node_box(self, n):
        x, y, w, h = n["x"], n["y"], n["w"], n["h"]
        sh = n["shape"]
        sw = 1.2
        if sh == "cylinder":
            return self._cylinder(x, y, w, h, n["fill"], n["stroke"], sw)
        if sh == "circle":
            cx, cy, r = x + w / 2, y + h / 2, min(w, h) / 2
            return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{n["fill"]}" stroke="{n["stroke"]}" stroke-width="{sw}"/>'
        if sh == "note":
            fold = 12
            return (f'<path d="M{x:.1f},{y:.1f} h{w-fold:.1f} l{fold:.1f},{fold:.1f} '
                    f'v{h-fold:.1f} h{-w:.1f} Z" fill="{n["fill"]}" stroke="{n["stroke"]}" stroke-width="{sw}"/>'
                    f'<path d="M{x+w-fold:.1f},{y:.1f} v{fold:.1f} h{-fold:.1f}" '
                    f'fill="none" stroke="{n["stroke"]}" stroke-width="{sw}"/>')
        return self._rounded(x, y, w, h, r=8, fill=n["fill"], stroke=n["stroke"], sw=sw)

    def _node_text(self, n):
        cx, cy = n["x"] + n["w"] / 2, n["y"] + n["h"] / 2
        fw = " font-weight='700'" if n.get("bold") else ""
        return (f'<text x="{cx:.1f}" y="{cy:.1f}" fill="{n["text"]}" font-size="{n["fontSize"]}"{fw} '
                f'font-family="{F}" text-anchor="middle" dominant-baseline="central">{esc(n["label"])}</text>')

    def _edge_geom(self, e):
        a = self.nodes.get(e["from"])
        b = self.nodes.get(e["to"])
        if not a or not b:
            return None
        acx, acy = a["x"] + a["w"] / 2, a["y"] + a["h"] / 2
        bcx, bcy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
        p1 = _rect_edge(acx, acy, a["x"], a["y"], a["w"], a["h"], bcx, bcy)
        p2 = _rect_edge(bcx, bcy, b["x"], b["y"], b["w"], b["h"], acx, acy)
        color = e.get("color", "#5a5a5a")
        dashed = bool(e.get("dashed"))
        dash = "stroke-dasharray='6,4' " if dashed else ""
        d = _ortho_path(p1, p2)
        halo = (f'<path d="{d}" fill="none" stroke="#ffffff" stroke-width="4.8" '
                f'stroke-linejoin="round" stroke-linecap="round" {dash}/>')
        line = (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.8" '
                f'stroke-linejoin="round" stroke-linecap="round" {dash}marker-end="url(#ah_{color.lstrip("#")})"/>')
        lab = e.get("label")
        label_bg = label_tx = None
        if lab:
            mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
            tw = _est_text_w(lab, 12.5) + 10
            label_bg = (f'<rect x="{mx-tw/2:.1f}" y="{my-11:.1f}" width="{tw:.1f}" height="20" '
                        f'rx="3" fill="#ffffff" stroke="none" opacity="0.95"/>')
            label_tx = (f'<text x="{mx:.1f}" y="{my:.1f}" fill="#333" font-size="12.5" '
                        f'font-family="{F}" text-anchor="middle" dominant-baseline="central">{esc(lab)}</text>')
        return {"color": color, "halo": halo, "line": line,
                "label_bg": label_bg, "label_tx": label_tx}

    # ---------- 渲染 ----------
    def _render(self):
        self._add(f'<rect x="0" y="0" width="{self.width:.1f}" height="{self.height:.1f}" fill="#ffffff"/>')
        marks = set()
        for p in self.panels:
            self._add(self._rounded(p["x"], p["y"], p["w"], p["h"], r=10, fill=p["fill"],
                                    stroke=p["stroke"], sw=1.0))
            if p["label"]:
                self._add(f'<text x="{p["x"]+12:.1f}" y="{p["y"]+20:.1f}" fill="{p["text"]}" '
                          f'font-size="14" font-weight="700" font-family="{F}">{esc(p["label"])}</text>')
        for g in self.groups:
            self._add(self._rounded(g["x"], g["y"], g["w"], g["h"], r=10, fill="none",
                                    stroke=g["stroke"], sw=1.0, dash="stroke-dasharray='7,5'"))
            if g["title"]:
                self._add(f'<text x="{g["x"]+12:.1f}" y="{g["y"]+15:.1f}" fill="#555" '
                          f'font-size="13" font-weight="700" font-family="{F}">{esc(g["title"])}</text>')
        if self.monitor_box:
            mb = self.monitor_box
            self._add(self._rounded(mb["x"], mb["y"], mb["w"], mb["h"], r=8, fill=mb["fill"],
                                    stroke=mb["stroke"], sw=1.2))
            cx = mb["x"] + mb["w"] / 2
            chars = list(mb["label"])
            n = len(chars)
            lh = 20
            total = n * lh
            start = mb["y"] + (mb["h"] - total) / 2 + lh / 2
            for i, ch in enumerate(chars):
                y = start + i * lh
                self._add(f'<text x="{cx:.1f}" y="{y:.1f}" fill="{mb["text"]}" font-size="16" '
                          f'font-weight="700" font-family="{F}" text-anchor="middle" '
                          f'dominant-baseline="central">{esc(ch)}</text>')
        # 先画全部边的白色光晕（跨线时留白），再画彩色边，避免交叉处糊在一起
        edge_geoms = [g for g in (self._edge_geom(e) for e in self.spec.get("edges", [])) if g]
        for g in edge_geoms:
            self._add(g["halo"])
        added_marks = set()
        for g in edge_geoms:
            mn = "ah_" + g["color"].lstrip("#")
            if mn not in added_marks:
                self._add(self._arrow_marker(g["color"], mn))
                added_marks.add(mn)
            self._add(g["line"])
            if g["label_bg"]:
                self._add(g["label_bg"])
                self._add(g["label_tx"])
        for n in self.nodes.values():
            self._add(self._node_box(n))
            self._add(self._node_text(n))
        for c in self.spec.get("callouts", []):
            x, y = c.get("at", [0, 0])
            text = c.get("text", "")
            color = c.get("color", "#fff2cc")
            tw = _est_text_w(text, 13) + 14
            self._add(self._rounded(x - tw / 2, y - 18, tw, 32, r=5, fill=color, stroke="#d6b656", sw=1.0))
            self._add(f'<text x="{x:.1f}" y="{y:.1f}" fill="#333" font-size="13" font-weight="700" font-family="{F}" '
                      f'text-anchor="middle" dominant-baseline="central">{esc(text)}</text>')
        meta = self.spec.get("meta", {})
        ty = self.MARGIN + 6
        title_x = self.MARGIN
        if self.monitor_box:
            title_x = self.monitor_box["x"] + self.monitor_box["w"] + 16
        self._add(f'<text x="{title_x:.1f}" y="{ty+20:.1f}" fill="#000" font-size="26" '
                  f'font-weight="700" font-family="{F}">{esc(meta.get("title", "架构图"))}</text>')
        if meta.get("subtitle"):
            self._add(f'<text x="{title_x:.1f}" y="{ty+44:.1f}" fill="#888" font-size="14" '
                      f'font-family="{F}">{esc(meta["subtitle"])}</text>')

    # ---------- 输出 ----------
    def svg(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width:.0f}" '
                f'height="{self.height:.0f}" viewBox="0 0 {self.width:.0f} {self.height:.0f}">'
                + "\n".join(self.parts) + "</svg>")

    def html(self):
        return ("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
                "<style>body{margin:0;background:#f5f6f8;display:flex;justify-content:center;"
                f"padding:24px;font-family:{F}"
                "}.sheet{background:#fff;box-shadow:0 2px 14px rgba(0,0,0,.08);border-radius:8px}</style>"
                "</head><body><div class='sheet'>" + self.svg() + "</div></body></html>")


def _rect_edge(cx, cy, x, y, w, h, tx, ty):
    """从矩形中心 (cx,cy) 沿指向 (tx,ty) 的方向，求与矩形边界的交点。"""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    hw, hh = w / 2, h / 2
    sx = hw / abs(dx) if dx != 0 else float("inf")
    sy = hh / abs(dy) if dy != 0 else float("inf")
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s


def _ortho_path(p1, p2):
    """两点之间的直角折线（H-V-H 或 V-H-V），拐角由 stroke-linejoin 圆角化。"""
    x1, y1 = p1
    x2, y2 = p2
    if abs(x2 - x1) >= abs(y2 - y1):
        mx = (x1 + x2) / 2
        return (f"M{x1:.1f},{y1:.1f} L{mx:.1f},{y1:.1f} "
                f"L{mx:.1f},{y2:.1f} L{x2:.1f},{y2:.1f}")
    else:
        my = (y1 + y2) / 2
        return (f"M{x1:.1f},{y1:.1f} L{x1:.1f},{my:.1f} "
                f"L{x2:.1f},{my:.1f} L{x2:.1f},{y2:.1f}")


def main():
    if len(sys.argv) < 2:
        print("usage: python gen_diagram.py <spec.json|yaml> [-o out.html] [--svg out.svg]")
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
    spec = load_spec(inp)
    d = Diagram(spec)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(d.html())
    with open(out_svg, "w", encoding="utf-8") as f:
        f.write(d.svg())
    print(f"OK -> {out_html}\nOK -> {out_svg}  ({d.width:.0f}x{d.height:.0f})")


if __name__ == "__main__":
    main()
