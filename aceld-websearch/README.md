# aceld-websearch · 给其他技能供料的文章检索

**近半年 · 权威 · 高指标 · 可读链接**。本技能不写正文，只产一份逐条核验过的
「可读链接清单」，作为 `course-studio` / `aceld-wechat` / `aceld-diagram` 等其他 skill 的**输入**。

## 解决什么问题

写课、写公众号、做技术选型时，最容易糊弄过去的一步就是「找几篇参考文章」：
随手搜两条、拿搜索摘要里的「10万+」当热度、链接点开要登录、文章其实是两年前的。
结果下游整篇内容都建立在一份没核过的料上。

`aceld-websearch` 把这一步变成可复现、可校验的流水线：

| 硬门槛 | 怎么保证 |
|---|---|
| **半年内** | `window.py` 算 `today-180d`，搜索侧 `freshness=m6` 粗筛，脚本侧逐条硬过滤；只认页面标注的发布日期 |
| **权威** | T1 一手官方 / T2 编辑审核或可识别作者；T3 聚合转载默认淘汰；短链、付费墙、快照、转载页直接不收 |
| **高指标** | 阅读 / 播放 / 点赞 / 评论 / 收藏 / star / 赞同，必须来自页面公开计数并写明口径，达阈值才入选；禁止估算 |
| **可读链接** | URL 去跟踪参数、回溯原文，`WebFetch` 抓到 ≥2 段正文才算数 |

## 一分钟跑通

```bash
S=~/.workbuddy-ai/skills/aceld-websearch

# ① 时间窗（也是唯一允许算日期的地方）
python $S/scripts/window.py --json

# ② 三路检索 → 填 candidates.json（模板 / 格式样例）
python $S/scripts/rank.py --template > research/ai-agent/candidates.json
#    检索用宿主 WebSearch，全部带 freshness="m6"；
#    每条候选再用 WebFetch 补齐 published / tier / metrics / readable

# ③ 硬过滤 + 评分 + 生成资料包
python $S/scripts/rank.py -i research/ai-agent/candidates.json -o research/ai-agent/pack

# ④ PASS 才允许交给下游
python $S/scripts/verify.py research/ai-agent/pack/pack.json
```

零第三方依赖，Python 3.8+ 即可；脚本不联网，联网检索与页面核验交给宿主的 `WebSearch` / `WebFetch`。

## 产物长这样

`pack.md`（节选）：

```markdown
## 入选链接（按综合分排序）

### 1. 我们把 Agent 搬进生产环境后踩过的 7 个坑

- 🔗 **可读链接**：<https://www.infoq.cn/article/...>
- 来源：InfoQ｜层级：T2｜类型：文章｜发布：2026-09-18（48 天前）
- 热度：**阅读/播放 12.8万 · 点赞 2100 · 评论 486 · 收藏 3400**（口径：文章页公开计数栏，WebFetch 于 2026-11-05 抓取）
- 评分：`77.4`（权威 24.0 / 热度 20.3 / 新鲜 16.1）
- 摘要：作者复盘了工具调用超时、上下文膨胀与重试风暴，给出可落地的降级策略。
- 可用作：课程案例 / 反面教材
```

同目录还有 `pack.json`：`items[].canonical_url` 供程序消费。完整字段契约见
[`skill/references/04-contract.md`](skill/references/04-contract.md)。

## 与其他技能怎么配合

- **人 / Agent 读**：把 `pack.md` 路径交给下游，直接取「入选链接」区里的链接；
- **程序读**：读 `pack.json` 的 `items[]`，见 `04-contract.md` 的三种消费方式；
- **批量铺开**：`04-contract.md` 里给了可注入的「资料检索」哨兵块，
  用 `aceld-skill-rollout` 幂等插到各技能 SKILL.md 前 30 行，让所有技能默认「缺资料先取包」。

> 资料包对下游是**只读输入**；要补文章就重跑本技能生成新目录，不要手改 `pack.*`。

## 三档画像

| profile | 适用 | 文章硬门槛 | Top N |
|---|---|---|---|
| `tech`（默认） | AI / 编程技术，中英双语 | 阅读 ≥5,000 且评论 ≥10 | 8 |
| `wechat` | 中文爆款 / 公众号选题 | 阅读 ≥10,000 且评论 ≥20 | 10 |
| `general` | 泛领域，不预设域名偏好 | 阅读 ≥5,000 且评论 ≥10 | 8 |

视频 / 社区帖 / 仓库 / 论文各有对应主指标与阈值，全部在
[`skill/assets/sources.json`](skill/assets/sources.json) 里改，**不用改脚本**。

## 文件结构

```
aceld-websearch/
├── README.md              本页
├── install.sh / install.ps1
├── requirements.txt       零依赖
├── skill/
│   ├── SKILL.md           上岗手册（六步流水线 + 三条铁律）
│   ├── references/
│   │   ├── 01-sources.md   权威分层 / 域名表 / 三路检索式
│   │   ├── 02-metrics.md   指标口径 / 各平台可见性 / 阈值 / 防编造
│   │   ├── 03-workflow.md  六步 SOP / 失败模式复盘
│   │   └── 04-contract.md  与下游 skill 的契约 + 可注入哨兵块
│   ├── assets/
│   │   ├── sources.json              profile / tier / 黑名单 / 阈值
│   │   └── candidates.example.json   候选池格式样例（数字为占位）
│   └── scripts/
│       ├── window.py       时间窗唯一真源
│       ├── urlnorm.py      URL 规范化 + 域名分级 + 原文回溯
│       ├── rank.py         硬过滤 + 评分 + 生成 pack.md/json
│       └── verify.py       交付前自检 PASS/FAIL
└── examples/              示例资料包
```

## 安装

```bash
bash install.sh                              # 装到 ~/.workbuddy-ai/skills/aceld-websearch
bash install.sh --claude                    # 装到 ~/.claude/skills/aceld-websearch
bash install.sh --dest /path/to/skills/x    # 自定义
```

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

> 若已存在同名技能，脚本会备份到 `~/.workbuddy-ai/skills-backup/`。
> **备份绝不能留在 `skills/` 里** —— 加载器按子目录扫技能，会出现多个同名技能。
> 装完重启会话让 Agent 重新加载技能列表。

## 常见问题

**Q：入选 0 条怎么办？**
回去补检索（换语言 / 换平台 / 换关键词），或换主题。不要偷偷调低阈值；
确实要放宽就显式加 `--days 210` / `--allow-t3` / `--allow-waiver` 并在交付说明里写清楚。

**Q：微信公众号抓不到阅读数？**
抓不到就别填 `views`。用点赞 / 在看 / 评论组合并写明口径，或标 `heat_waiver` 走「权威一手」独立区（不占入选名额）。详见 `02-metrics.md`。

**Q：为什么 `freshness` 不能写 `d180`？**
宿主搜索工具只支持 `d1..d30 / m1..m12 / y1..y5`，半年只能写 `m6`；
精确 180 天由 `window.py` + `rank.py` 在脚本侧硬过滤，两道窗口取严。

**Q：能直接把资料包当文章引用吗？**
链接可以，数字要连 `metric_source` 与 `published` 一起引用；资料包不是正文，别整段搬运。

## 许可

MIT，见仓库根 [`LICENSE`](../LICENSE)。
