# 03 · 六步 SOP 与踩坑复盘

假定所有命令都在技能目录 `~/.workbuddy-ai/skills/aceld-websearch/` 下；把 `S` 设成这个路径更省事：

```bash
S=~/.workbuddy-ai/skills/aceld-websearch
```

---

## ① 定窗口（30 秒）

```bash
python $S/scripts/window.py --json
```

拿到 `since` / `until` / `freshness` / `year_tokens`。挑 profile：

- 技术课 / 技术方案 / 架构 → `tech`
- 公众号选题 / 中文爆款 / 找行文角度 → `wechat`
- 不确定领域、跨行业 → `general`

把窗口写进 `candidates.json` 的 `window`（也可以留空，让 `rank.py` 自动生成）。
**固定基准日**用于复现历史资料包：`python $S/scripts/window.py --as-of 2026-11-05 --days 180 --json`。

---

## ② 三路检索（3~6 条检索式）

见 `01-sources.md` §3。要点复述：

- 每条都带 `freshness="m6"`（`d180` 非法，宿主最多 `d30`）；
- 中英各一路，白名单 / 开放 / 高热三路都要有；
- 年份词用 `year_tokens`，别写死去年的年份；
- 结果不要只看第一页，但也别翻到全是转载的第 5 页。

本阶段产出：20~40 条候选的 **标题 + URL + 来源 + 检索式**。别急着判断好坏。

---

## ③ 建候选池

```bash
python $S/scripts/rank.py --template > research/<topic-slug>/candidates.json
# 或复制 assets/candidates.example.json 改
```

把 ② 的候选一条条填进 `candidates[]`，`queries[]` 留痕。
此时 `metrics_verified` / `readable` 默认全是 `false` —— 这是**故意的**：没核验过的字段不许先打勾。

批量看一眼域名分布：

```bash
python $S/scripts/urlnorm.py --check-list research/<slug>/candidates.json --profile tech
```

短链、付费墙、采集站会在这一步就暴露，省下后面的 WebFetch 次数。

---

## ④ 逐条核验（最贵，别省）

对每条候选：

1. `WebFetch` 打开链接，问四件事（发布日期 / 作者机构 / 公开计数 / 正文可读性）；
2. 用 `urlnorm.py` 规范化 URL，去掉 `utm_*`、`fbclid`、`spm` 等跟踪参数；
3. 若是转载 / AMP / 快照 / 短链 → 回溯原文 URL，重填；
4. 把事实写回 `candidates.json`，`metrics_verified` / `readable` 只在真看到时才设 `true`；
5. 摘要 `summary` 必须基于正文写一句话，禁止复制搜索摘要。

可并行发起多个 `WebFetch`。抓不到正文的，记 `readable: false` + 原因，直接进淘汰区。

### 四问速查

| 问 | 页面证据 | 写进 |
|---|---|---|
| 什么时候发的？ | 标题下的发布日期、JSON-LD `datePublished` | `published` |
| 谁写的？ | 署名 / 公众号名 / 官方博客抬头 | `author` / `source` / `tier` |
| 多火？ | 页面计数栏、互动区 | `metrics` / `metric_source` |
| 能读完吗？ | 抓到 ≥2 段实质正文 | `readable` / `readable_evidence` |

---

## ⑤ 过滤评分

```bash
python $S/scripts/rank.py \
  -i research/<slug>/candidates.json \
  -o research/<slug>/pack \
  --profile tech
```

控制台会打出「候选 N → 入选 M / 备选 / 淘汰」以及**每条淘汰原因**。
这份淘汰清单不是噪音，它是下一轮检索的导航：

| 淘汰原因集中在 | 下一轮怎么补 |
|---|---|
| 超窗 | 年份词写错 / 主题近半年确实没新文；换更细的新术语再搜 |
| T3 / 转载 | 补白名单路，加 `blocked_domains` |
| 主指标不足 | 补高热路，加平台限定与「复盘 / 踩坑 / 高赞」等词 |
| 指标未核验 | 该平台不公开计数 → 换能公开计数的平台，或改 `metric_source` 写清代理指标 |
| 未验证可读 | 换原文链接；打不开就放弃，别绕 |

**入选 0 条时的正确顺序**：补检索 → 换语言 → 换平台 → 换关键词 → 最后才考虑显式放宽
（`--days 210` / `--allow-t3` / `--allow-waiver`），且必须在交付说明里写「已放宽」。
绝不默默改 `sources.json` 的阈值凑数。

---

## ⑥ 校验交付

```bash
python $S/scripts/verify.py research/<slug>/pack/pack.json --today
```

- `PASS` → 把 `pack/` 目录（含 `pack.md` + `pack.json`）交给下游；
- `FAIL` → 按提示修候选重跑 `rank.py`，**不要改 `verify.py` 的规则**；
- `--today` 额外检查基准日是否过期超过 7 天，过期提示重跑检索。

---

## 失败模式复盘表

| 现象 | 根因 | 修法 |
|---|---|---|
| 全是去年的文章 | 只用了 `freshness` 没做脚本硬过滤，或摘要里的「N 天前」是抓取时间 | 两道窗口取严；日期只认页面标注 |
| 阅读数看起来很漂亮，点进去对不上 | 抄了搜索摘要 / 把「10万+」当精确值 | 逐条 WebFetch 抄页面计数，写 `metric_source` |
| Top 8 有 6 条来自同一个站 | 没有域名限流 | `max_domain_share`（默认 0.4）已在 `rank.py` 生效 |
| 同一篇被收两次 | 一个原文链接 + 一个带 utm 的分享链接 | `urlnorm.normalize()` 去跟踪参数后按 canonical 去重 |
| 下游说链接打不开 | 收了短链 / 登录墙 / 分享中间页 | `urlnorm.py` 预检 + WebFetch 正文验证，转载回溯原文 |
| 为了凑够 8 条，把明显不达标的塞进去 | 人为调阈值 | 宁缺毋滥；交付 3 条真的，也不交 8 条注水的 |
| 资料包过两周还在用 | 没记检索留痕、没人重跑 | `queries[]` + `verify.py --today` 提醒刷新 |

---

## 与下游的交接话术（可直接用）

```
资料包已生成并校验 PASS：
  research/<slug>/pack/pack.md   （人读 / 直接取链接）
  research/<slug>/pack/pack.json （items[].canonical_url 供程序消费）
窗口 <since> ~ <until>，profile=<x>，入选 <M> 条，
每条都满足：页面发布日期在窗内 / T1-T2 / 指标可核验且达阈值 / 原文链接可读。
下游请只读，不要改写 pack.*；要补文章请重跑 aceld-websearch。
```
