---
name: aceld-skill-rollout
description: 把一个新能力（或一处修订）铺到 aceld-skill 全部技能上的批量适配流程。当用户说「把这个能力加到所有 aceld 技能」「批量更新技能」「技能库同步」「让每个技能都具备 X」「新加的能力下发到全部技能」时使用。含审计矩阵（存在≠生效）、幂等注入（sentinels 哨兵块）、仓库→本地同步、端到端验证与发布。
license: MIT
metadata:
  author: aceld
  version: "1.0.0"
  homepage: https://github.com/aceld/aceld-skill
---

# aceld-skill-rollout · 把能力铺满整个技能库

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

**本技能覆盖不了**：单个技能的内容创作、新技能从零设计 —— 那是各技能自己和 skill-creator 的活。

**这个技能解决一件事**：一个能力在 5 个技能里各写一遍，写完还不知道有没有真的生效。
它把「铺开」变成三步可验证的动作：**审计 → 注入 → 验证**。

---

## 0. 一分钟速览

```
① 审计 → ② 定 block → ③ 注入 → ④ 同步本地 → ⑤ 验证 → ⑥ 发布
```

| 阶段 | 动作 | 脚本 | 产出 |
|---|---|---|---|
| ① 审计 | 现在到底哪些技能有、哪些只是"写了但没生效" | `audit.py` | 一张矩阵表 |
| ② 定 block | 写一段**跨技能完全一致**的核心块 | 手写 | `block.md` |
| ③ 注入 | 幂等插入到每个技能的正确锚点 | `inject.py` | 改动的 SKILL.md |
| ④ 同步 | 仓库 `skill/` → 本地已装副本（带备份） | `sync.py` | 本地技能更新 |
| ⑤ 验证 | marker 在顶部？脚本能跑？仓库与本地一致？ | `audit.py --verify` | PASS / 问题清单 |
| ⑥ 发布 | 提交信息写清「为什么改」+ 推送 + 记 memory | 手写 | commit |

---

## 1. 三条铁律

### 铁律一：存在 ≠ 生效

这是踩过的最大的坑。第一版把「能力缺口」一节写在 SKILL.md **末尾**，
5 个技能全都「有」，但**一次都没被执行过**——因为 Agent 从上往下读，读到「阶段一」就开始干活了。

**判定标准**：能力块必须在**前 30 行**内，或者在流程的第一屏。写在末尾的一律按「没有」处理。

### 铁律二：块要一致，差异要外置

同一个能力在 5 个技能里写法各不相同，半年后你就分不清哪个是当前版本，
改一次要改五处、还容易漏。

做法：**核心块逐字一致**（由 `inject.py` 统一维护，带 sentinel 哨兵），
**每个技能特有的部分写在块外面**（如「本技能覆盖不了什么」）。

### 铁律三：三方技能不碰

本地 `~/.workbuddy-ai/skills/` 里有两类技能：

| 类型 | 特征 | 能不能改 |
|---|---|---|
| 自有 | 仓库里有同名目录，或名字以 `aceld-` 开头 | ✅ 改，然后 commit |
| 三方（市场装） | 有 `_meta.json` 且含 `ownerId`，名字不以 `aceld-` 开头 | ❌ 别改——下次更新会被覆盖，改了也是白改 |

`audit.py` 会自动分类并标出「跳过」。

---

## 2. 用法

```bash
# ① 审计：哪些有、在哪个位置、是不是三方
python scripts/audit.py
python scripts/audit.py --verify            # 加严：位置 + 脚本路径 + 仓库/本地一致性

# ② 注入：把一个 block 铺到所有自有技能（默认 dry-run，只看不改）
python scripts/inject.py --block block.md --marker "开工前置检查"
python scripts/inject.py --block block.md --marker "开工前置检查" --apply

# ③ 同步：仓库 skill/ → 本地已装副本（默认 dry-run）
python scripts/sync.py
python scripts/sync.py --apply
```

`--repo` 不给时自动找：`$ACELD_SKILL_REPO` → 从当前目录向上找 `aceld-course/skill/SKILL.md`。

---

## 3. 哨兵块（sentinels）——幂等的关键

所有注入的块都用 HTML 注释包起来：

```markdown
<!-- aceld-rollout:begin 开工前置检查 v1 -->
> ### ⚑ 开工前置检查（每次先跑，30 秒）
> ...
<!-- aceld-rollout:end -->
```

三个好处：
1. **幂等**：再跑一次是「替换」不是「再插一遍」，不会越注越多
2. **可审计**：`audit.py` 靠 sentinel 定位，比找中文标题可靠
3. **可回滚**：`inject.py --remove` 一键摘掉，不用手工删

`v1` 是块的版本号。**改块内容时必须升版本号**，否则 `audit.py --verify` 分不清
「还是旧版」和「已经是新版」。

---

## 4. 锚点选择（决定能不能生效）

| 锚点 | 适用 | 说明 |
|---|---|---|
| `--anchor after-intro` | **默认，推荐** | 插在一级标题下第一段之后，`---` 之前 |
| `--anchor after-heading "## 0. 一分钟速览"` | 有固定结构 | 插在指定标题**之前** |
| `--anchor append` | 不推荐 | 追加到末尾，`inject.py` 会警告「此处大概率不会被读到」 |

**为什么默认 after-intro**：SKILL.md 的惯例是「标题 → 一句话定位 → 分隔线 → 第一节」。
插在一句话定位之后，读者第一屏就能看到，且不打断原有编号。

---

## 5. 发布前的四问

1. **每个自有技能都有 sentinel？** `audit.py --verify` 全绿
2. **块内引用的脚本真的存在？** verify 会检查路径
3. **仓库和本地都改了？** 只改仓库 = 本地不生效；只改本地 = 下次装就丢
4. **提交信息写清「为什么」？** 不是「加了 X」，而是「原来写在末尾所以从没被执行」

---

## 6. 文件索引

| 文件 | 内容 |
|---|---|
| `references/01-audit.md` | 审计维度、有效性判定、矩阵表怎么读 |
| `references/02-inject.md` | 锚点、哨兵、版本号、幂等与回滚 |
| `references/03-boundaries.md` | 自有 vs 三方、本地副本、命名与许可边界 |
| `references/04-release.md` | 验证清单、提交规范、memory 记录、推送 |
| `scripts/audit.py` | 扫描仓库+本地，输出矩阵；`--verify` 加严 |
| `scripts/inject.py` | 幂等注入/替换/移除 sentinel 块 |
| `scripts/sync.py` | 仓库 `skill/` → 本地已装副本（带备份） |
