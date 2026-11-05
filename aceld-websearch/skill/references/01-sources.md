# 01 · 权威源分层与检索式

## 1. 三层权威，判的是「谁在说话」，不是「域名好不好看」

| 层级 | 定义 | 典型 | 默认 |
|---|---|---|---|
| **T1 一手 / 官方** | 作者就是当事方，内容可被追责 | 官方文档与博客、RFC / 规范、论文（arXiv / ACM / IEEE）、公司工程博客（Cloudflare / Netflix / Stripe / GitHub）、官方 GitHub 仓库与 Release、机构报告 | ✅ 收 |
| **T2 权威二手** | 有编辑审核或可识别的资深作者，原创、非转载 | InfoQ、机器之心、量子位、少数派、36氪、极客公园、The Verge、Ars Technica、MIT Tech Review、Hacker News 高分原帖、知乎专栏优质长文、掘金优质作者原创、B站/YouTube 原创深度视频 | ✅ 收 |
| **T3 一般 UGC / 聚合** | 无审核、常转载、SEO 导向 | CSDN 大部分、博客园、百家号、搜狐号、网易号转载、简书、Medium 个人博客、百家/头条聚合 | ❌ 默认淘汰（`--allow-t3` 才开） |

**域名表只是起点**：`assets/sources.json` 里的 `domains` 用来自动判定，`urlnorm.py` 做精确命中 + 子域命中
（`blog.cloudflare.com` 命中 `cloudflare.com`）。要覆盖判定，在 `candidates.json` 里写 `tier` **并必须写 `tier_reason`**：

```json
"tier": "T1",
"tier_reason": "该文是 Kubernetes 官方博客的发布公告，作者即项目维护方"
```

未分类域名（`UNKNOWN`）按 T3 处理。宁可淘汰，也不要给「看着像官网其实是采集站」的链接开绿灯。

## 2. 黑名单（直接判不可读，不必再 WebFetch）

`assets/sources.json` → `blocked_domains`，分三类：

- **短链 / 跳转**：`t.cn`、`bit.ly`、`dwz.cn`、`url.cn`、`b23.tv`、`v.douyin.com` —— 必须展开成原文链接再填 `url`；
- **付费墙 / 需登录**：WSJ、FT、Bloomberg、The Information、财新 —— 下游打不开，等于没给；
- **文库 / 快照 / 采集**：百度文库、百度快照、docin、doc88、book118 —— 不是原文，且常有版权与洗稿问题。

`urlnorm.py` 还会标记「疑似非原文」特征：`/amp/`、跳转中间页、`/s/` 短链页、`?from=timeline` 分享页、快照页。
命中就回溯原文，不要试图把中间页交差。

## 3. 三路检索式模板

所有检索都带 `freshness="m6"`；`year_tokens` 从 `window.py --json` 取（当前一般是 `2026 / 2025`）。

### 第 1 路：白名单路（找权威）

```
WebSearch(query="<主题 中文> 2026 实践 复盘", freshness="m6",
          allowed_domains=["infoq.cn","jiqizhixin.com","qbitai.com","sspai.com"])
WebSearch(query="<topic english> engineering blog 2026", freshness="m6",
          allowed_domains=["github.blog","blog.cloudflare.com","anthropic.com","openai.com"])
```

`allowed_domains` 一次别塞太多（4~6 个），否则召回被压得很窄。官方技术主题可再加一路 `arxiv.org` / `modelcontextprotocol.io`。

### 第 2 路：开放路（找传播广度）

```
WebSearch(query="<主题 中文> 2026 最佳实践 踩坑", freshness="m6")
WebSearch(query="<topic english> 2026 lessons learned production", freshness="m6")
WebSearch(query="<主题> 近半年 高赞 长文 2026", freshness="m6")
```

开放路负责「搜到那些不在白名单里但真的火了的文章」。命中后用 `urlnorm.py` 判层级，别因为没在白名单就丢掉 ——
也别因为排在第一就收下。

### 第 3 路：高热路（找中文高互动）

```
WebSearch(query="site:zhuanlan.zhihu.com <主题> 2026 复盘", freshness="m6")
WebSearch(query="site:mp.weixin.qq.com <主题> 10万+ 2026", freshness="m6")
WebSearch(query="site:bilibili.com <主题> 播放 2026", freshness="m6")
WebSearch(query="<topic> site:news.ycombinator.com 2026", freshness="m6")
```

> 「10万+」只是**检索词**，不是证据。真数字必须回页面抄，见 `02-metrics.md`。

### blocked_domains 的用法

发现某个采集站反复刷屏时，直接在这一路的检索里排掉：

```
WebSearch(query="...", freshness="m6",
          blocked_domains=["baijiahao.baidu.com","sohu.com","163.com"])
```

### domain_search 什么时候用

只用于「需要多源综合判断行业态势」的主题（例如「AI Agent 教育市场 2026 现状」），
它慢、贵，且**查询必须是一句话的高层意图**：

```
domain_search(query="研究 AI Agent 在工程团队中的落地现状")
```

不要在里面写「要字段、要排序、要近半年、要 Top 8」——过滤和排序是 `rank.py` 的活。
拿回来的 raw results 当作**额外候选**，同样要过第 ④ 步逐条核验，不能因为来自「权威检索」就免检。

## 4. 检索留痕

每条检索都记进 `candidates.json` 的 `queries[]`：

```json
{"query": "AI Agent 工程化 2026 复盘", "engine": "WebSearch",
 "freshness": "m6", "allowed_domains": ["infoq.cn"], "hits": 12,
 "note": "中文技术媒体路；第 2 页之后基本是转载，停"}
```

留痕的意义：`verify.py` 会检查它非空，`pack.md` 会原样输出 —— 下次换主题、换时间能照着重跑，
也能一眼看出「入选 0 条」到底是主题太冷，还是检索式写窄了。

## 5. 覆盖率自查

三路跑完，用这个表检查一下再进第 ④ 步：

| 检查项 | 不达标时 |
|---|---|
| 候选 ≥ 15 条 | 关键词太窄 → 换同义词 / 去掉限定词再来一轮 |
| 至少 2 个不同域名进候选 | 全是一个站 → 加 `blocked_domains` 或换平台路 |
| 中英候选都有 | 只有中文 → 补英文开放路，技术主题尤其 |
| 至少 3 条发布日期可初步确认在半年内 | 全是老文 → 年份词写错 / 该主题确实近半年没热度 |
| 有 T1 候选 ≥ 1 | 全是二手解读 → 补白名单官方路 |

（初步确认即可，最终以第 ④ 步 WebFetch 的页面日期为准。）
