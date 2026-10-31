#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_diagram.py —— 生成「Aceld 风格」架构图 (SVG)

把一份声明式 spec（JSON / YAML）渲染成扁平、分层、粉彩、带序号标注的架构图，
复刻刘丹冰(Aceld) 工程架构师手绘风。零外部依赖（仅可选 PyYAML）。

用法：
    python gen_diagram.py spec.json                 # 生成 spec.html + spec.svg
    python gen_diagram.py spec.json -o out.html     # 指定 html 输出
    python gen_diagram.py spec.yaml --svg out.svg   # 同时导出 svg

spec 字段见 skill/assets/diagram.example.json
"""
import sys
import os
import json


# ====================== 配色 Token（默认值） ======================
DEFAULT_PALETTE = {
    "consumer":  "#f4c6d4",  # 粉
    "splitter":  "#cfe8cf",  # 浅绿
    "parser":    "#cfe9ef",  # 浅青
    "validator": "#e3d7f1",  # 藕荷
    "scheduler": "#f3e7c9",  # 米黄
    "worker":    "#cfe0f0",  # 浅蓝
    "router":    "#e0dcef",  # 浅紫
    "dao":       "#f6efc9",  # 浅黄
    "kafka":     "#dcdcdc",  # 浅灰
    "default":   "#e8e8e8",
    "monitor":   "#2f6fb0",  # 蓝（鹰眼）
    "redis":     "#ffffff",
    "mysql":     "#33475b",  # 深蓝灰
    "teal":      "#1f8a8a",  # 主层标签 / Kafka
    "red":       "#d9534f",
    "blue":      "#2f6fb0",
    "ink":       "#333333",
    "edge":      "#555555",  # 组件深灰细边
    "dash":      "#bbbbbb",  # 分组浅灰虚线
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


# ====================== XML 转义 ======================
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _split_title(t):
    if "(HashKey" in t:
        i = t.index("(HashKey")
        return [t[:i].strip(), t[i:].strip()]
    if "  " in t:
        return t.split("  ", 1)
    return [t]


# ====================== 渲染 ======================
class Diagram:
    def __init__(self, spec):
        self.spec = spec
        self.pal = dict(DEFAULT_PALETTE)
        self.pal.update(spec.get("palette", {}) or {})
        self.MARGIN = 48
        self.MON_W = 64
        self.NODE_R = 32
        self.STAGE_GAP = 64
        self.PIPE_GAP = 140
        self.GROUP_PAD_X = 30
        self.GROUP_GAP = 44
        self.GROUP_HEADER_H = 54
        self.BOX_W = 158
        self.BOX_H = 50
        self.STORAGE_H = 66
        self.PIPE_START_X = self.MARGIN + self.MON_W + 90
        self.parts = []
        self.pipes = []
        self.group_bounds = []
        self.band_tops = {}
        self._layout()
        self._render()

    # ---------- 布局 ----------
    def _layout(self):
        groups = self.spec.get("groups", [])
        idx = 0
        x_cursor = self.PIPE_START_X
        self.pipes = []
        self.group_bounds = []
        for gi, g in enumerate(groups):
            pls = g.get("pipelines", [])
            xs = []
            for pj, p in enumerate(pls):
                stages = p.get("stages", [])
                self.pipes.append((idx, x_cursor, gi, pj, stages))
                xs.append(x_cursor)
                idx += 1
                x_cursor += self.PIPE_GAP
            if pls:
                left = min(xs) - self.NODE_R - self.GROUP_PAD_X
                right = max(xs) + self.NODE_R + self.GROUP_PAD_X
                self.group_bounds.append((left, right, gi, g.get("title", "")))
                x_cursor += self.GROUP_GAP
        n_pipes = idx
        max_pipe_x = max([p[1] for p in self.pipes], default=self.PIPE_START_X)
        self.content_right = max_pipe_x + self.NODE_R + 40
        self.width = self.content_right + 175 + self.MARGIN

        if self.group_bounds:
            self.span_left = min(b[0] for b in self.group_bounds)
            self.span_right = max(b[1] for b in self.group_bounds)
            self.span_center = (self.span_left + self.span_right) / 2
        else:
            self.span_center = (self.PIPE_START_X + self.content_right) / 2

        y = self.MARGIN
        self.title_y = y + 30
        y += 64 + 12

        self.producer = self.spec.get("producer", [])
        if self.producer:
            self.producer_y = y
            self.band_tops["producer"] = y + self.BOX_H / 2
            y += self.BOX_H + 40
        else:
            self.producer_y = None

        self.groups_top = y + 10
        max_stages = max([len(p[4]) for p in self.pipes], default=1)
        group_h = self.GROUP_HEADER_H + max_stages * self.STAGE_GAP + self.NODE_R + 72
        self.groups_bottom = self.groups_top + group_h
        self.band_tops["groups"] = (self.groups_top + self.groups_bottom) / 2
        y = self.groups_bottom + 14

        self.storage = self.spec.get("storage", [])
        if self.storage:
            self.storage_y = y
            self.band_tops["storage"] = y + self.STORAGE_H / 2
            y += self.STORAGE_H + 44
        else:
            self.storage_y = None

        self.height = y + self.MARGIN

    # ---------- 小工具 ----------
    def _add(self, s):
        self.parts.append(s)

    def _arrow_marker(self):
        return (
            '<defs><marker id="ah" markerWidth="10" markerHeight="10" refX="8" refY="3" '
            'orient="auto" markerUnits="strokeWidth">'
            '<path d="M0,0 L8,3 L0,6 Z" fill="#777"/></marker>'
            '<marker id="aht" markerWidth="10" markerHeight="10" refX="8" refY="3" '
            'orient="auto" markerUnits="strokeWidth">'
            '<path d="M0,0 L8,3 L0,6 Z" fill="{teal}"/></marker></defs>'
        ).format(teal=self.pal["teal"])

    def _rounded(self, x, y, w, h, r=10, fill="#fff", stroke="#555", sw=1.4, dash=None):
        d = dash or ""
        return (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{r}" ry="{r}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {d}/>'
        )

    def _circle_node(self, cx, cy, r, fill, label, stroke=None):
        stroke = stroke or self.pal["edge"]
        self._add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" '
                  f'stroke="{stroke}" stroke-width="1.4"/>')
        self._add(f'<text x="{cx:.1f}" y="{cy:.1f}" fill="{self.pal["ink"]}" '
                  f'font-size="13" font-family="PingFang SC,Microsoft YaHei,Helvetica,Arial,sans-serif" '
                  f'text-anchor="middle" dominant-baseline="central">{esc(label)}</text>')

    def _arrow(self, x1, y1, x2, y2, color="#777", w=1.4, dashed=False, marker="ah"):
        da = 'stroke-dasharray="5,4" ' if dashed else ""
        self._add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                  f'stroke="{color}" stroke-width="{w}" {da}marker-end="url(#{marker})"/>')

    # ---------- 渲染 ----------
    def _render(self):
        F = "PingFang SC,Microsoft YaHei,Helvetica,Arial,sans-serif"
        self._add(f'<rect x="0" y="0" width="{self.width:.1f}" height="{self.height:.1f}" fill="#ffffff"/>')
        self._add(self._arrow_marker())

        meta = self.spec.get("meta", {})
        self._add(f'<text x="{self.MARGIN:.1f}" y="{self.title_y:.1f}" fill="{self.pal["ink"]}" '
                  f'font-size="26" font-weight="700" font-family="{F}">{esc(meta.get("title", "架构图"))}</text>')
        if meta.get("subtitle"):
            self._add(f'<text x="{self.MARGIN:.1f}" y="{self.title_y + 22:.1f}" fill="#888" '
                      f'font-size="14" font-family="{F}">{esc(meta["subtitle"])}</text>')

        # 鹰眼监控列
        mon = self.spec.get("monitor")
        if mon:
            top = (self.producer_y - 6) if self.producer_y is not None else (self.groups_top - 6)
            bottom = (self.storage_y - 6) if self.storage_y is not None else (self.groups_bottom + 6)
            mx = self.MARGIN + 6
            self._add(self._rounded(mx, top, self.MON_W - 12, bottom - top, r=8,
                                    fill=mon.get("fill", self.pal["monitor"]), stroke="none"))
            midy = (top + bottom) / 2
            cxm = mx + (self.MON_W - 12) / 2
            self._add(f'<text x="{cxm:.1f}" y="{midy:.1f}" fill="#fff" font-size="15" font-weight="700" '
                      f'font-family="{F}" text-anchor="middle" dominant-baseline="central" '
                      f'transform="rotate(-90 {cxm:.1f} {midy:.1f})">{esc(mon.get("label", "鹰眼"))}</text>')

        # 接入层（producer 盒子横向居中于 group 跨度）
        if self.producer and self.producer_y is not None:
            n = len(self.producer)
            total_w = n * self.BOX_W + (n - 1) * 40
            start_x = self.span_center - total_w / 2
            ys = self.producer_y
            bx = [start_x + i * (self.BOX_W + 40) for i in range(n)]
            for i, name in enumerate(self.producer):
                self._add(self._rounded(bx[i], ys, self.BOX_W, self.BOX_H, r=10,
                                        fill="#ffffff", stroke=self.pal["edge"], sw=1.4))
                self._add(f'<text x="{bx[i] + self.BOX_W / 2:.1f}" y="{ys + self.BOX_H / 2:.1f}" '
                          f'fill="{self.pal["ink"]}" font-size="16" font-weight="600" font-family="{F}" '
                          f'text-anchor="middle" dominant-baseline="central">{esc(name)}</text>')
                if i > 0:
                    self._arrow(bx[i - 1] + self.BOX_W, ys + self.BOX_H / 2,
                                bx[i], ys + self.BOX_H / 2, color=self.pal["teal"], w=1.6, marker="aht")

            # 接入层 → 处理层：从 producer 行垂直落入每个 group 顶部
            for (left, right, gi, gtitle) in self.group_bounds:
                gcx = (left + right) / 2
                self._arrow(gcx, ys + self.BOX_H, gcx, self.groups_top,
                            color=self.pal["teal"], w=1.5, marker="aht")

        # 处理层（groups）
        for (left, right, gi, gtitle) in self.group_bounds:
            top = self.groups_top
            bottom = self.groups_bottom
            self._add(self._rounded(left, top, right - left, bottom - top, r=12,
                                    fill="none", stroke=self.pal["dash"], sw=1.4,
                                    dash='stroke-dasharray="7,5"'))
            if gtitle:
                lines = _split_title(gtitle)
                cxg = (left + right) / 2
                self._add(f'<text x="{cxg:.1f}" y="{top + 20:.1f}" fill="{self.pal["ink"]}" '
                          f'font-size="12" font-weight="700" font-family="{F}" '
                          f'text-anchor="middle">{esc(lines[0])}</text>')
                if len(lines) > 1:
                    self._add(f'<text x="{cxg:.1f}" y="{top + 37:.1f}" fill="#666" '
                              f'font-size="11" font-family="{F}" '
                              f'text-anchor="middle">{esc(lines[1])}</text>')

        # pipelines（圆点 + 向下箭头 + 拉取框）
        for (pi, x, gi, pj, stages) in self.pipes:
            ys = []
            for si, stage in enumerate(stages):
                cy = self.groups_top + self.GROUP_HEADER_H + self.NODE_R + si * self.STAGE_GAP
                ys.append(cy)
                fill = self.pal.get(stage, self.pal["default"])
                self._circle_node(x, cy, self.NODE_R, fill, stage.capitalize())
                if si > 0:
                    self._arrow(x, ys[si - 1] + self.NODE_R, x, cy - self.NODE_R, color="#888", w=1.3)
            last_y = ys[-1]
            py = last_y + self.NODE_R + 26
            self._add(self._rounded(x - 34, py, 68, 30, r=8, fill="#ffffff",
                                    stroke=self.pal["edge"], sw=1.2))
            self._add(f'<text x="{x:.1f}" y="{py + 15:.1f}" fill="#666" font-size="12" '
                      f'font-family="{F}" text-anchor="middle" dominant-baseline="central">拉取</text>')

        # Kafka teal 标签（右侧，处理层中部，竖排）
        kafka_label = self.spec.get("kafka_label")
        if kafka_label and self.group_bounds:
            ry = (self.groups_top + self.groups_bottom) / 2
            self._add(f'<text x="{self.content_right + 14:.1f}" y="{ry:.1f}" fill="{self.pal["teal"]}" '
                      f'font-size="16" font-weight="700" font-family="{F}" '
                      f'text-anchor="start" dominant-baseline="central" '
                      f'transform="rotate(-90 {self.content_right + 14:.1f} {ry:.1f})">{esc(kafka_label)}</text>')

        # 存储层
        if self.storage and self.storage_y is not None:
            n = len(self.storage)
            total_w = n * 230 + (n - 1) * 30
            start_x = self.span_center - total_w / 2
            for i, s in enumerate(self.storage):
                sx = start_x + i * (230 + 30)
                style = s.get("style", "solid")
                fill = s.get("fill", self.pal["redis"] if style == "dotted" else self.pal["mysql"])
                stroke = self.pal["dash"] if style == "dotted" else "#22303d"
                dash = 'stroke-dasharray="8,5"' if style == "dotted" else ""
                txt = s.get("text", "#ffffff" if style == "solid" else self.pal["ink"])
                self._add(self._rounded(sx, self.storage_y, 230, self.STORAGE_H, r=10,
                                        fill=fill, stroke=stroke, sw=1.6, dash=dash))
                self._add(f'<text x="{sx + 115:.1f}" y="{self.storage_y + self.STORAGE_H / 2:.1f}" '
                          f'fill="{txt}" font-size="18" font-weight="700" font-family="{F}" '
                          f'text-anchor="middle" dominant-baseline="central">{esc(s.get("label", ""))}</text>')
                self._arrow(self.span_center, self.groups_bottom, sx + 115, self.storage_y,
                            color="#888", w=1.4, dashed=True)

        # 右侧 Tier 标签（青色，竖排）
        tier_labels = self.spec.get("tier_labels")
        if tier_labels:
            for name, lab in zip(["producer", "groups", "storage"], tier_labels):
                if name in self.band_tops:
                    ry = self.band_tops[name]
                    self._add(f'<text x="{self.content_right + 52:.1f}" y="{ry:.1f}" fill="{self.pal["teal"]}" '
                              f'font-size="15" font-weight="700" font-family="{F}" '
                              f'text-anchor="start" dominant-baseline="central" '
                              f'transform="rotate(-90 {self.content_right + 52:.1f} {ry:.1f})">{esc(lab)}</text>')

        # 序号标注 callouts
        for c in self.spec.get("callouts", []):
            gi = c.get("group", 0)
            pj = c.get("pipe", 0)
            si = c.get("stage", 0)
            node = next((p for p in self.pipes if p[2] == gi and p[3] == pj), None)
            if not node:
                continue
            x = node[1]
            cy = self.groups_top + self.GROUP_HEADER_H + self.NODE_R + si * self.STAGE_GAP
            side = c.get("side", "left")
            cx = x - self.NODE_R - 20 if side == "left" else x + self.NODE_R + 20
            color = self.pal.get(c.get("color", "red"), self.pal["red"])
            self._add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="13" fill="{color}" stroke="#fff" stroke-width="2"/>')
            self._add(f'<text x="{cx:.1f}" y="{cy:.1f}" fill="#fff" font-size="13" font-weight="700" '
                      f'font-family="Helvetica,Arial,sans-serif" text-anchor="middle" '
                      f'dominant-baseline="central">{c.get("n")}</text>')
            lab = c.get("label")
            if lab:
                lx = cx - 20 if side == "left" else cx + 20
                anchor = "end" if side == "left" else "start"
                self._add(f'<text x="{lx:.1f}" y="{cy - 18:.1f}" fill="{self.pal["ink"]}" font-size="11" '
                          f'font-family="{F}" text-anchor="{anchor}">{esc(lab)}</text>')

        # 自定义连线
        for con in self.spec.get("connectors", []):
            x1, y1 = con["from"]
            x2, y2 = con["to"]
            self._arrow(x1, y1, x2, y2, color=con.get("color", "#888"), w=con.get("w", 1.4),
                        dashed=con.get("dashed", False))
            if con.get("label"):
                self._add(f'<text x="{(x1 + x2) / 2:.1f}" y="{(y1 + y2) / 2 - 4:.1f}" fill="#888" '
                          f'font-size="11" font-family="{F}" text-anchor="middle">{esc(con["label"])}</text>')

    # ---------- 输出 ----------
    def svg(self):
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width:.0f}" '
            f'height="{self.height:.0f}" viewBox="0 0 {self.width:.0f} {self.height:.0f}">'
            + "\n".join(self.parts) + "</svg>"
        )

    def html(self):
        return (
            "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
            "<style>body{margin:0;background:#f5f6f8;display:flex;justify-content:center;"
            "padding:24px;font-family:PingFang SC,Microsoft YaHei,Helvetica,Arial,sans-serif}"
            ".sheet{background:#fff;box-shadow:0 2px 14px rgba(0,0,0,.08);border-radius:8px}</style>"
            "</head><body><div class='sheet'>" + self.svg() + "</div></body></html>"
        )


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
