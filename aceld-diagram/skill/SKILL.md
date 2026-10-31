---
name: aceld-diagram
description: 刘丹冰(Aceld) 风格的架构图绘制技能。沉淀其「draw.io 默认主题」白底扁平风——圆角矩形模块、圆柱存储、虚线分组、便签标注、细线小箭头、左侧鹰眼监控列。当用户要画系统架构图、数据流/处理链路图、架构演进路线图，或要求「用 Aceld 的风格画图」「画一张扁平专业的架构图」时使用。调用 gen_diagram.py 按 node/edge/group 坐标自动生成 SVG。
---

# Aceld 架构图绘制 · draw.io 默认主题白底扁平风

把刘丹冰(Aceld) 多年沉淀的「架构图怎么画」变成可复用的技能。核心是**用最小可视化成本讲清系统怎么跑、数据怎么流、关键节点在哪**——纯白底、扁平、不追求花哨，追求一眼读懂。风格提取自其 `鹰眼二期` / `KisFlow` 等 `.drawio` 源文件真实配色与图形，而非主观想象。

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

**本技能覆盖不了**：时序图 / 状态机 / 桑基图 / 甘特图 —— 遇到直接走 ②，别用矩形硬拼。

---

## 0. 一句话定位

Aceld 的图是**白底、扁平、draw.io 默认主题**的：圆角矩形模块（1px 同色描边）、圆柱做存储、虚线框分组、便签做标注、细线小箭头、**左侧蓝色「鹰眼」监控列**纵贯全图。颜色取自 draw.io 内置调色板，同类语义同色。

## 1. 核心风格清单（画之前先记住）

1. **纯白底 + 扁平 + 零装饰**（无渐变/阴影/3D）。
2. **圆角矩形模块**（`rounded=1`）：1px 描边取同色系深一档；中文+英文混排、居中无衬线。
3. **配色用 draw.io 默认调色板**：蓝 `#1ba1e2`、绿 `#d5e8d4`、浅蓝 `#dae8fc`、红 `#f8cecc`、黄 `#fff2cc`、灰 `#E6E6E6`、石板蓝 `#647687`、橙 `#fa6800`、紫 `#e1d5e7`… 同类语义全图同色。**同一张图只在一种色系内选**（全浅色 pastel，或全实心重色），深浅不要混搭。详见 `references/style-guide.md`。
4. **数据库一律用圆柱**（`cylinder`）：MySQL / Redis / 日志存储等，浅色填充+同色描边。
5. **虚线分组括号 + 标题**：相关模块用虚线圆角框圈起并加标题（如 `Function 算子池`、`调度核心`、`外部依赖`）。
6. **便签（note）做标注**：补充说明贴在一旁，浅黄底小折角块。
7. **左侧「鹰眼」监控列**：蓝色竖条纵贯全图、内部白色横向堆叠「鹰眼」二字（不旋转、不溢出），代表全链路可观测（源自鹰眼二期，可选）。
8. **细线 + 小三角箭头**：线略粗（~1.8px）、箭头小而克制；正交折线走线、跨线白色光晕留白；实线表主数据流，虚线表控制/依赖（如 `调度`、`管理`、`连接`）。
9. **自由摆放、多图岛**：模块是手摆坐标而非自动布局；一张图可有多个相对独立的子系统，靠分组框区分。
10. **顺序链可用 chevron/step**：折角箭头块或起止圆表达处理顺序。

## 2. 两种用法

### 用法 A：自动生成（推荐，按坐标摆放）

编辑一份声明式 spec（JSON 即可，YAML 需装 PyYAML），运行生成器产出 SVG/HTML：

```bash
python skill/scripts/gen_diagram.py skill/assets/diagram.example.json -o out.html
# 同时得到 out.html（浏览器看）和 out.svg
```

spec 字段（坐标自由摆放，详见 `skill/assets/diagram.example.json`）：

| 字段 | 作用 |
|---|---|
| `meta.title` / `meta.subtitle` | 标题 / 副标题 |
| `monitor` | 左侧鹰眼监控列 `{label}`（可选） |
| `nodes[]` | 模块：`{id,x,y,w,h,fill(配色token),shape(rect\|cylinder\|note\|circle),label,fontSize,bold}` |
| `groups[]` | 虚线分组：`{nodes:[id...], title, stroke}` |
| `edges[]` | 连线：`{from,to,color,dashed,label}`（自动算边界锚点 + 小箭头） |
| `callouts[]` | 便签标注：`{at:[x,y], text, color}` |
| `panels[]` | 背景大色块：`{x,y,w,h,fill,label}`（可选） |
| `palette` | 覆盖/新增配色 token（可选） |

`fill` 取 style-guide 的配色 token（如 `blue/green/lblue/red/yellow/slate/orange/purple/gray`）；实心深色（`blue/orange/slate/sgreen`）自动配白字，浅色配黑字。改坐标与字段即可，**无需手写 SVG**。

### 用法 B：按规范手绘 / 指导

当需要口述或手画时，照 `references/style-guide.md` 的清单与反模式执行：白底、圆角矩形、圆柱存储、虚线分组、便签标注、鹰眼监控列、细线小箭头。

## 3. 决策树

```
用户要画图？
├─ 能给出组件/依赖清单 → 用法 A：写 JSON spec（nodes/edges/groups）跑生成器
├─ 只是想看「Aceld 风格长啥样」→ 直接打开 examples/kisflow_arch.html
└─ 要手画 / 评审一张图 → 用法 B：按 style-guide 清单核对
```

## 4. 反模式（不要做）

❌ 渐变/阴影/3D ❌ 中文衬线字体 ❌ 同类组件不同色 ❌ 粗描边/粗箭头抢戏
❌ 存储不用圆柱 ❌ 一张图塞爆（宁可拆多张）❌ 关系不分组、要点不标便签

## 5. 参考

- `references/style-guide.md` —— 风格提炼 + 真实配色 token + 适用场景 + 反模式（**画前必读**）
- `skill/scripts/gen_diagram.py` —— 零依赖 SVG 生成器（Python 标准库，含 YAML 兜底解析）
- `skill/assets/diagram.example.json` —— spec 模板（KisFlow 架构示例）
- `examples/kisflow_arch.json` + `.html` + `.svg` —— 生成效果示例

---

## 6. 能力缺口 → 动态找技能

本技能覆盖的是「静态架构图」。遇到下面这些信号，**不要硬画**，先去网上找：

| 信号 | 例子 |
|---|---|
| 要画的图形类型本技能没有 | 时序图、状态机、桑基图、甘特图、C4 模型 |
| 想要另一种风格 | 手绘风、暗色风、等距 3D、极简黑白 |
| 反复调不好 | 布局挤在一起调了半小时还挤 |

流程（由 `aceld-findskill` 技能提供）：

1. **写缺口** —— 一句话说清「输入 → 期望输出 → 约束」
   （例：一份 API 调用流程 → 时序图 SVG，白底扁平风，与现有架构图配色一致）
2. **检索** —— `python ~/.workbuddy-ai/skills/aceld-findskill/scripts/find.py "sequence diagram"`
3. **体检** —— `vet.py owner/repo/skill`：五条硬性淘汰线 + 安全扫描，`REJECT` 的一律不用
4. **吸收** —— 只拿「方法论与检查清单」，生成器按本技能的约定重写；**不复制别人的代码与原文**
5. **回写** —— 补进 `references/style-guide.md`，并在 `SOURCES.md` 登记来源与 commit

三条不许破：**不自动安装 / 不搬代码 / 没扫过安全的技能当恶意对待**。

判断标准很简单：**如果这一步你在硬写一个自己没把握的实现，就是该去找技能的信号。**
