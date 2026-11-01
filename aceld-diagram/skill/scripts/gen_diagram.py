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
import math


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
            pad = 24
            bx, by = min(xs) - pad, min(ys) - pad - 18
            bw, bh = (max(xe) - min(xs)) + pad * 2, (max(ye) - min(ys)) + pad * 2 + 34
            self.groups.append({"x": bx, "y": by, "w": bw, "h": bh,
                               "title": g.get("title", ""),
                               "stroke": g.get("stroke", "#666666"),
                               "fill": g.get("fill", "#F5F8FB")})
            self._track(bx, by, bw, bh)
        # 所有分组统一为同一宽度（取并集左右界），形成等宽的层带
        if self.groups:
            gx0 = min(g["x"] for g in self.groups)
            gx1 = max(g["x"] + g["w"] for g in self.groups)
            for g in self.groups:
                g["x"] = gx0
                g["w"] = gx1 - gx0

        mon = spec.get("monitor")
        # 内容（节点/分组/面板）统一左对齐到 MARGIN；有跨维度列时再预留列宽，避免左侧大片留白
        content_xs = [n["x"] for n in self.nodes.values()] + [g["x"] for g in self.groups] + \
                     [p["x"] for p in self.panels]
        content_min_x = min(content_xs) if content_xs else self.MARGIN
        mw = 54
        target = self.MARGIN + (mw + 14 if mon else 0)
        sh = target - content_min_x
        if abs(sh) > 0.01:
            for p in self.panels:
                p["x"] += sh
            for n in self.nodes.values():
                n["x"] += sh
            for g in self.groups:
                g["x"] += sh

        self.monitor_box = None
        if mon:
            top = self.min_y - 10
            bottom = self.max_y + 10
            if isinstance(mon, dict):
                m = dict(mon)
                if "fill" not in m:
                    m["fill"] = "blue"
                f, s, t = self._resolve_theme(m)
                label = m.get("label", "全局")
            else:
                f, s, t = self.pal["blue"][0], self.pal["blue"][1], "#ffffff"
                label = "全局"
            self.monitor_box = {"x": self.MARGIN, "y": top, "w": mw, "h": bottom - top,
                                "fill": f, "stroke": s, "text": t, "label": label}

        # 重新计算画布范围
        xs = ([n["x"] for n in self.nodes.values()] + [n["x"] + n["w"] for n in self.nodes.values()] +
              [g["x"] for g in self.groups] + [g["x"] + g["w"] for g in self.groups] +
              [p["x"] for p in self.panels] + [p["x"] + p["w"] for p in self.panels])
        if self.monitor_box:
            xs += [self.monitor_box["x"], self.monitor_box["x"] + self.monitor_box["w"]]
        self.min_x = min(xs) if xs else self.MARGIN
        self.max_x = max(xs) if xs else self.MARGIN
        self.width = self.max_x + self.MARGIN
        self.height = self.max_y + self.MARGIN
        cv = spec.get("canvas")
        if cv:
            self.width = max(self.width, cv.get("width", self.width))
            self.height = max(self.height, cv.get("height", self.height))

        # 连线需要避开的「禁线」：分组上下/左右边、层级虚线 y、鹰眼左右边
        self.fb_y = sorted({g["y"] for g in self.groups} | {g["y"] + g["h"] for g in self.groups} |
                           {float(t["y"]) for t in spec.get("tiers", [])})
        _fx = {g["x"] for g in self.groups} | {g["x"] + g["w"] for g in self.groups}
        if self.monitor_box:
            _fx |= {self.monitor_box["x"], self.monitor_box["x"] + self.monitor_box["w"]}
        self.fb_x = sorted(_fx)

    # ---------- 图形基元 ----------
    def _add(self, s):
        self.parts.append(s)

    def _arrow_marker(self, color, name):
        return (f'<marker id="{name}" markerWidth="13" markerHeight="13" refX="10" refY="4" '
                f'orient="auto" markerUnits="userSpaceOnUse">'
                f'<path d="M0,0 L11,4 L0,8 Z" fill="{color}"/></marker>')

    def _rounded(self, x, y, w, h, r=8, fill="#fff", stroke="#36393d", sw=1.0, dash=None):
        d = dash or ""
        return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" ry="{r}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {d}/>')

    def _cylinder(self, x, y, w, h, fill, stroke, sw=1.0):
        ry = min(h * 0.16, w * 0.5, 13)
        rx = w / 2.0  # 底弧必须用椭圆 rx=w/2，否则半径过小会被 SVG 自动放大成半圆、底部溢出
        body = (f'<path d="M{x:.1f},{y+ry:.1f} '
                f'L{x:.1f},{y+h-ry:.1f} '
                f'A{rx:.1f},{ry:.1f} 0 0 0 {x+w:.1f},{y+h-ry:.1f} '
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

    # 连线端点留白：源头留 3px、目标留 8px（保证箭头整支落在盒子外，不被节点遮住）
    STUB_SRC = 3.0
    STUB_DST = 8.0

    @staticmethod
    def _jog(lo, hi, forbidden, tol=7.0):
        """在 [lo,hi] 内选一个不与禁线（分组边/层级线）重合的折点位置。"""
        lo, hi = min(lo, hi), max(lo, hi)
        for frac in (0.5, 0.42, 0.58, 0.35, 0.65, 0.28, 0.72):
            v = lo + (hi - lo) * frac
            if all(abs(v - f) >= tol for f in forbidden):
                return v
        return lo + (hi - lo) * 0.5

    @staticmethod
    def _nudge(v, lo, hi, forbidden, tol=6.0, step=8.0):
        """若端口坐标贴近某条禁线，则沿边挪开 step，仍限制在盒子范围内。"""
        for f in forbidden:
            if abs(v - f) < tol:
                cand = f + step
                if cand > hi:
                    cand = f - step
                if lo <= cand <= hi:
                    v = cand
                break
        return max(lo, min(hi, v))

    def _edge_sides(self, a, b, hint=None):
        """返回 (a 出口边, b 入口边, 是否竖直)，边取 top/bottom/left/right。"""
        ax, ay, aw, ah = a["x"], a["y"], a["w"], a["h"]
        bx, by, bw, bh = b["x"], b["y"], b["w"], b["h"]
        acx, acy = ax + aw / 2, ay + ah / 2
        bcx, bcy = bx + bw / 2, by + bh / 2
        v_sep = 1 if by >= ay + ah else (-1 if ay >= by + bh else 0)
        h_sep = 1 if bx >= ax + aw else (-1 if ax >= bx + bw else 0)
        if hint == "h":
            vertical = False
        elif hint == "v":
            vertical = True
        else:
            vertical = (v_sep != 0)
        if vertical:
            if v_sep == -1 or (v_sep == 0 and bcy < acy):
                return "top", "bottom", True
            return "bottom", "top", True
        if h_sep == -1 or (h_sep == 0 and bcx < acx):
            return "left", "right", False
        return "right", "left", False

    def _route(self, a, b, hint=None, o1=0.0, o2=0.0):
        """正交路由：上下分离→竖进竖出；同行/并排→横进横出。o1/o2 为两端沿边偏移（端口分配）。"""
        acx, acy = a["x"] + a["w"] / 2, a["y"] + a["h"] / 2
        bcx, bcy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
        s1, s2, vertical = self._edge_sides(a, b, hint)
        ss, sd = self.STUB_SRC, self.STUB_DST
        if s1 == "top":
            p1 = (acx + o1, a["y"] - ss)
        elif s1 == "bottom":
            p1 = (acx + o1, a["y"] + a["h"] + ss)
        elif s1 == "left":
            p1 = (a["x"] - ss, acy + o1)
        else:
            p1 = (a["x"] + a["w"] + ss, acy + o1)
        if s2 == "top":
            p2 = (bcx + o2, b["y"] - sd)
        elif s2 == "bottom":
            p2 = (bcx + o2, b["y"] + b["h"] + sd)
        elif s2 == "left":
            p2 = (b["x"] - sd, bcy + o2)
        else:
            p2 = (b["x"] + b["w"] + sd, bcy + o2)
        # 端口避让：竖直线的 x 别压在分组左右边上；水平折线 y 别压在分组上下边/层级线上
        if vertical:
            p1 = (self._nudge(p1[0], a["x"] + 6, a["x"] + a["w"] - 6, self.fb_x), p1[1])
            p2 = (self._nudge(p2[0], b["x"] + 6, b["x"] + b["w"] - 6, self.fb_x), p2[1])
            my = self._jog(p1[1], p2[1], self.fb_y)
            d = (f"M{p1[0]:.1f},{p1[1]:.1f} L{p1[0]:.1f},{my:.1f} "
                 f"L{p2[0]:.1f},{my:.1f} L{p2[0]:.1f},{p2[1]:.1f}")
            midx = (p1[0] + p2[0]) / 2
            cands = [
                (p1[0] + 13, (p1[1] + my) / 2),   # 源头竖直段右侧（避开分组标题）
                (p1[0] - 13, (p1[1] + my) / 2),   # 左侧
                (midx, my - 12),                  # 拐点上方
                (midx, my + 15),                  # 拐点下方
                (p2[0] + 13, (p2[1] + my) / 2),   # 目标端右侧
            ]
        else:
            p1 = (p1[0], self._nudge(p1[1], a["y"] + 6, a["y"] + a["h"] - 6, self.fb_y))
            p2 = (p2[0], self._nudge(p2[1], b["y"] + 6, b["y"] + b["h"] - 6, self.fb_y))
            mx = self._jog(p1[0], p2[0], self.fb_x)
            d = (f"M{p1[0]:.1f},{p1[1]:.1f} L{mx:.1f},{p1[1]:.1f} "
                 f"L{mx:.1f},{p2[1]:.1f} L{p2[0]:.1f},{p2[1]:.1f}")
            midy = (p1[1] + p2[1]) / 2
            cands = [
                (mx, midy - 12),
                (mx, midy + 15),
                (p1[0] + (p2[0] - p1[0]) * 0.3, midy - 12),
                (p1[0] + (p2[0] - p1[0]) * 0.7, midy - 12),
            ]
        return {"p1": p1, "p2": p2, "d": d, "lab_candidates": cands}

    def _assign_ports(self, edges):
        """同一节点的同一条边若有多条连线，按对端位置均匀错开，避免端口重叠、箭头被压。"""
        from collections import defaultdict
        ends = defaultdict(list)
        for i, e in enumerate(edges):
            a = self.nodes.get(e["from"])
            b = self.nodes.get(e["to"])
            if not a or not b:
                continue
            s1, s2, _ = self._edge_sides(a, b, e.get("route"))
            acx, acy = a["x"] + a["w"] / 2, a["y"] + a["h"] / 2
            bcx, bcy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
            ends[(e["from"], s1)].append((i, 0, bcx if s1 in ("top", "bottom") else bcy))
            ends[(e["to"], s2)].append((i, 1, acx if s2 in ("top", "bottom") else acy))
        off = {}
        for key, lst in ends.items():
            lst.sort(key=lambda t: t[2])
            n = len(lst)
            for k, (i, end, _) in enumerate(lst):
                off[(i, end)] = (k - (n - 1) / 2) * 24.0
        return [(off.get((i, 0), 0.0), off.get((i, 1), 0.0)) for i in range(len(edges))]

    def _edge_geom(self, e, o1=0.0, o2=0.0):
        a = self.nodes.get(e["from"])
        b = self.nodes.get(e["to"])
        if not a or not b:
            return None
        r = self._route(a, b, e.get("route"), o1, o2)
        d = r["d"]
        color = e.get("color", "#5a5a5a")
        dashed = bool(e.get("dashed"))
        dash = "stroke-dasharray='6,4' " if dashed else ""
        halo = (f'<path d="{d}" fill="none" stroke="#ffffff" stroke-width="7.0" '
                f'stroke-linejoin="round" stroke-linecap="round" {dash}/>')
        line = (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.2" '
                f'stroke-linejoin="round" stroke-linecap="round" {dash}marker-end="url(#ah_{color.lstrip("#")})"/>')
        return {"color": color, "halo": halo, "line": line,
                "label": e.get("label"), "lab_candidates": r["lab_candidates"]}

    def _place_labels(self, edge_geoms):
        """为连线标签选位：避开节点、分组标题、鹰眼列与已放置的标签，杜绝文字互相覆盖。"""
        obstacles = []
        for n in self.nodes.values():
            obstacles.append((n["x"], n["y"], n["w"], n["h"]))
        for g in self.groups:
            if g["title"]:
                tw = _est_text_w(g["title"], 13) + 8
                obstacles.append((g["x"] + 6, g["y"] + 3, tw, 20))
        if self.monitor_box:
            mb = self.monitor_box
            obstacles.append((mb["x"], mb["y"], mb["w"], mb["h"]))
        placed = []

        def overlaps(r):
            for o in obstacles + placed:
                if not (r[0] + r[2] <= o[0] or o[0] + o[2] <= r[0] or
                        r[1] + r[3] <= o[1] or o[1] + o[3] <= r[1]):
                    return True
            return False

        for g in edge_geoms:
            if not g["label"]:
                continue
            tw = _est_text_w(g["label"], 12.5) + 10
            m = 3
            chosen = None
            for (cx, cy) in g["lab_candidates"]:
                r = (cx - tw / 2 - m, cy - 9 - m, tw + m * 2, 18 + m * 2)
                if not overlaps(r):
                    chosen = (cx, cy, r)
                    break
            if chosen is None:
                cx, cy = g["lab_candidates"][0]
                chosen = (cx, cy, (cx - tw / 2, cy - 9, tw, 18))
            g["label_at"] = (chosen[0], chosen[1])
            g["label_tw"] = tw
            placed.append(chosen[2])

    # ---------- 层级虚线分隔 ----------
    def _render_tiers(self):
        tiers = self.spec.get("tiers")
        if not tiers:
            return
        left = (self.monitor_box["x"] + self.monitor_box["w"] + 12) if self.monitor_box else self.MARGIN
        right = self.width - self.MARGIN
        for t in tiers:
            y = float(t["y"])
            if t.get("line", True):
                self._add(f'<line x1="{left:.1f}" y1="{y:.1f}" x2="{right:.1f}" y2="{y:.1f}" '
                          f'stroke="#9aa0a6" stroke-width="1.2" stroke-dasharray="8,5"/>')
            ty = (y - 7) if t.get("line", True) else y
            self._add(f'<text x="{left:.1f}" y="{ty:.1f}" fill="#55606a" font-size="13" '
                      f'font-weight="700" font-family="{F}" text-anchor="start">{esc(t["label"])}</text>')

    # ---------- 渲染 ----------
    def _render(self):
        self._add(f'<rect x="0" y="0" width="{self.width:.1f}" height="{self.height:.1f}" fill="#ffffff"/>')
        # 背景面板
        for p in self.panels:
            self._add(self._rounded(p["x"], p["y"], p["w"], p["h"], r=10, fill=p["fill"],
                                    stroke=p["stroke"], sw=1.0))
            if p["label"]:
                self._add(f'<text x="{p["x"]+12:.1f}" y="{p["y"]+20:.1f}" fill="{p["text"]}" '
                          f'font-size="14" font-weight="700" font-family="{F}">{esc(p["label"])}</text>')
        # 分组浅色底（只填充；边框与标题最后再画，保证清晰）
        for g in self.groups:
            self._add(self._rounded(g["x"], g["y"], g["w"], g["h"], r=10, fill=g["fill"],
                                    stroke="none", sw=0))
        # 鹰眼监控列
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
        # 层级虚线分隔
        self._render_tiers()
        # 连线：逐条「白晕→彩线」，白晕切断先前线条形成跨线桥；画在节点之下 → 遇盒自动被遮
        edges = self.spec.get("edges", [])
        ports = self._assign_ports(edges)
        edge_geoms = [g for g in (self._edge_geom(e, ports[i][0], ports[i][1])
                                  for i, e in enumerate(edges)) if g]
        self._place_labels(edge_geoms)
        added_marks = set()
        for g in edge_geoms:
            mn = "ah_" + g["color"].lstrip("#")
            if mn not in added_marks:
                self._add(self._arrow_marker(g["color"], mn))
                added_marks.add(mn)
        for g in edge_geoms:
            self._add(g["halo"])
            self._add(g["line"])
        # 节点（盒子 + 文字）画在连线之上 → 跨过矩形的线被遮挡
        for n in self.nodes.values():
            self._add(self._node_box(n))
            self._add(self._node_text(n))
        # 连线标签画在最上层，避免被节点/底色盖住
        for g in edge_geoms:
            if g.get("label"):
                mx, my = g["label_at"]
                tw = g["label_tw"]
                self._add(f'<rect x="{mx-tw/2:.1f}" y="{my-10:.1f}" width="{tw:.1f}" height="19" '
                          f'rx="3" fill="#ffffff" stroke="none" opacity="0.96"/>')
                self._add(f'<text x="{mx:.1f}" y="{my:.1f}" fill="#333" font-size="12.5" '
                          f'font-family="{F}" text-anchor="middle" dominant-baseline="central">{esc(g["label"])}</text>')
        # 分组虚线边框 + 标题（最后画，确保不被连线覆盖）
        for g in self.groups:
            self._add(self._rounded(g["x"], g["y"], g["w"], g["h"], r=10, fill="none",
                                    stroke=g["stroke"], sw=1.2, dash="stroke-dasharray='7,5'"))
            if g["title"]:
                tw = _est_text_w(g["title"], 13) + 12
                self._add(f'<rect x="{g["x"]+6:.1f}" y="{g["y"]+4:.1f}" width="{tw:.1f}" height="19" '
                          f'rx="3" fill="{g["fill"]}" stroke="none"/>')
                self._add(f'<text x="{g["x"]+12:.1f}" y="{g["y"]+15:.1f}" fill="#3a4550" '
                          f'font-size="13" font-weight="700" font-family="{F}">{esc(g["title"])}</text>')
        # 便签
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
