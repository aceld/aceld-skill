# 02 · 高指标的口径、可见性与防编造

> 用户要的是「观看量多、评论多等等这些高指标的文章」。
> 这份文件解决一个很实际的问题：**不同平台公开的计数根本不是一回事**，
> 硬套同一个字段，要么把好文章冤枉掉，要么把注水文章放进来。

## 1. 字段与口径（填 `metrics` 时别串字段）

| 字段 | 含义 | 允许填什么 |
|---|---|---|
| `views` | 阅读量 / 播放量 | 文章「阅读 N」、视频「播放 N」。**不能把点赞、曝光、粉丝数填进来** |
| `likes` | 点赞 / 喜欢 | 页面显示的赞数 |
| `comments` | 评论数 | 显示的评论条数（不是「精选评论」条数） |
| `shares` | 转发 / 分享 | |
| `favorites` | 收藏 / 在看 | 微信「在看」单独算，别和点赞合并 |
| `stars` | GitHub star | 只用于 `kind: repo` |
| `upvotes` | 赞同 / HN points / Reddit upvotes | 只用于 `kind: post|thread` |
| `citations` | 引用数 | 只用于 `kind: paper`（半年内新论文通常≈0） |
| `coins` / `danmaku` | 投币 / 弹幕 | B站辅助指标，不单独作为主指标 |

主指标按 `kind` 取，见 `assets/sources.json` → `primary_metric`：

| kind | 主指标 | 说明 |
|---|---|---|
| `article` | `views` | 文章看阅读量 |
| `video` | `views` | 视频看播放量 |
| `post` / `thread` | `upvotes` | 社区看赞同 / points |
| `repo` | `stars` | 仓库看 star |
| `paper` | `citations` | 论文看引用 |

## 2. 各平台「到底能看到什么」（实测向）

| 平台 | 公开可见 | 常见坑 |
|---|---|---|
| 微信公众号 `mp.weixin.qq.com` | 点赞 / 在看 / 评论（部分页面）；**阅读数常抓不到** | 抓不到阅读数就别填 `views`，用 `likes`+`comments`+`favorites` 组合，或走 `heat_waiver`/淘汰；「10万+」是显示上限不是精确值 |
| 知乎专栏 / 回答 | 赞同、评论、收藏（多数可见） | 用 `upvotes`，别把赞同当阅读填 `views` |
| 掘金 / SegmentFault / OSChina | 阅读、点赞、评论、收藏 | 阅读数常有，可直接用 `views` |
| InfoQ / 机器之心 / 量子位 | 阅读数（部分站点显示） | 不显示阅读时用点赞/评论，并在 `metric_source` 写明「站点未公开阅读数，采用公开互动数」 |
| 腾讯云开发者社区 / 阿里云开发者社区 | 多数页面**不显示**阅读、点赞、评论计数 | 实测（2026-11-05）`cloud.tencent.com/developer/article/...` 能抓到全文与「发布于 2026-07-01 18:12:53」，但页面无公开计数 → 不填 `views`、不标 `metrics_verified`，按「指标不可得」淘汰；别拿搜索结果里的热度字样凑数 |
| B站 / YouTube | 播放、弹幕、点赞、投币、收藏、评论 | 用 `views` 主指标；YouTube 订阅数不是文章热度。**B站 `WebFetch` 常返回 412 安全风控**（实测 2026-11-05），抓不到就是 `readable: false`，不要硬塞 |
| Hacker News / Reddit | points / upvotes、comments | 用 `upvotes`；HN 的 `points ≈ upvotes - downvotes`，照抄页面即可 |
| GitHub | star、fork、issue、讨论 | 用 `stars`；注意仓库创建时间 ≠ 文章发布日期，发布日期取 Release / 博客公告 |
| arXiv / 期刊 | 通常**没有公开阅读量**，引用数对新论文≈0 | 这类一手权威走 `heat_waiver`，默认不收；确需引用时 `--allow-waiver` 单列 |
| 付费墙 / 需登录 | 什么都没有 | 直接淘汰，不要拿搜索摘要的数字凑 |

> 平台改版很频繁。**每次以 `WebFetch` 当场抓到的页面为准**，不要凭这份表硬填。

## 3. `metric_source` 怎么写才算数

```json
"metrics": {"views": 128000, "likes": 2100, "comments": 486, "favorites": 3400},
"metric_source": "文章页底部公开计数栏（阅读 12.8万 / 赞 2100 / 评论 486 / 收藏 3400），WebFetch 于 2026-11-05 抓取"
```

不合格写法（会被 `verify.py` 拦或应在人工复核时驳回）：

- ❌ `"metric_source": "搜索结果里写的"`
- ❌ `"metrics_verified": true` 但 `metrics` 全是 0 或空
- ❌ `"metric_source": "约 10 万+"`（估算 / 上限值当精确值）
- ❌ 把第三方榜单数字写成「页面公开计数」而不注明榜单名

## 4. 阈值（改策略改 `assets/sources.json`，不要改脚本）

| profile | article | video | post/thread | repo | paper | 最低综合分 | Top N |
|---|---|---|---|---|---|---|---|
| `tech`（默认） | views≥5,000 且 comments≥10 | views≥20,000 且 comments≥30 | upvotes≥100 且 comments≥20 | stars≥300 | citations≥10 | 55 | 8 |
| `wechat` | views≥10,000 且 comments≥20 | views≥30,000 且 comments≥50 | upvotes≥300 且 comments≥30 | stars≥500 | citations≥20 | 58 | 10 |
| `general` | views≥5,000 且 comments≥10 | views≥20,000 且 comments≥30 | upvotes≥100 且 comments≥20 | stars≥300 | citations≥10 | 50 | 8 |

阈值是**硬门槛**，不是打分偏好：`rank.py` 先卡线再评分。
评分里热度用 `log10(1 + 实际值/门槛)` 归一化，所以 100 万阅读比 5 千阅读分更高，但不会一骑绝尘压过权威与新鲜度。

## 5. 代理指标（平台不公开主指标时）

按优先级依次用，且必须在 `metric_source` 里写明用了哪种：

1. 公开互动组合：点赞 / 评论 / 收藏 / 投币 / 弹幕（填全，别只填一个）；
2. 同平台榜单位次（如「知乎热榜第 3」「掘金周榜入选」）→ 写进 `metric_source`，不要伪造数字；
3. 多源交叉出现次数 `cross_refs`：同一篇被 ≥2 个独立站点引用/讨论 → 填 2、3，用于加分；
4. 以上都没有 → `heat_waiver: true`，默认淘汰，`--allow-waiver` 时进「权威一手（无公开热度）」独立区，**不占入选名额**。

## 6. 防注水：热度高但可疑的三种信号

- **评论/阅读比异常**：10 万阅读 0 条评论，或 100 阅读 500 条评论 —— 在 `metric_source` 记一句「互动比异常，疑刷量」，人工复核；
- **时间与热度不匹配**：发布 2 天就 50 万播放，但没有任何外部讨论（`cross_refs=0`）—— 谨慎；
- **内容空转**：正文只有导读 / 目录 / 转载声明，抓不到 ≥2 段实质内容 —— `readable: false` 直接淘汰。

## 7. 一条铁律收尾

**宁可交付 3 条真材实料，也不交 8 条注水的。**
资料包是下游写课、写文章、做技术判断的依据；一个编出来的阅读数，会让整节课的可信度归零。
