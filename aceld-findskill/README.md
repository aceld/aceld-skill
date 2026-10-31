# aceld-findskill · 能力缺口 → 找到并吸收别人的技能

刘丹冰Aceld 的 **Agent Skill 检索与吸收技能**：当手上技能做不到某一步时，
怎么在互联网上找到真能用的那个，安全地拿过来，变成自己的一部分。

核心不是「搜」，是**判断力**：判断该不该搜、判断哪个能用、判断哪些代码不能碰、
判断吸收什么而不是照搬什么。

## 这是什么

一份**判断流程**（`skill/SKILL.md` + 6 篇 reference）+ 三个**零依赖脚本**：

| 脚本 | 作用 |
|---|---|
| `scripts/preflight.py` | **开工前置检查**：本地技能匹配（IDF 加权）+ 线上候选 + 上游更新，30 秒出三选一结论 |
| `scripts/find.py` | 多源检索（skills.sh 安装量榜 / GitHub 仓库 / npx skills），输出候选表 |
| `scripts/vet.py` | 单技能体检：五条硬性淘汰线 + 18 条安全规则扫描 + 许可分级 → PASS/WARN/REJECT |
| `scripts/absorb.py` | 拉到 inbox + 生成阅读报告（含大纲、外部调用点、吸收五问、防漂移指纹） |
| `scripts/register_source.py` | 登记技能来源（install.sh 自动调用），供 `--check-updates` 用 |

**绝不自动安装**：所有候选只落到 `~/.aceld-skill-inbox/`，不写 skills 目录、不执行任何下载来的脚本。

## 快速开始

```bash
# 0) 国内先设代理（直连 github 会被 SNI 拦）
export https_proxy=http://127.0.0.1:7890 http_proxy=http://127.0.0.1:7890

# 1) 前置检查：本地有没有能用的？线上有没有更好的？（每次开工先跑这个）
python skill/scripts/preflight.py "竖版视频 抖音 版式重排"

# 2) 检索：给能力描述，不给产品名
python skill/scripts/find.py "pdf form filling" --min-installs 1000

# 3) 体检：id 用 skills.sh 的 owner/repo/skill 格式
python skill/scripts/vet.py anthropics/skills/pdf

# 4) 吸收：拉到 inbox 并生成阅读报告（不安装、不执行）
python skill/scripts/absorb.py anthropics/skills/pdf
```

## 前置检查的三种结论

```
$ python skill/scripts/preflight.py "配音 音色克隆"
【本地】
  100.0  aceld-voice   复现「刘丹冰Aceld」的音色、主播形象与讲课风格…
  100.0  aceld-course  「刘丹冰Aceld」课程制作全套流水线…
【线上】skills.sh 按安装量
    3.9k  feicaiclub/video-spec-builder/video-spec-builder
【结论】
  → 直接用本地 `aceld-voice`（匹配度 100）。
```

| 结论 | 下一步 |
|---|---|
| 直接用本地 X（≥35 分） | 回到 X 的流程做，**不要再检索** |
| 本地沾边（15–35 分） | 花 2 分钟 vet 线上最高安装量的那个，对比再决定 |
| 本地没有 | 写清缺口 → `find.py` → `vet.py` → `absorb.py` |
| 上游有更新 | `absorb.py --force` 重拉，比对指纹段 |

**评分规则**（踩过的坑都在这）：
- 正文（SKILL.md 章节）参与匹配 —— 「竖版」这种词永远不会写进 description
- 但**只靠正文命中封顶 20 分** —— 否则「pdf」会靠课程技能里「处理 PDF 讲稿」一句把自己顶到 34 分
- IDF 加权而非硬过滤 —— 小语料库里「音色」出现 4 次就被过滤掉，会让「配音」任务选错技能
- 同分优先正文更短的（更专注的）技能 —— 否则 `aceld-course` 和 `aceld-voice` 永远打平
- `aceld-findskill` 自己不进候选 —— 它是找技能的工具，不是答案

## 实测样例

```
$ python skill/scripts/vet.py vercel-labs/agent-skills/web-design-guidelines
体检对象  vercel-labs/agent-skills/web-design-guidelines
SKILL.md  skills/web-design-guidelines/SKILL.md（31 行正文）
仓库      ★33271  许可 NONE  最后提交 2026-10-28（0.1 个月前）
安装量    806092
frontmatter  name='web-design-guidelines'  desc=184 字
硬性淘汰  ✓ 无
风险提示  ! 无明确许可：只能读它的方法，不能复制它的代码与原文
安全扫描  ✓ 无
结论：WARN
```

## 五条硬性淘汰线

| # | 检查项 | 阈值 |
|---|---|---|
| 1 | `SKILL.md` frontmatter 合法 | `name` 小写连字符 ≤64 且等于目录名；`description` 1–1024 字 |
| 2 | 许可明确 | MIT/Apache-2.0/BSD/ISC/MPL/Unlicense → ok；GPL/无许可 → 只读方法；NC/ND → 拒绝 |
| 3 | 仍在维护 | 近 12 个月有提交 |
| 4 | 有真实使用 | 安装量 ≥1000 **或** 源仓库 ≥100★ |
| 5 | 结构合规 | 正文 <500 行、引用一层深、无绝对路径 |

## 三条铁律

1. **默认不自动安装** —— 检索到的只进 inbox，装不装是人决定的
2. **吸收方法论，不搬代码** —— 别人的结构/检查清单是资产，别人的脚本是负债
3. **没做过安全扫描的技能，等同于恶意技能** —— Skill 会被 Agent 当指令执行，比 npm 包更危险

## 目录

```
aceld-findskill/
├── README.md
├── install.sh / install.ps1
├── requirements.txt
└── skill/
    ├── SKILL.md
    ├── references/
    │   ├── 01-gap.md            缺口判定：什么算缺、怎么写成一句话、别搜的四种情况
    │   ├── 02-sources.md        检索源与真实 API（含限流配额表）
    │   ├── 03-vet.md            五条淘汰线细则 + 打分表 + 四种「看起来好其实不能用」
    │   ├── 04-security.md       OWASP AST 对照 + 18 条规则 + 人工复核清单
    │   ├── 05-absorb.md         吸收五问、回写模板、冲突处理
    │   └── 06-maintenance.md    来源索引、漂移检查、体检节奏、淘汰机制
    └── scripts/
        ├── preflight.py
        ├── find.py
        ├── vet.py
        ├── absorb.py
        └── register_source.py
```

## 给已有技能加「开工前置检查」

任何技能都可以在 `SKILL.md` **最顶部**（不是末尾）加这一块：

```markdown
> ### ⚑ 开工前置检查（每次先跑，30 秒）
> ```bash
> python ~/.workbuddy-ai/skills/aceld-findskill/scripts/preflight.py "本次任务关键词"
> ```
> ① 直接用本地 X → 继续按本技能做；
> ② 本地没有 / 线上更强 → 走 aceld-findskill 检索 + 体检，别硬编；
> ③ 上游有更新 → 先看差异再决定。
```

同时要写清**本技能覆盖不了什么**，否则 Agent 会默认「有这个技能就能干这件事」。

判断标准：**如果这一步你在硬写一个自己没把握的实现，就是该跑 preflight 的信号。**

## 许可

MIT（本仓库自身代码）。检索到的第三方技能各自遵循其原许可——见 `references/03-vet.md`。
