# 刘丹冰Aceld 架构图绘制技能（aceld-diagram）

刘丹冰Aceld 的 **draw.io 默认主题白底扁平风**架构图技能：圆角矩形模块、圆柱存储、虚线分组、便签标注、细线小箭头、可选跨维度列（放全局/横切模块，非默认）。

把「刘丹冰Aceld 的图怎么画」沉淀成可复用规范 + 一个零依赖生成器，照着画或自动生成都行。风格提取自其 `鹰眼二期` / `KisFlow` 等 `.drawio` 源文件真实配色与图形。

## 这是什么

一份**风格规范**（`skill/references/style-guide.md`）+ 一个**零依赖 SVG 生成器**（`skill/scripts/gen_diagram.py`）。

- 想自动出图：写一份 JSON spec（节点/边/分组坐标），跑生成器，得到 SVG / HTML。
- 想手画或评审：照 style-guide 的清单与反模式执行。

## 快速开始

```bash
# 1) 复制模板
cp skill/assets/diagram.example.json ./my_diagram.json

# 2) 改坐标与字段（nodes / edges / groups / callouts …）

# 3) 生成
python skill/scripts/gen_diagram.py ./my_diagram.json -o my_diagram.html
# 同时产出 my_diagram.html（浏览器直接看）和 my_diagram.svg
```

无网络、无第三方库即可运行（YAML 才需要 `pyyaml`）。

## 生成时的自检

生成器收尾会打印三类告警，**看到就改，别忽略**：

| 告警 | 含义 | 改法 |
|---|---|---|
| `!! 连线重合 N 处` | 两条线走在同一段路上，看起来像一条粗线或断线 | 调坐标 / 加 `via` / 改用 `buses` |
| `!! 连线穿过节点 N 处` | 线穿过无关盒子，会被盒子整段遮住，只剩箭头悬着 | 改布局（首选）或用 `via` 绕开 |
| `!! 多余折线 N 处` | 能一条直线直达却硬折了一下 | 改坐标 / 删掉 `via` 里的冗余路点 / `straight:true` |

> ① ② ③ 三份历史案例 spec 会触发「穿节点」告警——这是 2026-11-05 新增诊断查出的**旧布局毛病**，不是生成失败。
> 新画的图按提示改坐标即可；④ 回归样例是零告警的。

## 成品案例

下面都是用本技能实际画出的架构图（预览为竖版；点开可看高清 PNG 与可编辑 spec）：

### ① KisFlow 流式计算引擎 · 竖版
![KisFlow 架构图](cases/kisflow.png)

源 spec：[`examples/kisflow_arch_portrait.json`](examples/kisflow_arch_portrait.json)（竖版）· [`examples/kisflow_arch.json`](examples/kisflow_arch.json)（横版）

### ② Zinx TCP 服务器框架 · 竖版（左侧跨维度列 = 接口层）
![Zinx 架构图](cases/zinx.png)

源 spec：[`examples/zinx_arch.json`](examples/zinx_arch.json)

> 左侧那条纵贯全图的 `接口层` 就是**跨维度列**的正确用法：放「贯穿所有模块的通用/横切模块」（接口层 / 监控 / 安全 / 全局配置），按图内容命名，**不是固定的「鹰眼」**。

### ③ 短链服务 ShortLink · 竖版（微服务分层）
![ShortLink 架构图](cases/shorturl.png)

源 spec：[`examples/shorturl_arch.json`](examples/shorturl_arch.json)

> 版式默认**竖版**（文档高度不限、宽度有限，竖版不被横向裁切）；PPT / 大屏再改坐标出横版。

### ④ 箭头置顶 + 直连不折 · 回归样例

![箭头与直连回归样例](cases/arrows_regression.png)

上下对齐的两盒之间是**一条直线**，不会中途横折一下；三支箭头都画在最上层，节点、分组标题、便签、标签白底都盖不住。改完生成器先跑这份 spec 看效果：[`examples/arrows_regression.json`](examples/arrows_regression.json)。

## 风格速览

| 要素 | 刘丹冰Aceld 的画法 |
|---|---|
| 背景 | 纯白，扁平，无渐变/阴影 |
| 模块 | 圆角矩形，1px 同色描边，中英混排居中 |
| 配色 | draw.io 默认调色板，**同一张图优先全实心重色**（蓝/橙/石板蓝/绿/深红/深灰，白字），深浅不混搭 |
| 存储 | 圆柱（MySQL / Redis / 日志） |
| 分组 | 浅色底 + 虚线圆角框 + 标题（算子池 / 调度核心 / 外部依赖），不同分组不同浅色相 |
| 层级 | 贯穿全图的横向虚线分隔 + 左端加粗层级名/说明（替代零散便签） |
| 标注 | 便签（note）贴一旁 |
| 跨维度列 | 左侧纵贯竖条承载全局/横切模块标签（可选，**非默认**；鹰眼仅鹰眼二期实例） |
| 连线 | ~2.2px 正交小箭头：上下分离竖进竖出、同行并排横进横出；**能直连就一条直线，不折无意义的弯**；主体线画在节点之下（跨盒被遮），**箭头末段单独提到最上层，永不被盖**；同边端口自动错开、跨线白晕留桥、标签自动避让；虚线表控制/依赖 |

完整规范、真实配色 token、适用场景与反模式见 [`skill/references/style-guide.md`](skill/references/style-guide.md)。

## 目录结构

```
aceld-diagram/
├── install.sh / install.ps1     一键安装（把 skill/ 拷到技能目录）
├── requirements.txt
├── README.md                    本文件
├── cases/                       成品案例预览图（README 画廊用）
│   ├── kisflow.png
│   ├── zinx.png
│   ├── shorturl.png
│   └── arrows_regression.png       箭头置顶 + 直连不折的回归预览
├── skill/
│   ├── SKILL.md                 技能入口
│   ├── references/
│   │   └── style-guide.md       风格提炼 + 配色 + 反模式（画前必读）
│   ├── scripts/
│   │   └── gen_diagram.py       零依赖 SVG 生成器
│   └── assets/
│       └── diagram.example.json spec 模板（KisFlow 示例）
└── examples/                    可编辑 spec + 生成结果（json / svg / html / png）
    ├── kisflow_arch.json / kisflow_arch_portrait.json
    ├── zinx_arch.json
    ├── shorturl_arch.json
    └── arrows_regression.json    箭头置顶 + 直连不折的回归样例
```

## 安装

### Windows（PowerShell）

```powershell
git clone https://github.com/aceld/aceld-skill.git
cd aceld-skill\aceld-diagram
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

### macOS / Linux

```bash
git clone https://github.com/aceld/aceld-skill.git
cd aceld-skill/aceld-diagram
bash install.sh
```

装完重启会话，对 Agent 说「用刘丹冰Aceld 的风格画一张 XX 架构图」即可。

## 许可

[MIT License](../LICENSE)，可自由用于商业项目。
