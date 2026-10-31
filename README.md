<div align="center">

# aceld-skill

[@aceld](https://github.com/aceld) 的 **个人 Agent Skill 宝库**

这里沉淀 Aceld 多年一线实战中反复验证、可复用的「方法论 + 流水线」：
从 Golang 架构、职场进阶、社交与人生经验，到 AI 架构、数字货币 / 区块链行业认知，
再到架构师绘图等硬技能——都会逐步整理成一个个能直接安装的 Agent Skill。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 这是什么

`aceld-skill` 是 [@aceld](https://github.com/aceld) 的**个人技能合集仓库**：每个子目录是一个
独立、可单独安装的 Agent Skill。它不是某一个工具的文档，而是把作者跨领域的实战经验，
沉淀成 AI 能直接照着执行的流水线。

装上对应技能后，你对 AI 说一句自然语言，它就会照着那条流水线推进，而不是每次从零开始踩坑。

## 已收录技能

| 技能 | 目录 | 说明 |
|---|---|---|
| Course Studio（AI 课程制作流水线） | [`aceld-course/`](aceld-course/) | 给一份讲稿，产出一节完整的课：动画幻灯片 → 配音 → 成片 → 图文 → 图卡 → 封面 |
| Aceld 架构图绘制（draw.io 默认主题白底扁平风） | [`aceld-diagram/`](aceld-diagram/) | 圆角矩形模块、圆柱存储、虚线分组、便签标注、细线小箭头、左侧鹰眼监控列的架构图：风格规范 + 零依赖 SVG 生成器 |
| Find Skill（开工前置检查 + 检索 + 体检 + 吸收） | [`aceld-findskill/`](aceld-findskill/) | 每个技能开工前先跑它：本地有没有更合适的、线上有没有更新的。再做多源检索（skills.sh 安装量 / GitHub）+ 五条硬性淘汰线 + 安全扫描 + 吸收方法论（不搬代码） |

> 每个技能都是自包含的：进入对应子目录，运行里面的 `install.sh` / `install.ps1` 即可安装。

### 技能之间怎么协作

`aceld-findskill` 是**底座**，所有 aceld 技能的 `SKILL.md` **顶部**都挂了同一块「⚑ 开工前置检查」：

```bash
python ~/.workbuddy-ai/skills/aceld-findskill/scripts/preflight.py "本次任务关键词"
```

30 秒出三种结论：**① 直接用本地 X** / **② 本地没有或线上更强 → 检索+体检** / **③ 上游有更新 → 先看差异**。
不检查就开工，等于用去年的地图走今年的路——技能生态每周都在变。

## 规划中的技能方向

`aceld-skill` 会持续扩充，下面这些方向都会逐步沉淀进来（最终目录名以实际落地为准）：

| 方向 | 大致内容 |
|---|---|
| Golang 架构 | 多年 Golang 架构师经验：高并发、微服务、工程化、性能调优、项目落地套路 |
| 职场进阶 | 技术人的职业路径、晋升、带团队、技术选型与向上汇报的方法论 |
| 社交与人生经验 | 沟通、人脉经营、个人成长等长期主义的人生经验 |
| AI 架构 | AI 应用 / Agent 架构设计、落地与实践经验 |
| 数字货币 / 区块链 | 行业认知、技术原理与一线实战经验 |
| 架构师绘图 | 架构师常用的绘图方法、模板与表达套路 |
| …… | 更多跨领域实战经验持续加入 |

> 当前已落地的技能见上方「已收录技能」。

## 如何安装某个技能

以 `aceld-course` 为例：

### Windows（PowerShell）

```powershell
git clone https://github.com/aceld/aceld-skill.git
cd aceld-skill\aceld-course
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

### macOS / Linux

```bash
git clone https://github.com/aceld/aceld-skill.git
cd aceld-skill/aceld-course
bash install.sh
```

各技能的安装目标、参数与完整用法，详见对应子目录里的 README。

---

## 目录约定

```
aceld-skill/               仓库根（本文件）
├── LICENSE                全仓库统一的 MIT 许可
├── .gitignore
├── .gitattributes
└── <skill-name>/          每个子目录 = 一个独立技能
    ├── README.md          该技能的说明
    ├── install.sh / install.ps1
    ├── requirements.txt
    ├── skill/             技能本体
    └── examples/          示例
```

新增技能时，直接在仓库根下新建一个 `<skill-name>/` 子目录，按上面的约定放好即可，不影响其它技能。

---

## 许可

本仓库各技能均以 [MIT License](LICENSE) 发布，可自由用于商业项目。
