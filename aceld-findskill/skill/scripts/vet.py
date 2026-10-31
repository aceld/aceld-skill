#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vet.py —— 单个 Agent Skill 体检：五条硬性淘汰线 + 安全扫描

用法：
    python vet.py anthropics/skills/pdf
    python vet.py anthropics/skills/pdf --json out.json
    python vet.py owner/repo --skill my-skill        # 仓库里技能名不同时
    python vet.py owner/repo/skill --min-stars 50 --max-age-months 24

输出：逐条检查结论 + PASS / WARN / REJECT

依赖：仅标准库。走 https_proxy / http_proxy。
元数据三级降级：api.github.com（60 次/小时，带磁盘缓存）→ ungh.cc 镜像 → raw 文件嗅探。
设 GITHUB_TOKEN 可把第一级提到 5000 次/小时。
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "aceld-findskill/1.0 (+https://github.com/aceld/aceld-skill)"}
TEXT_EXT = {".md", ".py", ".sh", ".ps1", ".js", ".ts", ".mjs", ".cjs", ".json",
            ".yaml", ".yml", ".toml", ".txt", ".rb", ".go", ".bat", ".cmd", ".psm1"}
MAX_FILES = 60
MAX_BYTES = 200_000
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".aceld-skill-inbox", ".cache")
CACHE_TTL = 6 * 3600

# (正则, 等级, 说明)
RULES = [
    (r"ignore\s+(all\s+)?(previous|prior|above)\s+(instruction|prompt|rule)s?", "HIGH", "提示词注入：要求忽略既有指令"),
    (r"忽略(以上|之前|上述|前面)的?(所有)?(指令|限制|规则|提示)", "HIGH", "提示词注入（中文）"),
    (r"disregard\s+(the\s+)?(system|previous|above)", "HIGH", "提示词注入"),
    (r"you\s+are\s+now\s+(a|an)\s+", "MED", "身份覆写话术"),
    (r"curl[^\n|]{0,200}\|\s*(ba)?sh", "HIGH", "curl | bash 远程执行"),
    (r"wget[^\n|]{0,200}\|\s*(ba)?sh", "HIGH", "wget | bash 远程执行"),
    (r"\bInvoke-Expression\b|\biex\s*\(", "HIGH", "PowerShell 动态执行"),
    (r"\bbase64\s+(-d|--decode|-D)\b", "MED", "base64 解码（可能藏载荷）"),
    (r"\beval\s*\(|\bexec\s*\(", "MED", "动态执行"),
    (r"os\.system|subprocess\.(run|Popen|call|check_output)|child_process", "MED", "外部命令调用"),
    (r"\.ssh\b|id_rsa|id_ed25519|\.aws[/\\]credentials|\.netrc|keychain", "HIGH", "读取凭据"),
    (r"\b(AWS_|OPENAI_API_KEY|ANTHROPIC_API_KEY|GITHUB_TOKEN|HF_TOKEN|STRIPE_)", "MED", "触碰密钥环境变量"),
    (r"rm\s+-rf\s+[/~]|Remove-Item[^\n]*-Recurse[^\n]*C:\\", "HIGH", "危险删除"),
    (r"chmod\s+777", "MED", "过宽权限"),
    (r"\b(postinstall|preinstall)\b", "MED", "安装钩子"),
    (r"https?://(bit\.ly|t\.cn|tinyurl\.com|pastebin\.com|transfer\.sh)", "HIGH", "短链（易被换载荷）"),
    (r"https?://[^\s)]+\.(exe|dll|bat|ps1|scr|msi)\b", "HIGH", "直链二进制"),
    (r"\[//\]:\s*#|<!--[\s\S]{0,400}?(ignore|忽略|instead|改为)[\s\S]{0,400}?-->", "MED", "注释区藏指令"),
]
INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]")


# ── 带缓存的取数 ──────────────────────────────────────────────────────
def _ckey(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]


def _cache_get(url):
    p = os.path.join(CACHE_DIR, _ckey(url) + ".json")
    try:
        if time.time() - os.path.getmtime(p) > CACHE_TTL:
            return None
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def _cache_put(url, val):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(os.path.join(CACHE_DIR, _ckey(url) + ".json"), "w", encoding="utf-8") as f:
            json.dump(val, f, ensure_ascii=False)
    except Exception:
        pass


def get(url, raw=False, tries=2, timeout=25, cache=True):
    if cache:
        c = _cache_get(url)
        if c is not None:
            return c
    for k in range(tries):
        req = urllib.request.Request(url, headers=UA)
        tok = os.environ.get("GITHUB_TOKEN")
        if tok and "api.github.com" in url:
            req.add_header("Authorization", "Bearer " + tok)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as f:
                b = f.read()
            v = b.decode("utf-8", "replace")
            v = v if raw else json.loads(v)
            if cache:
                _cache_put(url, v)
            return v
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (403, 429) and k + 1 < tries:
                time.sleep(2); continue
            return None
        except Exception:
            if k + 1 < tries:
                time.sleep(1.2); continue
            return None
    return None


def _license_from_text(t):
    """raw LICENSE 内容嗅探，兜住镜像不返回 license 字段的情况。"""
    h = t[:1200].lower()
    if "apache license" in h and "2.0" in h:
        return "APACHE-2.0"
    if "mit license" in h or re.search(r"permission is hereby granted, free of charge", h):
        return "MIT"
    if "bsd 3-clause" in h or ("redistribution and use in source and binary forms" in h
                               and "neither the name" in h):
        return "BSD-3-CLAUSE"
    if "redistribution and use in source and binary forms" in h:
        return "BSD-2-CLAUSE"
    if "isc license" in h or "permission to use, copy, modify, and/or distribute" in h:
        return "ISC"
    if "mozilla public license" in h:
        return "MPL-2.0"
    if "this is free and unencumbered software released into the public domain" in h:
        return "UNLICENSE"
    if "cc0" in h or "creative commons zero" in h:
        return "CC0-1.0"
    return "NONE"


def repo_meta(owner, repo):
    """api.github.com → ungh.cc → None。返回统一结构。"""
    d = get("https://api.github.com/repos/%s/%s" % (owner, repo))
    if d and "stargazers_count" in d:
        return {"stars": d.get("stargazers_count", 0),
                "license": ((d.get("license") or {}).get("spdx_id") or "NONE").upper(),
                "pushed": (d.get("pushed_at") or "")[:10],
                "branch": d.get("default_branch") or "main",
                "archived": bool(d.get("archived")), "via": "api"}
    d = get("https://ungh.cc/repos/%s/%s" % (owner, repo))
    if d and d.get("repo"):
        r = d["repo"]
        return {"stars": r.get("stars", 0),
                "license": (r.get("license") or "NONE").upper() if isinstance(r.get("license"), str) else "NONE",
                "pushed": (r.get("pushedAt") or "")[:10],
                "branch": r.get("defaultBranch") or "main",
                "archived": False, "via": "ungh"}
    return None


def repo_paths(owner, repo, branch):
    """api tree → ungh files。返回路径列表（无大小信息时用 -1）。"""
    d = get("https://api.github.com/repos/%s/%s/git/trees/%s?recursive=1" % (owner, repo, branch))
    if d and d.get("tree"):
        return [(t["path"], t.get("size", -1)) for t in d["tree"] if t.get("type") == "blob"]
    d = get("https://ungh.cc/repos/%s/%s/files/%s" % (owner, repo, branch))
    if d and d.get("files"):
        return [(f["path"], -1) for f in d["files"]]
    return []


# ── frontmatter（不引 yaml 依赖，只解一层 + 嵌套缩进）──────────────────
def lic_triage(lic):
    """许可分级 → (level, msg)。ok=通过；warn=只读方法别复制；reject=别碰。

    不追求 SPDX 精确，只回答一个实际问题：能不能把它的代码/原文搬进我的技能。
    注意用词边界匹配：'CO-MPL-ETE' 这种子串误判是这类检查最常见的 bug。
    """
    raw = str(lic or "").strip()
    L = raw.upper()
    if not raw or L in ("NONE", "UNKNOWN", "NOASSERTION"):
        return "warn", "无明确许可：只能读它的方法，不能复制它的代码与原文"
    if (re.search(r"\b(NC|ND)\b|NON-?COMMERCIAL|NO-?DERIV|SSPL|BUSL|BSL-1|COMMONS-CLAUSE", L)):
        return "reject", "许可限制商用/改作（%s），不能吸收" % raw[:44]
    if re.search(r"\bA?GPL\b|GENERAL PUBLIC LICENSE", L):
        return "warn", "许可 %s：可读可改写，但分发改写版需同许可" % raw[:44]
    if re.search(r"\bPROPRIETARY\b|ALL RIGHTS RESERVED|COMPLETE TERMS|SEE LICENSE", L):
        return "warn", "专有许可（%s）：只能读方法，不能复制代码与原文" % raw[:44]
    if re.search(r"\bMIT\b|\bAPACHE\b|\bBSD\b|\bISC\b|\bMPL-?2|\bUNLICENSE\b|\bCC0\b|\b0BSD\b|PUBLIC DOMAIN", L):
        return "ok", None
    return "warn", "许可不明（%s）：当无许可处理，只读方法不复制代码" % raw[:44]


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text, "文件不以 --- 开头"
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text, "frontmatter 未闭合"
    block = text[3:end].strip("\n")
    body = text[end + 4:].lstrip("\n")
    meta, cur = {}, None
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", line)
        if m and not line.startswith(" "):
            k, v = m.group(1), m.group(2).strip()
            if v in ("", "|", ">"):
                meta[k] = ""
                cur = k
            else:
                meta[k] = v.strip("'\"")
                cur = None
        elif cur and line.startswith(" "):
            meta[cur] = (meta.get(cur, "") + " " + line.strip()).strip()
    return meta, body, None


def locate(owner, repo, branch, skill):
    """按常见布局猜路径，失败再扫树。返回 (path, content)。"""
    cands = []
    if skill:
        cands += ["%s/SKILL.md" % skill,
                  "skills/%s/SKILL.md" % skill,
                  ".claude/skills/%s/SKILL.md" % skill,
                  "plugins/%s/skills/%s/SKILL.md" % (skill, skill),
                  ".agents/skills/%s/SKILL.md" % skill]
    cands.append("SKILL.md")
    for p in cands:
        c = get("https://raw.githubusercontent.com/%s/%s/%s/%s" % (owner, repo, branch, p), raw=True)
        if c and c.startswith("---"):
            return p, c
    paths = [p for p, _ in repo_paths(owner, repo, branch) if p.endswith("SKILL.md")]
    pick = None
    if skill:
        exact = [p for p in paths if p.split("/")[-2:-1] == [skill]]
        pick = exact[0] if exact else None
        if not pick:
            near = [p for p in paths if skill in p]
            pick = near[0] if len(near) == 1 else None
    if not pick and len(paths) == 1:
        pick = paths[0]
    if not pick:
        return None, None
    return pick, get("https://raw.githubusercontent.com/%s/%s/%s/%s" % (owner, repo, branch, pick), raw=True)


def list_skill_files(owner, repo, branch, skill_dir):
    out = []
    for p, size in repo_paths(owner, repo, branch):
        if skill_dir and not p.startswith(skill_dir.rstrip("/") + "/"):
            continue
        if os.path.splitext(p)[1].lower() in TEXT_EXT and (size < 0 or size <= MAX_BYTES):
            out.append(p)
    return out[:MAX_FILES]


def scan_text(text):
    hits = []
    for pat, lvl, why in RULES:
        for m in re.finditer(pat, text, re.I):
            s = max(0, m.start() - 40)
            hits.append({"level": lvl, "why": why,
                         "snippet": text[s:m.end() + 40].replace("\n", " ")[:160]})
            break
    if INVISIBLE.search(text):
        hits.append({"level": "HIGH", "why": "含不可见字符（零宽/双向覆写，可藏指令）",
                     "snippet": ""})
    return hits


def get_installs(source, skill):
    if not source or not skill:
        return None
    d = get("https://skills.sh/api/search?q=" + urllib.parse.quote(skill))
    if not d:
        return None
    for s in d.get("skills", []):
        if s.get("id") == "%s/%s" % (source, skill):
            return int(s.get("installs") or 0)
    return None


def main():
    ap = argparse.ArgumentParser(description="Agent Skill 体检")
    ap.add_argument("id", help="owner/repo 或 owner/repo/skill")
    ap.add_argument("--skill", default=None, help="技能目录名（id 只给 owner/repo 时用）")
    ap.add_argument("--min-installs", type=int, default=1000)
    ap.add_argument("--min-stars", type=int, default=100)
    ap.add_argument("--max-age-months", type=int, default=12)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    parts = a.id.strip().strip("/").split("/")
    if len(parts) < 2:
        print("!! id 格式应为 owner/repo 或 owner/repo/skill", file=sys.stderr)
        return 2
    owner, repo = parts[0], parts[1]
    skill = a.skill or (parts[2] if len(parts) > 2 else repo)

    fails, warns, sec = [], [], []

    # ── 1. 仓库元数据（三级降级）────────────────────────────────────
    m = repo_meta(owner, repo)
    if not m:
        print("!! 拿不到仓库元数据：%s/%s（网络不通 / 仓库不存在 / API 限流）" % (owner, repo),
              file=sys.stderr)
        print("   国内先 export https_proxy=http://127.0.0.1:7890", file=sys.stderr)
        return 2
    stars, lic, pushed, branch = m["stars"], m["license"], m["pushed"], m["branch"]
    if m["archived"]:
        fails.append("仓库已归档（archived）")

    # ── 2. 定位 SKILL.md ───────────────────────────────────────────
    path, content = locate(owner, repo, branch, skill)
    if not content:
        print("!! 在 %s/%s 里找不到可用的 SKILL.md（skill=%s）" % (owner, repo, skill), file=sys.stderr)
        return 2
    meta, body, ferr = parse_frontmatter(content)
    sdir = os.path.dirname(path)

    # 许可优先级：SKILL.md frontmatter > 仓库 API > 根目录 LICENSE 正文 > package.json
    if meta.get("license"):
        lic = str(meta["license"]).strip().strip("'\"")
    if lic in ("NONE", "", None):
        for ln in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING",
                   "LICENSE-MIT", "LICENSE-APACHE"):
            t = get("https://raw.githubusercontent.com/%s/%s/%s/%s" % (owner, repo, branch, ln), raw=True)
            if t:
                lic = _license_from_text(t)
                break
    if lic in ("NONE", "", None):
        t = get("https://raw.githubusercontent.com/%s/%s/%s/package.json" % (owner, repo, branch), raw=True)
        if t:
            try:
                pj = json.loads(t)
                v = pj.get("license") or (pj.get("licenses") or [{}])[0].get("type")
                if isinstance(v, str) and v:
                    lic = v.upper().replace(" ", "-")
            except Exception:
                pass

    # ── 3. 五条硬性淘汰线 ──────────────────────────────────────────
    name = (meta.get("name") or "").strip()
    desc = (meta.get("description") or "").strip()
    if ferr:
        fails.append("frontmatter 不合法：%s" % ferr)
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name or ""):
        fails.append("name 不合规：%r（要求小写字母数字 + 连字符）" % name)
    elif len(name) > 64:
        fails.append("name 超过 64 字符")
    elif sdir and os.path.basename(sdir) != name:
        warns.append("name(%s) 与目录名(%s) 不一致（安装后可能加载不到）"
                     % (name, os.path.basename(sdir)))
    if not (1 <= len(desc) <= 1024):
        fails.append("description 长度 %d，要求 1–1024" % len(desc))
    elif re.match(r"^(I|We|You)\b", desc):
        warns.append("description 用了第一/第二人称（规范建议第三人称 + 触发关键词）")

    ll, lm = lic_triage(lic)
    if ll == "reject":
        fails.append(lm)
    elif ll == "warn":
        warns.append(lm)

    try:
        months = (time.time() - time.mktime(time.strptime(pushed, "%Y-%m-%d"))) / 86400 / 30.4
    except Exception:
        months = 999
    if months > a.max_age_months:
        fails.append("最后提交 %s（%.1f 个月前 > %d 个月）" % (pushed, months, a.max_age_months))

    inst = get_installs("%s/%s" % (owner, repo), skill)
    if inst is None and stars < a.min_stars:
        fails.append("既查不到安装量，星标也只有 %d（< %d）" % (stars, a.min_stars))
    elif inst is not None and inst < a.min_installs and stars < a.min_stars:
        fails.append("安装量 %d（< %d）且星标 %d（< %d）"
                     % (inst, a.min_installs, stars, a.min_stars))

    lines = body.count("\n") + 1
    tokens = len(body) / 2.2                       # 中文保守估
    if lines > 500:
        warns.append("正文 %d 行（建议 <500，超出部分应下沉到 references/）" % lines)
    if tokens > 5000:
        warns.append("正文约 %d tokens（建议 <5000）" % tokens)
    if re.search(r"(?<![\w/])(?:[A-Z]:\\|/Users/|/home/[a-z])", body):
        warns.append("正文含绝对路径（换机器就废）")

    # ── 4. 安全扫描 ────────────────────────────────────────────────
    files = list_skill_files(owner, repo, branch, sdir) or [path]
    for p in files:
        t = get("https://raw.githubusercontent.com/%s/%s/%s/%s" % (owner, repo, branch, p), raw=True)
        if not t:
            continue
        for h in scan_text(t):
            h["file"] = p
            sec.append(h)

    high = [h for h in sec if h["level"] == "HIGH"]
    med = [h for h in sec if h["level"] == "MED"]

    # ── 5. 结论 ───────────────────────────────────────────────────
    if fails or high:
        verdict = "REJECT"
    elif warns or med:
        verdict = "WARN"
    else:
        verdict = "PASS"

    print("=" * 78)
    print("体检对象  %s/%s/%s" % (owner, repo, skill))
    print("SKILL.md  %s（%d 行正文）" % (path, lines))
    print("仓库      ★%d  许可 %s  最后提交 %s（%.1f 个月前）%s   [%s]"
          % (stars, lic, pushed, months,
             "  [archived]" if m["archived"] else "", m["via"]))
    print("安装量    %s" % ("-" if inst is None else inst))
    print("frontmatter  name=%r  desc=%d 字" % (name, len(desc)))
    print("=" * 78)

    def dump(title, items, fmt):
        print("\n%s" % title)
        if not items:
            print("  ✓ 无")
            return
        for it in items:
            print(fmt(it))

    dump("硬性淘汰", fails, lambda x: "  ✗ %s" % x)
    dump("风险提示", warns, lambda x: "  ! %s" % x)
    dump("安全扫描", sec,
         lambda h: "  [%s] %s  %s\n        %s" % (h["level"], h["file"], h["why"], h["snippet"]))

    print("\n结论：%s" % verdict)
    if verdict == "REJECT":
        print("  → 不要进 inbox。除非你能逐条解释并接受上面的每一个 ✗。")
    elif verdict == "WARN":
        print("  → 可以进 inbox 阅读，但吸收前必须人工复核上面的 ! 与 MED 项。")
    else:
        print("  → 可以进 inbox：python absorb.py %s/%s/%s" % (owner, repo, skill))

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"id": a.id, "verdict": verdict, "path": path,
                       "stars": stars, "license": lic, "pushed": pushed,
                       "installs": inst, "frontmatter": meta,
                       "fails": fails, "warns": warns, "security": sec},
                      f, ensure_ascii=False, indent=1)
        print("\nJSON → %s" % a.json)
    return 0 if verdict != "REJECT" else 1


if __name__ == "__main__":
    sys.exit(main())
