---
name: aceld-websearch
description: 给其他技能供料的「近半年 · 权威 · 高指标文章检索」。当课程制作、公众号写作、架构图、技术选型等技能需要外部参考资料/行业文章/案例/数据，或用户说「找几篇近半年的权威文章」「搜阅读量高、评论多的爆款」「给这个主题配个资料包」时使用。强制滚动 180 天时间窗、T1/T2 权威源分层、可核验的高热度指标（阅读/播放/点赞/评论/收藏/star/赞同）、逐条 WebFetch 验证可读原文链接，产出 pack.md + pack.json 资料包，作为其他 skill 的直接输入。不写正文、不做总结陈词，只交付经核验的可读链接清单。
license: MIT
agent_created: true
metadata:
  author: aceld
  version: "1.0.0"
  homepage: https://github.com/aceld/aceld-skill
---

# aceld-websearch · 近半年 / 权威 / 高指标 / 可读链接

**本技能不写内容，只给其他技能喂料**：产出一份逐条核验过的「可读链接清单」，让下游 skill 有料可用。

<!-- aceld-rollout:begin 开工前置检查 v1 -->
> ### ⚑ 开工前置检查（每次先跑，30 秒）
>
> ```bash
> python ~/.workbuddy-ai/skills/aceld-findskill/scripts/preflight.py "本次任务关键词"
> ```
>
> 出三种结论，照做即可：
> **① 直接用本地 X** → 继续按本技能做；
> **② 本地没有 / 线上更强** → 走 `aceld-findskill` 检索 + 体检，别硬编；
> **③ 上游有更新** → 先看差异再决定。
>
> **为什么强制**：技能生态每周在变，本技能写的做法可能已有更便宜的替代。
> 不检查就开工，等于用去年的地图走今年的路。
<!-- aceld-rollout:end -->

---

## 0. 三条铁律

**铁律一：四条硬门槛，不过就淘汰，绝不「悄悄放宽」。**
`页面发布日期在近 180 天内` + `T1/T2 权威源` + `指标可核验且达阈值` + `链接真能读到正文`。
入选 0 条时，正确动作是**回去补检索 / 换检索式 / 换语言**，不是把阈值调低、把 T3 放进来、把日期放宽。
确实要放宽时，必须显式加 `--allow-t3` / `--allow-waiver` / `--days`，并在交付物里写明「已放宽」。

**铁律二：指标只能抄页面，不能算出来。**
禁止把搜索结果摘要里的「10万+」「约 5 万阅读」当证据，禁止估算、禁止脑补。
每条都要有 `metrics_verified: true` + `metric_source`（写清是哪个页面哪个位置显示的什么计数）。
平台不公开计数 → 该条淘汰，或标 `heat_waiver` 走「权威一手（无公开热度）」独立区，**永不占入选名额**。

**铁律三：链接要能被下游直接打开读到全文。**
短链、快照、AMP、分享中间页、转载聚合页、登录/付费/App 墙一律不收；转载必须回溯到原文。
URL 去跟踪参数后用 `WebFetch` 抓到 ≥2 段正文，才算「可读」。

---

## 1. 触发与边界

| 场景 | 动作 |
|---|---|
| 别的技能要举例、找案例、找数据、找行文角度 | ✅ 本技能出资料包，下游读 `pack.md` |
| 用户说「找几篇近半年的权威/爆款文章，把链接给我」 | ✅ 直接出资料包 |
| 写课程 / 写公众号 / 画架构图 / 做技术选型本身 | ❌ 交给 `course-studio` / `aceld-wechat` / `aceld-diagram`，本技能只供料 |
| 只查一个明确事实（某版本号、某个 API 参数） | ❌ 用一次普通 WebSearch，不必建资料包 |
| 找的是「技能 / 工具」而不是「文章」 | ❌ 走 `aceld-findskill` |

---

## 2. 六步流水线

```
① 定窗口 → ② 三路检索 → ③ 建候选池 → ④ 逐条核验 → ⑤ 过滤评分 → ⑥ 校验交付
```

| 阶段 | 做什么 | 工具 / 脚本 | 产出 |
|---|---|---|---|
| ① 定窗口 | 算出 `since = today-180d`，确定 profile | `scripts/window.py --json` | 窗口 JSON + `freshness=m6` |
| ② 三路检索 | 白名单路 / 开放路 / 中文高热路 | `WebSearch`（`freshness="m6"`）、必要时 `domain_search` | 20~40 条候选摘要 |
| ③ 建候选池 | 只把链接、标题、来源、检索式记下来 | `scripts/rank.py --template` | `candidates.json` 骨架 |
| ④ 逐条核验 | 打开每条：发布日期、作者/机构、公开计数、正文可读性 | `WebFetch`（可并行）、`scripts/urlnorm.py` | 补齐字段的 `candidates.json` |
| ⑤ 过滤评分 | 硬门槛 + 评分 + 去重 + 域名分散 | `scripts/rank.py -i ... -o ...` | `pack.json` + `pack.md` |
| ⑥ 校验交付 | 自检有没有被绕过、md/json 是否一致 | `scripts/verify.py pack.json` | PASS → 交给下游 |

---

## 3. 每步的关键动作

### ① 定窗口（别自己算日期）

```bash
python ~/.workbuddy-ai/skills/aceld-websearch/scripts/window.py --json
```

宿主搜索工具的 `freshness` 只支持 `d1..d30 / m1..m12 / y1..y5`，
**「半年」只能写 `freshness="m6"`**（`d180` 是非法值）。两道窗口取严：

- 搜索侧：`freshness="m6"` 粗筛；
- 脚本侧：`[today-180d, today]` 逐条硬过滤；
- 日期只认**文章页面标注的发布日期**，不认搜索结果的「3 天前」、不认抓取时间、不认「更新于」。

`--profile` 三选一：`tech`（默认，AI/编程技术、中英双语）、`wechat`（中文爆款/选题）、`general`（不预设域名偏好）。阈值见 `assets/sources.json`。

### ② 三路检索（缺一路，就会漏掉一半好文）

对每个主题至少跑 3 条检索式，中英各一路，全部带 `freshness="m6"`：

1. **白名单路**：`WebSearch` + `allowed_domains`（从 `assets/sources.json` 的 T1/T2 挑），把官方博客、工程博客、InfoQ、机器之心这类先捞一遍；
2. **开放路**：`WebSearch` 中英双语关键词 + 年份词（来自 `window.py` 的 `year_tokens`），捞跨平台高传播文章；
3. **高热路**：关键词后加平台与热度词，例如 `2026 复盘 高赞`、`site:zhuanlan.zhihu.com`、`site:mp.weixin.qq.com`、`site:bilibili.com 播放`，专捞中文高互动内容。

需要对行业态势做多源综合时（贵、慢），再补一次 `domain_search`，**查询必须是一句话的高层意图**，字段/排序/过滤一律留给本技能下游处理。
具体检索式模板见 `references/01-sources.md`。

### ③ 建候选池

```bash
python ~/.workbuddy-ai/skills/aceld-websearch/scripts/rank.py --template > candidates.json
```

此阶段**只记事实，不评判**：标题、URL、来源、检索式。不要凭 snippet 里的「10万+」先入为主。
`queries[]` 要留痕（检索式、engine、freshness、限定域、命中数），否则下次无法复现。

### ④ 逐条核验（本技能最贵、也最不能省的一步）

对每条候选 `WebFetch`，只问四件事，回来就填进 `candidates.json`：

| 字段 | 判定 |
|---|---|
| `published` | 页面标注的发布日期；找不到 → 直接淘汰（不猜） |
| `author` / `source` / `tier` | 作者与机构可识别吗？一手还是转载？覆盖域名表判定要写 `tier_reason` |
| `metrics` | 页面**公开显示**的阅读/播放/点赞/评论/收藏/star/赞同各是多少，写进 `metric_source` 说明口径 |
| `readable` | 抓到 ≥2 段正文吗？是否要登录/付费/App？`readable_evidence` 写清证据 |

`WebFetch` 打不开 / 需要登录 / 只有摘要 → `readable: false`，淘汰，不要试图绕过。
URL 先过一遍：`python scripts/urlnorm.py "<url>" --profile tech --json`，它会去跟踪参数、识别短链、付费墙、转载中间页并给权威层级。
**转载页必须回溯原文链接**再填 `url`，不能拿聚合页交差。

### ⑤ 过滤评分

```bash
python ~/.workbuddy-ai/skills/aceld-websearch/scripts/rank.py \
  -i candidates.json -o research/<topic-slug>
```

脚本零依赖、不联网，只做确定性判定：四条硬门槛 → 评分（权威 35 / 热度 35 / 新鲜 20 / 可读与一手 10 / 交叉引用加成 8）
→ 同链接同题去重 → 单域名占比上限（默认 40%，防一个站刷屏）→ Top N。
`--top`、`--days`、`--profile`、`--allow-t3`、`--allow-waiver` 都是显式开关，默认全关。

### ⑥ 校验交付

```bash
python ~/.workbuddy-ai/skills/aceld-websearch/scripts/verify.py research/<topic-slug>/pack.json
```

**看到 `PASS` 才能把资料包交给下游**。FAIL 就回去修候选，不要改脚本迁就数据。

---

## 4. 输出契约（其他 skill 怎么吃这份资料包）

固定产出两个文件，放在同一个目录：

| 文件 | 给谁 | 内容 |
|---|---|---|
| `pack.md` | 人 / 下游 Agent 直接读 | 可读链接清单：链接、来源、层级、发布日期、热度（带口径）、评分、正文摘要、可用作什么、淘汰留痕、检索留痕 |
| `pack.json` | 程序化消费 | `items[].canonical_url`、`published`、`tier`、`metrics`、`metric_source`、`summary`、`value_for`、`score`；另含 `window` / `queries` / `rejected` |

下游技能的三种用法（详见 `references/04-contract.md`）：

1. **直接读**：把 `pack.md` 路径交给下游，让它按链接清单取料；
2. **嵌进提示词**：`python -c` 读出 `items[].canonical_url` 拼成一行塞进下游输入；
3. **批量注入**：用 `aceld-skill-rollout` 把 `references/04-contract.md` 里的哨兵块铺到其他技能的 SKILL.md 顶部，让所有技能默认「缺资料先取包」。

**约定**：资料包是**只读输入**，下游不得改写 `pack.*`；要补充新文章就重跑本技能生成新目录（按主题 slug + 日期）。

---

## 5. 最容易踩的坑

- **拿搜索摘要当证据**：摘要里的「10万+」经常是标题党或旧数据，必须 WebFetch 回原页面抄公开计数。
- **把「更新于」当发布日期**：一篇 2023 年的文章今天改了个错字，不该混进「半年内」。
- **`m6` ≠ 精确 180 天**：`m6` 是最近 6 个日历月，脚本的 180 天窗口才是最终裁判。
- **一个站刷屏**：不加域名限流，Top 8 会有 6 条来自同一个平台，看起来热闹其实信息单一。
- **有全文但没有公开计数**：中文开发者社区（腾讯云 / 阿里云开发者社区等）常见，抓得到正文和发布日期也**不满足「高指标」**；淘汰或换能公开计数的平台，不要因此把 `metrics_verified` 打勾。
- **链接打不开**：微信公众号部分文章、知乎部分回答读不到正文；B站 `WebFetch` 实测常返回 412 风控。读不到就淘汰，别硬塞。
- **指标口径混用**：把「点赞」当「阅读」填进 `views` 会虚增热度；字段名和口径见 `references/02-metrics.md`。
- **为了凑数降阈值**：这是最严重的事故。宁可交付 3 条真材实料，也不交 8 条注水的。

---

## 6. 文件地图

```
skill/
├── SKILL.md                          本页（上岗手册）
├── references/
│   ├── 01-sources.md                 权威分层、域名表、黑名单、检索式模板
│   ├── 02-metrics.md                 指标口径、代理指标、阈值、防编造
│   ├── 03-workflow.md                六步 SOP 细节与踩坑复盘
│   └── 04-contract.md                与下游 skill 的契约 + 可注入哨兵块
├── assets/
│   ├── sources.json                  profile / tier / 黑名单 / 阈值（改这里调策略）
│   └── candidates.example.json      候选池格式样例（数字为占位，勿当真资料）
└── scripts/
    ├── window.py                     时间窗唯一真源
    ├── urlnorm.py                    URL 规范化 + 域名分级 + 原文回溯
    ├── rank.py                       硬过滤 + 评分 + 生成 pack.md/json
    └── verify.py                     交付前自检 PASS/FAIL
```
