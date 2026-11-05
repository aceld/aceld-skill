# 04 · 输出契约：其他 skill 怎么吃这份资料包

> 本技能存在的唯一理由，是**让别的技能不用自己临时瞎搜**。
> 所以接口必须稳定、可读、可校验：一份人能读的 `pack.md`，一份程序能读的 `pack.json`。

## 1. 目录约定

```
research/<topic-slug>/pack/
├── pack.md      人读 / 下游 Agent 直接读的可读链接清单
├── pack.json    机器读
└── (可选) candidates.json、检索留痕，留在上一级目录
```

- `<topic-slug>`：小写英文短横线，如 `ai-agent-production`、`mcp-2026`。
- 同一主题重跑：**新建目录**（加日期后缀）或覆盖同一目录，但绝不就地手改 `pack.*`。
- `pack.*` 对下游是**只读输入**。

## 2. `pack.json` 字段（下游只依赖这些）

| 路径 | 类型 | 含义 |
|---|---|---|
| `schema_version` | str | 当前 `"1.0"`；下游先读它再做兼容 |
| `topic` / `profile` / `generated_at` | str | 主题、画像、生成时间 |
| `window.since` / `window.until` / `window.days` / `window.freshness` | str/int | 时间窗，写进下游产物的「资料时效」说明 |
| `thresholds` | obj | 本次实际生效的阈值（含是否被显式放宽） |
| `queries[]` | arr | 检索留痕，可复现 |
| `items[]` | arr | **入选链接，下游主要消费它** |
| `items[].canonical_url` | str | 去跟踪参数、可读、指向原文的规范链接 |
| `items[].title` / `source` / `author` / `published` | str | 标题、来源、作者、页面标注的发布日期 |
| `items[].tier` | `T1`\|`T2` | 权威层级 |
| `items[].kind` | str | `article` / `video` / `post` / `thread` / `repo` / `paper` |
| `items[].metrics` / `metric_source` | obj / str | 公开计数 + 口径出处 |
| `items[].summary` | str | 基于正文的一句话摘要（**不是搜索摘要**） |
| `items[].value_for` | str | 建议用途：课程案例 / 数据 / 反例 / 行文角度 |
| `items[].score` | obj | `total` 与四个分项，可用于排序/筛选 |
| `items[].readable_evidence` | str | 可读性证据 |
| `alternates[]` / `waived[]` / `rejected[]` | arr | 备选 / 无公开热度的一手 / 淘汰留痕 |
| `stats` | obj | 候选→入选→淘汰的数量 |

**兼容约定**：下游只用上表字段；新增字段不破坏旧下游；`schema_version` 主版本变化才允许改字段语义。

## 3. 三种消费方式

### 方式 A：把 `pack.md` 直接交给下游（最常用）

```
读 research/ai-agent-production/pack/pack.md，按「入选链接」里的可读链接取料，
每条注明来源与发布日期；不要使用「备选 / 淘汰」区里的链接。
```

`pack.md` 已经把链接、热度（带口径）、摘要、可用途都排好，不需要下游再做筛选。

### 方式 B：拼成一行塞进下游输入

```bash
python -c "import json;d=json.load(open('research/ai-agent-production/pack/pack.json',encoding='utf-8'));print('\n'.join('- '+i['title']+' '+i['canonical_url'] for i in d['items']))"
```

### 方式 C：程序化取链接（写进下游脚本）

```python
import json
pack = json.load(open("research/ai-agent-production/pack/pack.json", encoding="utf-8"))
assert pack["schema_version"].split(".")[0] == "1"
urls = [i["canonical_url"] for i in pack["items"]]
window = pack["window"]          # 写进产物的「资料时效」说明
```

## 4. 可注入哨兵块（配合 `aceld-skill-rollout` 铺到其他技能）

想让所有 aceld 技能默认「缺外部资料时先取包」，用 `inject.py` 把
**`assets/block-research.md`** 幂等插到各技能 `SKILL.md` 的**前 30 行**。

### ★ 为什么这个块只有 3 行

每个 aceld 技能顶部已经有一块「开工前置检查」（`begin` 在第 10~18 行）。
新块如果用 `inject.py` 的默认锚点 `after-intro`，会被插到那块之后（约第 36 行），
**超过 30 行 = 不生效**；如果反过来把新块放前面但块太长，又会把「开工前置检查」挤到 30 行外。

解法：新块压到 3 行（加哨兵共 5 行 + 1 空行 = 6 行），插在 H1 之前：

```
新块 begin ≈ 第 11 行 ✓
原「开工前置检查」begin 10/11/13/18 → 16/17/19/24 ✓ 全部仍 ≤30
```

### 铺开命令

```bash
R=~/.workbuddy-ai/skills/aceld-skill-rollout/scripts
B=~/.workbuddy-ai/skills/aceld-websearch/assets/block-research.md
ONLY=aceld-course,aceld-diagram,aceld-findskill,aceld-skill-rollout,aceld-wechat

# 先看不改
python $R/inject.py --block "$B" --marker "资料检索" \
  --anchor after-heading --heading "# " --only "$ONLY"
# 真的写（会同时处理仓库与本地同名技能，幂等、自动跳过三方技能）
python $R/inject.py --block "$B" --marker "资料检索" \
  --anchor after-heading --heading "# " --only "$ONLY" --apply
# 验证：两个 marker 都要「✓ 生效」
python $R/audit.py --marker "资料检索" --verify
python $R/audit.py --verify
```

> **`--heading "# "` 不是笔误**：`inject.py` 的 `after-heading` 实际把块插在匹配行**之前**，
> 用 `"# "` 才能命中各技能不同的 H1 标题并落到最顶部。
> 被调方 `aceld-websearch` 自己不注入（自己调自己没意义），
> 所以 `audit.py --marker "资料检索"` 里它显示 ✗ 是**预期**，不是故障。
> 本地独有的 `aceld-voice`（配音技能，不消费文章）也不在铺开范围内；
> `course-studio` 是仓库 `aceld-course/` 装出来的名字，会在 `publish.py` 的 `sync --mirror` 时自动带上块，
> 不需要单独注入。
>
> **提交链路的默认校验 marker 是「开工前置检查」**，注入新块后必须再跑一次
> `python $R/audit.py --verify` 确认原块没被挤出前 30 行（本次实测 14/14 仍生效）。

> 三方技能（`_meta.json` 有 `ownerId`）不要注入；`inject.py` / `audit.py` 会自动跳过。

## 5. 各下游的典型用法

| 下游技能 | 拿资料包干嘛 | 注意 |
|---|---|---|
| `course-studio` / `aceld-course` | 找课程案例、行业数据、反面教材，喂给「讲稿 → 幻灯片」阶段 | 引用时在课件脚注带 `published` + `canonical_url`；别把半年前的结论讲成「最新」 |
| `aceld-wechat` | 找选题角度、爆款行文节奏、可引用的公开数据 | 用 `--profile wechat` 重跑；文章里的数字要注明出处与统计时间 |
| `aceld-diagram` | 找架构演进、系统设计的一手参考 | 优先 `items[].tier == "T1"`（官方文档 / 工程博客） |
| 技术选型 / 调研报告 | 横向对比多方观点 | 检查 `max_domain_share`，避免结论只来自一家 |

## 6. 交付自检清单

- [ ] `verify.py` 输出 `PASS`
- [ ] `pack.md` 里每条入选链接都点得开、能读到正文
- [ ] 每条都有 `metric_source`，数字来自页面而非摘要
- [ ] `window` 是近 180 天，`--today` 没提示过期
- [ ] `queries[]` 非空，别人能照着重跑
- [ ] 下游拿到的只是 `pack/` 目录，没有把 `candidates.json` 当输入
- [ ] 如有放宽（T3 / waiver / 更长窗口），已在交付说明里显式写出
