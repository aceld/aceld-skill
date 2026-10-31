# 02 · 检索源与真实 API

> 全部接口 2026-10 实测可用。国内直连 github 会被 SNI 拦，先设代理：
> `export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890`

---

## 1. skills.sh —— 首选，唯一有「真实安装量」的源

技能市场榜单，安装量来自 CLI 上报，是目前最可信的「有人真在用」信号。

```bash
curl "https://skills.sh/api/search?q=pdf"
```

```json
{"query":"pdf","searchType":"fuzzy","searchVersion":"algolia",
 "skills":[{"id":"anthropics/skills/pdf","source":"anthropics/skills",
            "skillId":"pdf","name":"pdf","installs":219996}],
 "count":..., "duration_ms":...}
```

- `id` = `owner/repo/skillId`，**直接喂给 `vet.py`**
- `installs` 分档看：>10 万是生态级（几乎肯定经过大量实战）、1 万~10 万是主流、1 千~1 万是小众但可用、<1 千基本是个人试验
- 模糊搜索，中文也能搜到少量，但英文命中率高得多
- 没有返回 description / license / stars，这些要 `vet.py` 去补

**榜单页**：`https://skills.sh/` 首屏是安装量榜，适合「我不知道要什么，先看看有什么」的探索场景。
**详情页**：`https://skills.sh/{owner}/{repo}/{skillId}`，含正文渲染版，读起来比 raw markdown 舒服。

---

## 2. GitHub —— 找「技能合集仓库」和读源码

### 2.1 仓库搜索（匿名可用）

```bash
curl -H "Accept: application/vnd.github+json" \
  "https://api.github.com/search/repositories?q=agent+skills+in:name,description&sort=stars&order=desc&per_page=10"
```

返回 `full_name / stargazers_count / license.spdx_id / pushed_at / default_branch`。

**坑**：`in:readme` 会把 awesome-go 这种无关大仓库排到最前。只用 `in:name,description`，
再按「名字或描述里有没有 skill/agent/plugin」过滤一遍。

### 2.2 代码搜索（**必须带 token**）

```bash
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
  "https://api.github.com/search/code?q=filename:SKILL.md+path:skills"
```

匿名访问返回 401。有 token 后这是**找具体技能最准的一招**——
直接列出全 GitHub 上某个关键词附近的 `SKILL.md`。

### 2.3 定位 SKILL.md（无 token 也能做）

```bash
# 猜路径，命中率很高，顺序试
raw.githubusercontent.com/{owner}/{repo}/{branch}/{skill}/SKILL.md
raw.githubusercontent.com/{owner}/{repo}/{branch}/skills/{skill}/SKILL.md
raw.githubusercontent.com/{owner}/{repo}/{branch}/.claude/skills/{skill}/SKILL.md
raw.githubusercontent.com/{owner}/{repo}/{branch}/plugins/{skill}/skills/{skill}/SKILL.md

# 猜不中就扫树
curl "https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1" | grep SKILL.md
```

`raw.githubusercontent.com` 基本不限流，是**读内容的主通道**。

---

## 3. ungh.cc —— GitHub API 的免费镜像（限流时的救命稻草）

```bash
curl https://ungh.cc/repos/{owner}/{repo}
# → {"repo":{"stars":185315,"pushedAt":"...","defaultBranch":"main",...}}

curl https://ungh.cc/repos/{owner}/{repo}/files/{branch}
# → {"files":[{"path":"skills/pdf/SKILL.md"},...]}
```

- 不返回 `license` 字段（`vet.py` 会退到读 LICENSE 正文 / package.json）
- 不返回 `archived`
- **没有搜索接口**，只能查已知仓库

用途：`api.github.com` 匿名 60 次/小时用完后的降级路径。`vet.py` 已内置三级降级。

---

## 4. npx skills —— 官方 CLI（装了 Node 才有）

```bash
npx skills find "pdf"          # 搜索
npx skills add owner/repo      # 安装（★ 本技能不自动调这个）
npx skills check               # 查已装技能的更新
npx skills list                # 列出已装
```

需要 Node ≥ 22.20。搜索结果是人读格式，解析不稳定，`find.py` 只做尽力解析，不依赖它。

**`npx skills add` 会真的写盘**——本技能的流程里，安装永远是人的决定，脚本不代劳。

---

## 5. 定向找法（知道要找什么的时候最快）

| 场景 | 打法 |
|---|---|
| 已知某个团队做得好 | 直接 `vet.py {org}/skills/{skill}`，如 `anthropics/skills/pdf`、`openai/skills/pdf` |
| 想看某个主题的生态 | `find.py "关键词" --source skills.sh --limit 30`，按安装量看头部 |
| 想找方法论而非代码 | GitHub 搜 `filename:SKILL.md path:references` 或搜 `prompt` `checklist` `guidelines` |
| 找某语言的实现 | GitHub 搜 `language:python filename:SKILL.md` |
| 找榜单之外的 | `https://skills.sh/` 按分类翻，或看 awesome-agent-skills 类仓库 |

---

## 6. 限流与配额（务必知道）

| 通道 | 匿名 | 带 token |
|---|---|---|
| `api.github.com` REST | 60 次/小时 | 5000 次/小时 |
| `api.github.com` search | 10 次/分钟 | 30 次/分钟 |
| `raw.githubusercontent.com` | 基本不限 | 同 |
| `ungh.cc` | 无公开限制 | 同 |
| `skills.sh/api` | 无公开限制 | 同 |

`vet.py` 对 API 响应做 6 小时磁盘缓存（`~/.aceld-skill-inbox/.cache/`），
重复体检同一个技能不会重复消耗配额。批量体检十几个技能时，**先 export GITHUB_TOKEN**。
