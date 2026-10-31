# aceld-skill-rollout · 把能力铺满整个技能库

> 一个能力在 5 个技能里各写一遍，写完还不知道有没有真的生效。
> 这个技能把「铺开」变成三步可验证的动作：**审计 → 注入 → 验证**。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

---

## 它解决什么问题

技能库一多，就会出现这种局面：某个能力（比如「开工前先跑一次前置检查」）
需要在 5 个技能里都写一遍。

手工写一遍的结果通常是：

1. 5 个技能都「有」这段文字，`grep` 全命中 → 以为完成
2. 实际上 3 个写在文件末尾，Agent 从上往下读，**永远读不到**
3. 半年后想改，发现 5 处写法各不相同，不知道哪个是最新
4. 改到第 3 个时手滑，把某个 SKILL.md 写成了空文件

这个技能就是针对这四步，一步一个工具。

---

## 四步

| 阶段 | 命令 | 解决什么 |
|---|---|---|
| ① 审计 | `python scripts/audit.py` | 哪些技能有、在什么位置、是不是三方 |
| ② 注入 | `python scripts/inject.py --block b.md --marker "能力名" --apply` | 幂等插入，再跑一次是「替换」不是「再插一遍」 |
| ③ 验证 | `python scripts/audit.py --verify` | 位置 ≤30 行？脚本存在？仓库与本地一致？ |
| ④ 发布 | `python scripts/publish.py -m "..."` | **提交 + 推送 + 同步本地 + 再验证**，一条命令 |

`publish.py` 是第 ④ 步的重点：用户的要求是「提交 GitHub 后本地技能也要更新」，
分步手工做一定会漏，而且漏了**没有任何报错**——本地还是旧版，你以为已经更新了。

配套的 `sync.py` 负责仓库 → 本地已装副本，**默认只报告不覆盖**；
`--mirror` 才以仓库为准全覆盖（`publish.py` 用的就是它）。

---

## 安装

```bash
# macOS / Linux
bash install.sh

# Windows
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

装完重启会话，让 Agent 重新加载技能列表。

---

## 快速上手

```bash
cd <aceld-skill 仓库根>

# 1. 先看现状
python aceld-skill-rollout/skill/scripts/audit.py

# 2. 写一个跨技能一致的块（参考 skill/assets/block-preflight.md）
#    然后干跑，只看不改
python aceld-skill-rollout/skill/scripts/inject.py \
    --block aceld-skill-rollout/skill/assets/block-preflight.md \
    --marker "开工前置检查"

# 3. 确认 insert/replace/skip3 数字对得上，再真写
python aceld-skill-rollout/skill/scripts/inject.py \
    --block aceld-skill-rollout/skill/assets/block-preflight.md \
    --marker "开工前置检查" --apply

# 4. 发布：提交 + 推送 + 同步本地 + 验证，一条命令
python aceld-skill-rollout/skill/scripts/publish.py -m "feat(xxx): 为什么改"
```

---

## 三条铁律

### 一、存在 ≠ 生效

能力块必须在 `SKILL.md` **前 30 行**内。写在末尾的一律按「没有」处理——
Agent 从上往下读，读到「阶段一」就开始干活了。

审计表里的 `位置` 列就是判据：

```
aceld-course    ✓   10/254    v1 ✓ 生效
aceld-findskill ✓   140/208   v1 ✗ 太靠后
```

### 二、块要一致，差异外置

核心块逐字一致（由 `inject.py` 统一维护，带 sentinel 哨兵），
每个技能特有的「本技能覆盖不了什么」写在块**外面**。
这样改块只改一处，摘块也不会带走差异部分。

### 三、三方技能不碰

本地 `~/.workbuddy-ai/skills/` 里，有 `_meta.json` 且含 `ownerId`、
名字不以 `aceld-` 开头的，是市场装的技能——改了下次更新会被整体覆盖。
`audit.py` 自动分类并标「跳过」。

### 四、提交 ≠ 完成，本地同步了才算

仓库改了、本地没跟，用户当下用的还是旧版。所以第 ④ 步用 `publish.py`
把 `commit / push / sync --mirror / verify` 绑成一个动作——**不要手工分步做**。

---

## 目录结构

```
aceld-skill-rollout/
├── README.md
├── install.sh
├── install.ps1
├── requirements.txt
└── skill/
    ├── SKILL.md
    ├── assets/
    │   └── block-preflight.md      # 现成的「开工前置检查」块模板
    ├── references/
    │   ├── 01-audit.md             # 审计维度、有效性判定、矩阵表怎么读
    │   ├── 02-inject.md            # 锚点、哨兵、版本号、幂等与回滚
    │   ├── 03-boundaries.md        # 自有 vs 三方、本地副本、命名与许可
    │   └── 04-release.md           # 验证清单、提交规范、memory、推送
    └── scripts/
        ├── audit.py                # 扫描 + 矩阵表；--verify 加严
        ├── inject.py               # 幂等注入/替换/移除 sentinel 块
        ├── sync.py                 # 仓库 skill/ → 本地已装副本；--mirror 全覆盖
        └── publish.py              # 提交 + 推送 + 同步本地 + 验证，一条命令
```

---

## 与其它技能的关系

| 技能 | 关系 |
|---|---|
| `aceld-findskill` | 兄弟技能。它解决「用哪个技能」，本技能解决「把能力铺到所有技能」。块内引用的 `preflight.py` 来自它 |
| `skill-creator` | 互补。它从零造一个新技能，本技能给**已有**技能批量打补丁 |

本技能**不负责**：单个技能的内容创作、新技能从零设计。

---

## 关键实现细节（踩过的坑）

| 坑 | 后果 | 现在怎么做 |
|---|---|---|
| `grep` 命中就以为生效 | 3 个技能块在末尾，从没被执行 | `audit.py` 判前 30 行 + 跳过 frontmatter/代码块 |
| `open(path,"w")` 先截断后写 | 生成内容抛异常 → 251 行文件变 0 字节 | 一律 `tmp + os.replace` 原子写 |
| `fence = not fence` 判代码块 | ```` ```markdown ```` 里套 ```` ```bash ```` → 示例文字被当正文 | 只有裸围栏算闭合 |
| Windows 上 `os.path.isabs("/foo")` 为 True | `~/.workbuddy-ai/...` 被截成 `/...` → 7 条假错 | `~` 先 expanduser；绝对路径只认盘符 |
| 无脑 `repo → local` 覆盖 | 本地 1634 行工作版被 254 行发布版冲掉 | `sync.py` 默认只报告，`--mirror` 才覆盖且逐个备份 |
| 用**仓库目录名**找本地目录 | `aceld-course/` 装出来其实是 `course-studio`，比的不是同一个技能 | 读 `SKILL.md` 的 `name:` 决定本地目录名（`read_skill_name()`） |
| `cp -R` / `copytree` 带进 `__pycache__` | 本地技能目录里一堆 `.pyc` | 装完 `clean_pycache()` 清掉 |
| 提交推送完就收工 | 本地还是旧版，**且没有任何报错** | `publish.py` 把四步绑成一个动作 |

---

## License

MIT
