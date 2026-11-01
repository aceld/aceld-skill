# 刘丹冰Aceld 架构图绘制技能（aceld-diagram）

刘丹冰Aceld 的 **draw.io 默认主题白底扁平风**架构图技能：圆角矩形模块、圆柱存储、虚线分组、便签标注、细线小箭头、左侧「鹰眼」监控列。

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

## 效果示例

见 [`examples/kisflow_arch.html`](examples/kisflow_arch.html)（KisFlow 流式计算引擎架构），源 spec 在 [`examples/kisflow_arch.json`](examples/kisflow_arch.json)。

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
| 监控 | 左侧蓝色「鹰眼」竖条（可选） |
| 连线 | ~2.2px 正交小箭头：上下分离竖进竖出、同行并排横进横出；连线画在节点之下（跨盒被遮）、同边端口自动错开、跨线白晕留桥、标签自动避让；虚线表控制/依赖 |

完整规范、真实配色 token、适用场景与反模式见 [`skill/references/style-guide.md`](skill/references/style-guide.md)。

## 目录结构

```
aceld-diagram/
├── install.sh / install.ps1     一键安装（把 skill/ 拷到技能目录）
├── requirements.txt
├── README.md                    本文件
├── skill/
│   ├── SKILL.md                 技能入口
│   ├── references/
│   │   └── style-guide.md       风格提炼 + 配色 + 反模式（画前必读）
│   ├── scripts/
│   │   └── gen_diagram.py       零依赖 SVG 生成器
│   └── assets/
│       └── diagram.example.json spec 模板（KisFlow 示例）
└── examples/
    ├── kisflow_arch.json        示例输入
    └── kisflow_arch.html        示例输出（浏览器查看）
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
