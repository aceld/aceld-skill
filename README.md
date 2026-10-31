<div align="center">

# aceld-skill

[@aceld](https://github.com/aceld) 的 **Agent Skill 合集仓库**

把做课、写作、运维等可复用的工程流水线，沉淀成一个个能直接安装的 Agent Skill。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 这是什么

`aceld-skill` 是一个**技能合集仓库**：每个子目录是一个独立、可单独安装的 Agent Skill。
装上之后，你对 AI 说一句自然语言，它就会照着对应技能的流水线推进，而不是每次从零开始踩坑。

## 已收录技能

| 技能 | 目录 | 说明 |
|---|---|---|
| Course Studio（AI 课程制作流水线） | [`aceld-course/`](aceld-course/) | 给一份讲稿，产出一节完整的课：动画幻灯片 → 配音 → 成片 → 图文 → 图卡 → 封面 |

> 每个技能都是自包含的：进入对应子目录，运行里面的 `install.sh` / `install.ps1` 即可安装。

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
