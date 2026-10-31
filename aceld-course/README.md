<div align="center">

# Course Studio · AI 课程制作流水线

**给一份讲稿，产出一节完整的课：动画幻灯片 → 配音 → 成片 → 图文 → 图卡 → 封面。**

一个可直接安装使用的 Agent Skill，把「做一节课」从反复试错变成一条走得通的流水线。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#)

</div>

---

## 这是什么

这是一个 **Agent Skill（技能包）**，不是又一个「AI 一键生成视频」的黑盒。

它沉淀的是一套**已经跑通过 5 节 30 分钟长课**的工程流水线：怎么把讲稿切成页面、怎么让动画卡在说话的节拍上、怎么克隆音色而不丢句末的字、怎么把 40 个分片拼成不漂移的成片。

装上之后，你对 AI 说一句「帮我做一节讲 XXX 的课」，它会照着这条流水线推进，而不是每次从零开始踩坑。

**适合谁**

- 做技术课程 / 知识科普视频的创作者
- 需要批量产出「视频 + 长文 + 短图卡」多平台内容的人
- 想让 AI 替自己把重复劳动干完，但要求成品能直接发出去的人

---

## 能做出什么

一节课 = 7 个阶段，每个阶段都有产物和对应脚本：

| 阶段 | 产物 | 说明 |
|---|---|---|
| ① 知识点设计 | `segments.json` | 按页切分的讲稿，一页一个知识点 |
| ② 讲稿编写 | 逐字稿 | 口语化、可朗读、带动画触发词 |
| ③ 动画幻灯片 | `clips/slide_XX.mp4` × N | 1920×1080 深色科技风，逐帧可控 |
| ④ 配音 | `voice/seg_XX.wav` + `meta.json` | 零样本音色克隆 + ASR 质检 |
| ⑤ 视频合成 | `第X课-XXX.mp4` | 课件 + 主播小窗 + 字幕，音画严格同步 |
| ⑥ 图文文章 | `第X课（文字版）.md` | 长文，可直贴公众号 |
| ⑦ 分发物料 | 小红书图卡 + 横竖版封面 | 1080×1440 图卡 / 1146×717 + 1080×1920 封面 |

一份内容，四个平台的成品。

---

## 一键安装

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

安装脚本只做一件事：把 `skill/` 复制到 Agent 的技能目录。

| 目标 | 路径 |
|---|---|
| 默认（WorkBuddy / CodeBuddy） | `~/.workbuddy-ai/skills/course-studio/` |
| Claude Code | 加参数 `--claude` → `~/.claude/skills/course-studio/` |
| 自定义 | 加参数 `--dest <路径>` |

装完重启会话，问一句「你会做课吗」验证是否加载。

> 不想用脚本？把 `skill/` 整个目录手动拷到技能目录，改名 `course-studio` 即可。

---

## 5 分钟上手

**第 1 步：建工作目录**

```bash
mkdir my-course && cd my-course
cp <repo>/aceld-course/skill/assets/course.example.yaml ./course.yaml
```

**第 2 步：填 `course.yaml`**

```yaml
author: 你的名字            # 出现在署名、封面、片尾
course_title: 我的课程系列    # 出现在面包屑、封面角标

# 音色克隆用的参考音频：你自己录的 8~12 秒干净人声
voice:
  ref_file: assets/voice_ref/my_voice.wav
  ref_text: "把这段音频里说的话，一字不差地写在这里"

paths:
  ffmpeg: ffmpeg            # 在 PATH 上就写 ffmpeg
  cosyvoice: ./tts_engines/CosyVoice
  cosyvoice_model: ./tts_engines/pretrained_models/CosyVoice2-0.5B
```

**第 3 步：准备音色参考（最关键的一步）**

录 8~12 秒你自己说话，要求：

- 首尾干净，**结尾说完最后一个字就停**，不要留杂音、不要硬切
- 正常语速，不要刻意放慢
- 16k 以上采样率，单人、无背景音乐

> 参考音频不干净，后面所有段落都会在句尾冒出怪音。这一步值得反复重录。

**第 4 步：开做**

```
帮我做一节讲「XXX」的课，大约 25 分钟，20 页左右。
```

接下来它会依次产出讲稿、幻灯片、配音、成片。中途你可以只要求某一环重做。

---

## 沉淀了什么（这是这个仓库真正的价值）

不是「AI 能生成视频」，而是下面这些**不看就会重踩一遍**的结论：

| 结论 | 不看会怎样 |
|---|---|
| 动画时间轴必须用 **ASR 词级真实时间**，不能用字数比例估算 | 讲得越细漂得越厉害，字幕/动画/语音三者对不上 |
| 动画步骤写**触发词**（讲稿原样子串），不写秒数 | 改一次讲稿就要重算全片时间 |
| 分片渲染每页会多 **~0.08s**，30 页累计 2 秒以上 | 合成时必须用 ffprobe 实测时长，不能用声明值 |
| 淡出用 **6ms 不是 28ms** | 句末轻声（的/了/停）被削掉，听感是「最后几个字没了」 |
| 静音裁剪头部严（-22dB）尾部宽（-34dB） | 头部太松 → 句首「杂质」；尾部太严 → 系统性丢字 |
| 音色克隆 `speed` **不要动**（保持 1.0） | 频谱线性插值拉伸，0.6 直接发闷，调不回来 |
| 多音字/英文走**替换表**，只改送模型的文本 | 「行」读 xíng、「转」读 zhuǎn、英文变中文腔 |
| 幻灯片里 `draw` 动效会**覆盖虚线样式** | 讲稿说「紫色虚线」，画面是实线 |
| `ffmpeg -loop 1` 图片 overlay 必须带 **`shortest=1`** | 输出永不结束，36 分钟源能编到 1 小时 |
| 公众号正文**禁用渐变背景** | 粘贴时弹「内容结构检测」，遮罩挡住编辑器，粘贴静默失败 |

完整清单见 [`skill/references/09-pitfalls.md`](skill/references/09-pitfalls.md)。

---

## 目录结构

```
aceld-skill/                         仓库根（技能合集）
└── aceld-course/                    本技能（自包含，可单独 clone / 安装）
    ├── install.sh / install.ps1     一键安装
    ├── requirements.txt             Python 依赖
    ├── README.md                    本文件
    ├── skill/                       技能本体（拷到技能目录即可用）
    │   ├── SKILL.md                 入口：7 阶段总览 + 决策树 + 索引
    │   ├── references/              分章深度文档
    │   │   ├── 01-script.md         知识点设计与讲稿
    │   │   ├── 02-slides.md         动画幻灯片
    │   │   ├── 03-voice.md          配音（CosyVoice2 零样本克隆）
    │   │   ├── 04-compose.md        合成与字幕
    │   │   ├── 05-article.md        图文文章
    │   │   ├── 06-xhs.md            小红书图卡
    │   │   ├── 07-cover.md          横版/竖版封面
    │   │   ├── 08-wechat.md         公众号草稿发布
    │   │   └── 09-pitfalls.md       踩坑清单与验收 SOP
    │   ├── scripts/                 可直接跑的脚本
    │   │   ├── config.py            配置加载（唯一的路径来源）
    │   │   ├── gen_common.py        幻灯片 CSS/JS 动效库
    │   │   ├── build_deck.py        组装 deck.html（含触发词校验）
    │   │   ├── render_slides.py     逐帧渲染成 mp4
    │   │   ├── tts_cosy.py          配音 + ASR 质检
    │   │   ├── align_asr.py         ASR 强制对齐 → 真实时间轴
    │   │   ├── compose.py           合成成片（字幕/混音/响度）
    │   │   ├── deess_np.py          去齿音（STFT，避免 sidechain 泵动）
    │   │   ├── md2html.py           长文预览
    │   │   ├── num2cn.py            数字转中文（送 TTS 用）
    │   │   ├── make_cover.py        横版/竖版封面
    │   │   └── xhs_kit.py           小红书图卡组件库
    │   └── assets/
    │       ├── course.example.yaml  配置模板
    │       └── theme.example.yaml   世界观主题模板
    └── examples/
        ├── deck_example.py          四页幻灯片的完整写法（含触发词）
        └── segments.example.json    讲稿格式示例
```

---

## 依赖

**必需**

| 依赖 | 用途 |
|---|---|
| Python 3.10+ | 全部脚本 |
| ffmpeg / ffprobe 5.0+ | 渲染、合成、探测时长 |
| Chrome（系统安装即可） | Playwright 渲染幻灯片 |
| `playwright` `numpy` `soundfile` `pyyaml` `pillow` | 见 `requirements.txt` |

**配音相关（阶段④才需要）**

| 依赖 | 用途 |
|---|---|
| `CosyVoice2-0.5B` 模型（约 5GB） | 零样本音色克隆 |
| `torch` + CUDA（可选，CPU 也能跑但慢） | 推理 |
| `faster-whisper` + `large-v3` | 配音质检、时间轴对齐 |
| `soxr` | 重采样 |

**可选**

- `pygments` —— 公众号代码高亮
- `PyYAML` —— 配置文件解析

```bash
pip install -r requirements.txt
```

> 只做幻灯片 + 合成（不配音）的话，装 `playwright numpy soundfile pyyaml` 就够了。

---

## 常见问题

**Q：一定要 GPU 吗？**
配音建议有。8GB 显存的笔记本 GPU 跑 CosyVoice2 约 0.6 RTF（30 分钟音频约 25 分钟跑完）。纯 CPU 能跑但慢 5~10 倍。不做配音的话完全不需要 GPU。

**Q：必须用 CosyVoice2 吗？**
配音脚本是解耦的，`tts_cosy.py` 只负责「给文本 → 出 wav」。换 F5-TTS、GPT-SoVITS、edge-tts 都可以，只要产出 `voice/seg_XX.wav` + `meta.json` 同结构即可。但 `03-voice.md` 里的参数结论是针对 CosyVoice2 实测的。

**Q：一定要有主播小窗吗？**
不要也行。`course.yaml` 里 `video.avatar: null` 即可，成片就是纯课件 + 字幕。

**Q：主题一定要是仙侠风吗？**
不。`theme.example.yaml` 里的术语映射只是**一个示例**。你可以换成任何世界观（武侠、科幻、游戏、纯技术风），或者干脆不要包装——把 `theme.mode` 设为 `plain`。

**Q：能只做文章、不做视频吗？**
能。7 个阶段互相独立，只要有一份讲稿，直接进阶段⑥。

**Q：Windows 上 `python` 被应用控制策略拦了怎么办？**
用同版本的 `pythonw.exe` 代替，功能一致。这是 Windows 应用控制策略按文件哈希拦截导致的，重命名/复制无效。

---

## 出处与许可

本流水线由 [@aceld](https://github.com/aceld) 在制作 5 节 30 分钟技术长课的过程中逐步沉淀，原为个人私用技能，现整理为通用版本开源。

代码以 [MIT License](LICENSE) 发布，可自由用于商业项目。

文档中的技术结论来自真实踩坑，欢迎提 Issue 补充你自己的经验——这个仓库最好的用法是**持续往里加新的坑**。

---

<div align="center">

如果这个仓库帮你省下了第一次做课的时间，点个 Star 就是最好的回礼。

</div>
