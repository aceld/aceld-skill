# Aceld 架构图绘制技能（aceld-diagram）

刘丹冰(Aceld) 的**工程架构师手绘风**架构图技能：白底扁平、纵向分层、莫兰迪粉彩组件、虚线分组、序号标注、左侧鹰眼监控列、Redis 虚线框 / Mysql 深蓝实底。

把「Aceld 的图怎么画」沉淀成可复用规范 + 一个零依赖生成器，照着画或自动生成都行。

## 这是什么

一份**风格规范**（`skill/references/style-guide.md`）+ 一个**零依赖 SVG 生成器**（`skill/scripts/gen_diagram.py`）。

- 想自动出图：写一份 JSON spec，跑生成器，得到 SVG / HTML。
- 想手画或评审：照 style-guide 的清单与反模式执行。

## 快速开始

```bash
# 1) 复制模板
cp skill/assets/diagram.example.json ./my_diagram.json

# 2) 改字段（groups / stages / callouts / storage …，无需坐标）

# 3) 生成
python skill/scripts/gen_diagram.py ./my_diagram.json -o my_diagram.html
# 同时产出 my_diagram.html（浏览器直接看）和 my_diagram.svg
```

无网络、无第三方库即可运行（YAML 才需要 `pyyaml`）。

## 效果示例

见 [`examples/realtime_pipeline.html`](examples/realtime_pipeline.html)（实时数据接入与分发架构），源 spec 在 [`examples/realtime_pipeline.json`](examples/realtime_pipeline.json)。

## 风格速览

| 要素 | Aceld 的画法 |
|---|---|
| 背景 | 纯白，扁平，无渐变/阴影 |
| 分层 | 纵向 Tier，右侧青色竖排中文标签 |
| 组件 | 圆角矩形 / 小圆点，莫兰迪粉彩 + 细灰边，同类同色 |
| 分组 | 浅灰虚线圆角框（Kafka Topic / 消费组 / 层） |
| 管道 | 一列小圆点纵向堆叠 + 向下箭头，多列重复 |
| 序号标注 | 实心圆 + 白字数字，红/蓝区分语义 |
| 监控 | 左侧蓝色「鹰眼」竖条 |
| 存储 | Redis 虚线白框；Mysql 深蓝灰实底白字 |

完整规范、配色 token、适用场景与反模式见 [`skill/references/style-guide.md`](skill/references/style-guide.md)。

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
│       └── diagram.example.json spec 模板
└── examples/
    ├── realtime_pipeline.json   示例输入
    └── realtime_pipeline.html   示例输出（浏览器查看）
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

装完重启会话，对 Agent 说「用 Aceld 的风格画一张 XX 架构图」即可。

## 许可

[MIT License](../LICENSE)，可自由用于商业项目。
