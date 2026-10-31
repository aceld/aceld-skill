# -*- coding: utf-8 -*-
"""配置加载：整个流水线唯一的路径与参数来源。

所有脚本都从这里取配置，不要在业务脚本里硬编码路径。
查找顺序：
  1. 环境变量 COURSE_CONFIG 指定的文件
  2. 从当前工作目录向上逐级查找 course.yaml / course.yml
  3. 仓库内置的 assets/course.example.yaml（仅作兜底，值为占位符）

环境变量覆盖（优先级最高）：
  COURSE_AUTHOR / COURSE_FFMPEG / COURSE_VOICE_REF / COURSE_ROOT ...
  规则：COURSE_ + 配置键的大写路径（点换下划线），例如 COURSE_PATHS_FFMPEG
"""
from __future__ import annotations

import os
import copy

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets")
CONFIG_NAMES = ("course.yaml", "course.yml", "course.json")

DEFAULTS = {
    "author": "Your Name",
    "course_title": "My Course",
    "lesson_label": "第 {n} 课",
    "signature": "我是{author}，我们下节课，不见不散",
    "theme": {"mode": "plain", "file": ""},
    "voice": {
        "engine": "cosyvoice2",
        "ref_file": "assets/voice_ref/my_voice.wav",
        "ref_text": "",
        "speed": 1.0,
        "gap_sent": 0.60,
        "repl": [],
    },
    "paths": {
        "root": ".",
        "ffmpeg": "ffmpeg",
        "ffprobe": "ffprobe",
        "chrome_channel": "chrome",
        "cosyvoice": "./tts_engines/CosyVoice",
        "cosyvoice_model": "./tts_engines/pretrained_models/CosyVoice2-0.5B",
        "whisper_model": "large-v3",
    },
    "video": {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "tail": 0.70,
        "crf": 19,
        "preset": "medium",
        "avatar": None,
        "avatar_box": [1500, 840, 420, 240],
    },
    "subtitle": {
        "font": "Microsoft YaHei",
        "size": 44,
        "max_chars": 20,
        "band": True,
    },
    "output": {"dir": "dist"},
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def find_config(start: str | None = None) -> str | None:
    """从 start（默认 cwd）向上逐级查找配置文件。"""
    env = os.environ.get("COURSE_CONFIG")
    if env and os.path.exists(env):
        return os.path.abspath(env)

    cur = os.path.abspath(start or os.getcwd())
    for _ in range(12):
        for name in CONFIG_NAMES:
            p = os.path.join(cur, name)
            if os.path.exists(p):
                return p
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


class Config:
    """点号访问的配置对象：cfg["video.width"] / cfg.get("video.width", 30)"""

    def __init__(self, data: dict, path: str | None = None):
        self.data = data
        self.file = path          # 配置文件路径（注意：不要叫 self.path，会和方法名冲突）

    # ---------- 读取 ----------
    def get(self, dotted: str, default=None):
        node = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def __getitem__(self, dotted: str):
        return self.get(dotted)

    # ---------- 便捷取值 ----------
    @property
    def root(self) -> str:
        """课程工程根目录（绝对路径）。配置里的相对路径都相对它解析。"""
        r = self.get("paths.root", ".")
        if not os.path.isabs(r):
            base = os.path.dirname(self.file) if self.file else os.getcwd()
            r = os.path.join(base, r)
        return os.path.abspath(r)

    def path(self, dotted: str, default: str = "") -> str:
        """取路径类配置，相对路径按 root 解析；找不到可执行文件时回退到裸命令名。"""
        v = self.get(dotted, default)
        if not v:
            return default
        if os.path.isabs(v):
            return v
        cand = os.path.join(self.root, v)
        if os.path.exists(cand):
            return os.path.abspath(cand)
        # 允许直接写 PATH 上的命令名，如 ffmpeg
        return v

    def text(self, dotted: str, default: str = "") -> str:
        v = self.get(dotted, default)
        return "" if v is None else str(v)

    def signature(self) -> str:
        return self.text("signature").format(author=self.text("author"))

    def lesson_label(self, n: int | str) -> str:
        return self.text("lesson_label", "第 {n} 课").format(n=n)

    def repl(self) -> list[tuple[str, str]]:
        """发音替换表：[[原文, 替换], ...] → [(原文, 替换), ...]"""
        out = []
        for item in self.get("voice.repl") or []:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                out.append((str(item[0]), str(item[1])))
        return out

    # ---------- 主题 ----------
    def theme_terms(self) -> dict[str, str]:
        """世界观术语映射；plain 模式返回空 dict。"""
        if self.text("theme.mode", "plain") == "plain":
            return {}
        f = self.text("theme.file")
        if not f:
            return {}
        p = f if os.path.isabs(f) else os.path.join(self.root, f)
        if not os.path.exists(p):
            return {}
        data = _load_file(p) or {}
        return {str(k): str(v) for k, v in (data.get("terms") or {}).items()}

    def __repr__(self) -> str:
        return f"<Config {self.file or '(defaults)'} root={self.root}>"


def _load_file(path: str) -> dict:
    if path.endswith(".json"):
        import json
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if yaml is not None:
        return yaml.safe_load(text) or {}
    # 没有 PyYAML 时用内置的极简解析器（支持本项目的 course.yaml 子集）
    return _mini_yaml(text)


# ---------------- 极简 YAML 兜底解析 ----------------
# 只支持：注释、key: value、缩进嵌套、- 列表、[a, b] 行内列表、引号字符串、数字/布尔/null

def _strip_comment(line: str) -> str:
    q = None
    for i, ch in enumerate(line):
        if q:
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


def _scalar(v: str):
    v = v.strip()
    if not v:
        return None
    if (v[0] == v[-1]) and v[0] in "\"'" and len(v) >= 2:
        body = v[1:-1]
        return body.replace("\\n", "\n") if v[0] == '"' else body
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        items, buf, q = [], "", None
        for ch in inner:
            if q:
                buf += ch
                if ch == q:
                    q = None
            elif ch in "\"'":
                q = ch
                buf += ch
            elif ch == ",":
                items.append(_scalar(buf))
                buf = ""
            else:
                buf += ch
        if buf.strip():
            items.append(_scalar(buf))
        return items
    low = v.lower()
    if low in ("null", "none", "~"):
        return None
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


def _mini_yaml(text: str):
    rows = []
    for raw in text.splitlines():
        s = _strip_comment(raw).rstrip()
        if not s.strip():
            continue
        indent = len(s) - len(s.lstrip(" "))
        rows.append((indent, s.strip()))
    if not rows:
        return {}

    def parse(i, indent):
        """解析 indent 层的块，返回 (对象, 下一个下标)"""
        # 判断是列表还是字典
        is_list = rows[i][1].startswith("- ")
        obj = [] if is_list else {}
        while i < len(rows):
            ind, content = rows[i]
            if ind < indent:
                break
            if ind > indent:                     # 意外缩进，跳过
                i += 1
                continue
            if content.startswith("- "):
                if not is_list:
                    break
                obj.append(_scalar(content[2:]))
                i += 1
            else:
                if is_list:
                    break
                if ":" not in content:
                    i += 1
                    continue
                key, _, val = content.partition(":")
                key = key.strip().strip("\"'")
                val = val.strip()
                if val:
                    obj[key] = _scalar(val)
                    i += 1
                else:
                    # 空值：看下一行的缩进和类型决定是 dict 还是 list
                    if i + 1 < len(rows) and rows[i + 1][0] > indent:
                        child, i = parse(i + 1, rows[i + 1][0])
                        obj[key] = child
                    else:
                        obj[key] = None
                        i += 1
        return obj, i

    result, _ = parse(0, rows[0][0])
    return result


def _apply_env(data: dict) -> dict:
    """COURSE_PATHS_FFMPEG=xxx → data["paths"]["ffmpeg"] = xxx"""
    for key, val in os.environ.items():
        if not key.startswith("COURSE_") or key == "COURSE_CONFIG":
            continue
        parts = key[len("COURSE_"):].lower().split("_")
        # 逐层深入；若中间层不存在就跳过（避免把 COURSE_VIDEO_FPS 错插到别处）
        node = data
        ok = True
        for p in parts[:-1]:
            if isinstance(node, dict) and p in node:
                node = node[p]
            else:
                ok = False
                break
        if ok and isinstance(node, dict) and parts[-1] in node:
            node[parts[-1]] = val
    return data


def load(path: str | None = None) -> Config:
    p = path or find_config()
    data = copy.deepcopy(DEFAULTS)
    if p and os.path.exists(p):
        data = _deep_merge(data, _load_file(p))
    data = _apply_env(data)
    return Config(data, p)


_cached: Config | None = None


def cfg() -> Config:
    """进程内单例，避免每个脚本重复解析。"""
    global _cached
    if _cached is None:
        _cached = load()
    return _cached


if __name__ == "__main__":
    c = cfg()
    print("配置文件：", c.file or "(使用默认值)")
    print("工程根目录：", c.root)
    print("署名：", c.text("author"))
    print("ffmpeg：", c.path("paths.ffmpeg"))
    print("音色参考：", c.path("voice.ref_file"))
    print("画幅：%sx%s @%sfps" % (c.get("video.width"), c.get("video.height"), c.get("video.fps")))
