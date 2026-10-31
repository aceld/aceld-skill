# 04 · 音画同步、合成与字幕

## 1. 合成流程

```
输入：clips/slide_XX.mp4        （动画底片）
     voice/seg/seg_XX.wav      （配音）
     voice/seg/meta.json       （配音时长与分句）
     [可选] avatar/avatar.mp4  （主播小窗）
输出：第X课-XXX.mp4
```

```
1. concat 拼接 N 个 slide clip → video_base.mp4
2. numpy 拼接音频（每段后补 TAIL 静音，与画面时长对齐）
3. 响度对齐：目标 RMS -16.2dB + tanh 软膝限幅
4. 生成 ASS 字幕（用逐字 ASR 时间轴）
5. ffmpeg overlay：[底片] + [主播小窗] + [字幕带] + [ASS 字幕]
```

## 2. ★音画同步：必须用 ASR 真实时间轴

### 2.1 旧做法（已弃用）

句子起止按「字数比例」估算。

**后果**：讲得越细漂得越厉害，字幕、动画、语音三者对不上，观众一眼就能看出来。

### 2.2 新做法（`align_asr.py`）

```
1. faster-whisper large-v3 词级转写，得到每个词的起止时间
2. 把词展开成「字 → 时间」序列（词内按时长均分）
3. 与 TTS 实际读的文本做 difflib.SequenceMatcher 字符级对齐
4. 未匹配到的字用前后锚点线性插值
5. 产出 meta_asr.json：
   - lines[]   逐句真实起止（给字幕）
   - chars[]   每个原文字符的 t/e（给动画触发词）
```

**字幕直接用它**，不要再自己算比例。

### 2.3 两个 ASR 的坑

1. **传 numpy 数组必须自己重采样到 16k**（只有传文件路径时才自动解码）。
   否则会按 44.1k 当 16k 读 → 2.7 倍快放 → ASR 全乱码。
2. **防幻觉参数**：

```python
segments, _ = model.transcribe(
    path, language="zh",
    vad_filter=True,
    compression_ratio_threshold=2.0,
    temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    repetition_penalty=1.05,
    no_repeat_ngram_size=4,
)
```

## 3. ★分片渲染的累积漂移（必踩）

每页单独渲染成 mp4 时，ffmpeg 把时长对齐到 1/30 帧网格，
**每页实际时长比声明多 ~0.08s，30 页累计可达 2.2 秒**，越到后面画面越落后于字幕。

**对策：合成时必须用 ffprobe 读每个分片的实测时长来累加时间轴**，不能用渲染脚本里声明的 `dur`；
音频补齐也要按实测时长补，否则音画一起漂。

```python
def probe_dur(p):
    r = subprocess.run([FP, "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", p], capture_output=True, text=True)
    return float(r.stdout.strip())
```

局部重渲染（`ONLY=9,11`）时**不能复用旧 timeline**：重排后 `old[i]` 指向的是另一页。
对跳过的页要用 `probe_dur(现有 clip)` 取真实时长，保证 timeline 永远和磁盘一致。

## 4. ★字幕不要用 TTS 的粗切行

TTS 阶段为了粗对齐，会按**字数**把整段切成若干「行」，合成时再在这堆碎片上二次切分。
碎片边界本来就在词中间，后面再怎么切都救不回来。

实测：全片 496 行里有 387 行断在词中间（「么该丢。」）。

**正解：用「整段原文 + `chars` 逐字时间」重新切。**

```python
full = "".join(ln["text"] for ln in it["lines"])   # 整段原文
subs = split_long(full, 20)                        # 按标点切，20 字上限
pos = 0
for sub in subs:
    k = full.find(sub, pos)
    st = chs[k]["t"]
    en = chs[k + len(sub) - 1].get("e") or st + 0.15
    lines.append((it["start"] + st, it["start"] + en, sub))
    pos = k + len(sub)
```

行数从 859 降到 754，每行都是完整短语，时间还更准（逐字 ASR 时间）。

### 4.1 按标点切，不按字数切

```python
def split_long(text, maxlen=20):
    if len(text) <= maxlen:
        return [text]
    parts, cur = [], ""
    for ch in text:
        cur += ch
        if ch in "，、；：,;" and len(cur) >= maxlen * 0.65:
            parts.append(cur); cur = ""
        elif ch in "。！？":
            parts.append(cur); cur = ""
        elif len(cur) >= maxlen * 1.45:
            parts.append(cur); cur = ""
    if cur.strip():
        parts.append(cur)
    return [p for p in parts if p.strip()] or [text]
```

### 4.2 ASS 字幕样式

```
PlayResX: 1920   PlayResY: 1080   WrapStyle: 2
Style: Default,<字体>,44,&H00FFFFFF,...,1,2.4,0,2,70,490,30,1
```

- 底部居中（Alignment=2），MarginV 给足（避开底部安全区）
- 字体用系统字体名（Windows `Microsoft YaHei`，macOS `PingFang SC`）
- 单行时长不足 0.06s 时强制拉到 0.06s，否则一闪而过看不见

## 5. 响度对齐

```python
rms_db = 20 * math.log10(max(float(np.sqrt(np.mean(audio ** 2))), 1e-9))
audio = audio * (10 ** ((-16.2 - rms_db) / 20))

# tanh 软膝限幅，避免硬削波
thr, knee = 10 ** (-1.0 / 20), 10 ** (-1.0 / 20) * 0.65
ab = np.abs(audio)
audio = np.sign(audio) * np.where(
    ab > knee, knee + (thr - knee) * np.tanh((ab - knee) / (thr - knee)), ab)
```

目标 RMS -16.2dB 是视频平台比较安全的区间：手机外放够响，耳机听不炸。

## 6. 去齿音（de-esser）

**不要用 ffmpeg 的 `sidechaincompress` 做 de-esser。**
它是压缩器，ratio 9 / attack 3ms 的抽吸（pumping）会在齿音上产生「拉链声」，
听感就是「偶尔蹦出的尖锐刺耳噪音」——而客观指标（峰值、Flat factor、噪声底）全部正常，极难定位。

**用 numpy 平滑去齿音**：

```python
from deess_np import deess
audio, gmax, gmean = deess(audio, sr, ratio_thr=0.15, max_db=7.0, k=1.2)
```

原理：

- STFT 512 / hop 128，按「5.5k 以上能量 ÷ 以下能量」的**比值**判断 —— **与电平无关**，
  不会出现「小声段落完全不压、大声段落压过头」
- 增益在**增益域**做 attack 4ms / release 120ms 一阶平滑 → 没有拉链声
- 只衰减高频段，元音和低频完全不动（实测 RMS 只降 0.3%）
- 实测：平均衰减 ~3dB、最大 7dB；`|diff| > 0.35` 的采样点从 19~206 个降到 **0**

ffmpeg 那边只留**静态**轻处理（静态 EQ 不会产生任何时变伪影）：

```
highshelf=f=9000:g=-2,lowpass=f=11500,aresample=44100,
loudnorm=I=-16.0:TP=-2.0:LRA=11,alimiter=limit=0.95
```

**验收口径**：`astats` 的 `Flat factor == 0`；`np.abs(np.diff(a)) > 0.35` 的点数为 0。

### 6.1 只改音频的快路径

改后期链/去齿音强度时**不需要重跑整条管线**，也不用重编码视频：

```bash
ffmpeg -i in.mp4 -c:v copy <音频滤镜> -c:a aac -b:a 192k out.mp4
```

27 分钟视频约 2 分钟（整片 libx264 medium 重编码要 1h46m）。

## 7. 主播小窗

### 7.1 位置与尺寸

```
右下角，位置 (1500, 840)，尺寸 420×240
```

`course.yaml` 里配：

```yaml
video:
  avatar: "work/avatar/avatar.mp4"
  avatar_box: [1500, 840, 420, 240]
```

不要小窗就设 `avatar: null`，成片是纯课件 + 字幕。

### 7.2 ★素材短于成片时人会定格

`overlay` 默认 `eof_action=repeat`，素材播完就停在一帧上，观众一眼看出「人不动了」。

```python
run([FF, "-i", vbase, "-stream_loop", "-1", "-i", AVATAR, "-i", audio, ...])
```

`-stream_loop -1` 放在**它要作用的那一路 `-i` 之前**，输出靠 `-t total` 截断。
代价是循环接缝处有一次跳切——420×240 的小窗里可以接受，比定格好得多。

**验收方法**（别靠肉眼看单帧）：同一位置隔 1 秒取两帧，算小窗区域的平均像素差，> 1.5 就说明在动。

```python
d = np.abs(grab(t)[840:1080, 1500:1920].astype(int)
         - grab(t+1)[840:1080, 1500:1920].astype(int))
```

只取一帧永远看不出「冻结」。

### 7.3 素材来源

- **真人视频片段**（推荐）：正面机位，1080p 以上
- **静态照片 + 眨眼**（备选，效果较僵）：睁眼帧 + 眨眼帧循环

## 8. 竖版 9:16 转换（抖音 / 视频号 / 小红书视频）

### 8.1 用模糊填充，绝不裁切

横版是课件版式，直接 `crop=1080:1920` 会把架构图、表格两侧切掉。

```
[0:v]scale=1080:1920:force_original_aspect_ratio=increase,
     crop=1080:1920,
     scale=270:480, boxblur=10:2, scale=1080:1920,
     eq=brightness=-0.22:contrast=1.10:saturation=1.30[bg];
[0:v]scale=1080:-2:flags=lanczos[fg];
[bg][fg]overlay=(W-w)/2:(H-h)/2[base];
[base][1:v]overlay=0:0:shortest=1[out]
```

要点：

- 背景先降到 270×480 再模糊再放大 → 模糊半径便宜 16 倍，编码几乎不掉速
- `brightness=-0.22` + `contrast=1.10` + `saturation=1.30`：压暗后补色，不发灰
- 浅色课件多的话，模糊后背景很亮，白字会糊 → 需要加遮罩（见 8.2）

### 8.2 ★`-loop 1` 图片 overlay 必须带 `shortest=1`

```bash
ffmpeg -y -i src.mp4 -loop 1 -i overlay.png -filter_complex "…overlay=0:0:shortest=1[out]" \
       -map "[out]" -map 0:a -c:v h264_nvenc -preset p5 -rc vbr -cq 23 -b:v 0 \
       -pix_fmt yuv420p -c:a copy -shortest -movflags +faststart out.mp4
```

漏掉 `shortest=1` 时，图片是无限循环输入 → **输出永不结束**。
实测 36 分钟的源被编到 01:06:37 还在跑，差点把盘写爆。

### 8.3 标题遮罩：用「平台式压暗」，不要整段渐变

```
上部：y < 500 alpha 198，500..655 线性淡出到 0
下部：1285..1440 淡入，之后 alpha 205 恒定（保护字幕可读）
颜色：(3, 7, 16, a)
```

平台式（plateau）比整段线性渐变干净：文字区恒定压暗，且不留渐变带痕迹。

### 8.4 编码性能

`h264_nvenc -preset p5 -rc vbr -cq 23 -b:v 0` 实测 **4~6× 实时**（36 分钟约 8 分钟出片）。
没有 NVENC 就用 `libx264 -preset medium -crf 21`。

## 9. 成片规格（全片必须一致）

```
分辨率: 1920×1080（竖版 1080×1920）
帧率:   30 fps
编码:   H.264 yuv420p
音频:   AAC 44100Hz 立体声 192kbps
容器:   MP4 + faststart
```

## 10. 合成后的三项验收

1. `ffprobe -count_frames` → 帧数是否 = 时长 × 30
2. 抽关键时间点的帧 → **像素统计**判断元素是否出现（不要只靠肉眼看图，工具可能返回缓存图导致误判）
3. 抽首/中/尾三帧 → 人眼确认版式

```python
from PIL import Image
import numpy as np
a = np.array(Image.open(p).convert("RGB"))
r, g, b = a[:,:,0].astype(int), a[:,:,1].astype(int), a[:,:,2].astype(int)
mask = (abs(r-194) < 28) & (abs(g-51) < 30) & (abs(b-123) < 30)   # 目标颜色
print(mask[395:435, :].sum())                                     # 只看该元素所在的 y 带
```
