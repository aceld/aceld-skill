# 04 · 发布：验证、提交、推送、记账

> 铺完能力只是「改完了」，发布是「确认改对了，并且下次还在」。
> 四问不过就别 commit。

---

## 1. 发布前四问

| # | 问题 | 怎么查 | 不过的后果 |
|---|---|---|---|
| 1 | 每个自有技能都有 sentinel？ | `audit.py --verify` 全绿 | 下次注入重复插入 |
| 2 | 块内引用的脚本真的存在？ | 同上（verify 会逐个 `isfile`） | 用户复制命令跑 → 报 No such file |
| 3 | 仓库和本地都改了？ | `audit.py` 里同名两行都是 `✓ 生效` | 只改仓库=本地不生效；只改本地=下次装就丢 |
| 4 | 提交信息写清「为什么」？ | 看 `git log` | 半年后没人知道这次改动解决了什么 |

第 4 条值得展开。对比：

```
✗ feat: 给所有技能加了开工前置检查
✓ feat(findskill): 把「遇到缺口才找」升级为「开工前必查」——新增 preflight.py
```

第一版只说了「做了什么」，而「做了什么」`git show` 一看就知道。
提交信息该说的是 `git show` 看不出来的东西：**为什么要改**。

---

## 2. 完整发布流程

### 2.1 首选：一条命令

```bash
cd D:/我的坚果云/AI/aceld-skill
python aceld-skill-rollout/skill/scripts/publish.py -m "feat(xxx): 为什么改"
```

它按顺序做：`git add -A` → `commit` → `push`（自动设 7890 代理）→
`sync.py --mirror --apply`（同步本地）→ `audit.py --verify`。
任何一步失败立刻停，并告诉你下一步怎么做。

**为什么要绑成一个动作**：用户的要求是「提交后本地也要更新」。
分步做的话，`push` 成功就已经觉得完事了，本地还是旧版，**而且没有任何报错**。
这种静默不一致最难发现——下次用技能时才发现用的是两周前的版本。

推送失败（网络/凭据）时提交已留在本地，修好后补一条：

```bash
python aceld-skill-rollout/skill/scripts/publish.py --sync-only
```

### 2.2 手工分步（调试脚本本身时才需要）

```bash
# 0. 进仓库根（find_repo 靠这个找）
cd D:/我的坚果云/AI/aceld-skill

# 1. 验证（这一步不绿，后面全部作废）
python aceld-skill-rollout/skill/scripts/audit.py --verify

# 2. 同步本地已装副本
python aceld-skill-rollout/skill/scripts/sync.py            # 先看
python aceld-skill-rollout/skill/scripts/sync.py --mirror --apply

# 3. 再验证一次（本地那几行也要 ≤30 行）
python aceld-skill-rollout/skill/scripts/audit.py --verify

# 4. 语法自检（别把 SyntaxError 提交上去）
python -m py_compile aceld-skill-rollout/skill/scripts/*.py

# 5. 看 diff（关键：确认没有意外删除）
git status --short
git diff --stat

# 6. 提交
git add -A
git commit -m "..."

# 7. 推送（必须走 Clash 代理，见下）
```

### 第 5 步为什么重要

`git diff --stat` 里出现这种行就要停下来：

```
 aceld-course/skill/SKILL.md | 253 +-----------------------------------------
```

253 行删除、0 行新增 = 文件被清空了。这正是 `open(path,"w")` 事故的样子
（见 `02-inject.md` §6）。**正常的能力注入 diff 应该是「几行 +，几行 -」**。

---

## 3. 推送必须走 Clash 代理

本机环境：

| 通道 | 结果 |
|---|---|
| 直连 443 | ❌ 被 SNI 拦，换 IP 也 reset |
| 沙箱自带代理 `127.0.0.1:53839` | ❌ 对 github.com 返回 502 |
| Clash Party `127.0.0.1:7890` | ✅ 通 |

```bash
export https_proxy=http://127.0.0.1:7890
export http_proxy=http://127.0.0.1:7890
git push origin main
```

**凭据**：本机 `git config credential.helper` = `manager`（Git Credential Manager），
**已存有 aceld 的凭据**，`GIT_TERMINAL_PROMPT=0 git push` 可以直接成功。
（早期记录说「无任何凭据」是错的，已实测推翻。）

`GIT_TERMINAL_PROMPT=0` 仍然要加：万一 GCM 哪天要重新授权，
它会**立刻失败**而不是挂在用户名/密码提示上干等。`publish.py` 已经设了这个变量。

---

## 4. 提交信息规范

沿用 Conventional Commits，scope 用技能名：

```
<type>(<scope>): <为什么改>

<可选：怎么验证的>
```

| type | 用在哪 |
|---|---|
| `feat` | 新技能、新能力、新脚本 |
| `fix` | 修 bug、修误判 |
| `docs` | 只改文档 |
| `refactor` | 结构变了但行为没变 |
| `chore` | 版本号、依赖、格式 |

真实例子：

```
feat(rollout): 新增 aceld-skill-rollout——把「铺能力」做成可验证的三步
fix(findskill): preflight 打分误判——正文命中封顶 20 分、同分优先短正文
docs(aceld-course): 新增竖版原生 1080×1920 方法论
```

一次 commit 只干一件事。既加技能又改打分，出问题没法单独 revert。

---

## 5. 记 memory

发布完在 `D:\我的坚果云\AI\.workbuddy-ai\memory\YYYY-MM-DD.md` 追加一条。
只记**下次会用到的结论**，不记过程：

```markdown
## aceld-skill-rollout 技能落地（2026-10-31）

- 新建 `aceld-skill/aceld-skill-rollout/`：audit.py / inject.py / sync.py + 4 篇 reference
- 满库注入「⚑ 开工前置检查」块 v1：自有 7 个全部生效（仓库 4 + 本地独有 1），三方 5 个跳过
- 关键教训：**存在 ≠ 生效**，能力块必须在 SKILL.md 前 30 行
- 踩坑：`open(path,"w")` 先截断后写 → 生成内容抛异常会留 0 字节文件；一律 tmp + os.replace
- 踩坑：Windows 上 `os.path.isabs("/foo")` 为 True，`~` 被正则吃掉 → 7 条假错
```

写进 `MEMORY.md`（长期）的只放**跨会话必须遵守的规则**，
日常流水放 `YYYY-MM-DD.md`（append-only）。

---

## 6. 回滚一次发布

```bash
# 只回滚某个技能
git checkout -- aceld-course/skill/SKILL.md

# 回滚整个 commit（保留改动到工作区，方便改完再提）
git revert --no-commit <sha>

# 摘掉某个能力块（不删代码，只删哨兵区间）
python aceld-skill-rollout/skill/scripts/inject.py --marker "开工前置检查" --remove --apply
```

`git revert` 优于 `reset --hard`：已经推上去的 commit，`reset` 会造成
本地与远端分叉，下次 push 还得 force。

---

## 7. 发布检查清单（可勾选）

用 `publish.py` 时，前 5 条它全包了，你只需确认后 4 条：

```
[ ] （publish 自动）audit.py --verify 全绿
[ ] （publish 自动）sync.py --mirror 执行过，本地也是 ✓ 生效
[ ] （publish 自动）py_compile 无报错
[ ] （publish 自动）git diff --stat 没有异常的大段删除
[ ] （publish 自动）push 成功
[ ] 新技能已加进仓库根 README.md 的「已收录技能」表
[ ] 新技能的 README.md / install.sh / install.ps1 齐了
[ ] commit message 说了「为什么」
[ ] memory 记了一条
[ ] 重启会话后新技能才进 Agent 的技能列表
```

> 最后一条容易忘：`sync.py` 只是把文件放到 `~/.workbuddy-ai/skills/`，
> **Agent 的技能列表是会话启动时读的**。不重启，本会话里仍然用旧版。

第 5、6 条最容易漏。技能在仓库里但 README 没列 = 别人翻不到；
没有 `install.sh` = 装了也不会用。
