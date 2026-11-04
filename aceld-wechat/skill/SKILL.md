---
name: aceld-wechat
description: 微信公众号文章编写与发布全流程。涵盖「怎么写」（标题公式、现象→病机→解法骨架、去 AI 味、配图节奏）与「怎么发」（markdown 转微信内联样式 HTML、零凭据粘贴进编辑器、图片自动转 mmbiz、只存草稿绝不发表）。当用户要写公众号文章、把 markdown 排成公众号版式、发布到微信公众号草稿箱、或遇到「粘贴后正文变空/图片裂了/标题填不进去」时使用。
---

# 公众号文章：编写与发布

两条线：**写得像人话**（`references/article-style.md`）、**发得不丢样式**（`references/wechat-constraints.md`）。
脚本负责把 markdown 变成微信能吃的 HTML，再把它塞进编辑器。

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

---

## 零、这个技能不碰你的账号

**硬约束：仓库里没有任何凭据。**

| 东西 | 在哪 |
|---|---|
| 账号密码 | 不存在。登录靠你自己在 Chrome 里扫码 |
| AppID / AppSecret | 不使用。走的是浏览器界面，不是官方 API |
| Cookie / token | 不落盘。token 每次从地址栏现抓，进程结束就没了 |
| 作者名 / 公众号名 | 只在 `assets/theme-*.json` 里作为**示例文案**，改成你自己的 |

想把个人文案（署名、banner）放本地而不进仓库，就用 `assets/theme.local.json`
并确认 `.gitignore` 里有它。

---

## 一、第一次使用

### 1. 启动一个带调试端口的 Chrome

普通打开 Chrome 是不行的，必须带 `--remote-debugging-port`。
建议用**独立 profile**，这样和你日常浏览器互不干扰，登录态也会保留：

```bash
# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" \
  --remote-debugging-port=9222 \
  --user-data-dir="%USERPROFILE%\.chrome-wechat" \
  https://mp.weixin.qq.com/

# macOS
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.chrome-wechat" \
  https://mp.weixin.qq.com/
```

### 2. 扫码登录

在弹出的窗口里扫码。**判断是否成功只看一件事**：地址栏变成
`https://mp.weixin.qq.com/cgi-bin/home?...&token=数字`。
首屏那个二维码渲染出来不代表失败，等几秒它自己会跳。

### 3. 自检

```bash
python scripts/doctor.py
```

全 `[OK]` 就说明：端口通、已登录、有编辑页、选择器没失效、按钮找得到。
任何一项 `[X]`，按提示处理（微信改版时选择器会失效，见 `references/wechat-constraints.md` 第五节）。

---

## 二、写文章

先读 `references/article-style.md`，核心就四条：

1. **标题**带数字、带判断，副题里的数字正文要对得上
2. **开篇三段式**：接上文 → 转折 → 先给结论
3. **骨架**：现象 → 病机 → 解法，现象和解法数量必须一一对应
4. **去 AI 味**：删「首先/其次/总之」，短句，给数字不给形容词

配图用 `aceld-diagram` 出图，放 `文章配图/` 下，正文用
`![图注](文章配图/v2/fig01.png)` 引用。图注写「这张图说明了什么」。

---

## 三、排版：markdown → 微信 HTML

```bash
python scripts/md2wechat.py \
  --src 第六课（文字版）.md \
  --out work/公众号版.html \
  --theme assets/theme-aceld.json
```

图片在这一步**不读盘**，只把 `![图注](文章配图/v2/fig01.png)` 里的路径
剥掉 `文章配图/` 前缀，写成占位 URL `http://127.0.0.1:8792/v2/fig01.png`。
真正的图片文件由下一步 `publish.py --img-dir` 读取并转 base64。

输出会自检并打印：

```
TITLE     : 凡人AI修仙（第六课）：守心之道 —— 智能体长任务，为什么不跑偏
HTML_LEN  : 112245
H2/H3     : 14 / 22
IMG_REF   : 12  IMG_TAG: 28
GRADIENT  : 0（必须为 0，微信会拦渐变）
```

**`GRADIENT` 不是 0 就别往下走**，粘贴会被「内容结构检测」拦掉，正文变空且没有报错。

支持的 markdown 语法：

| 语法 | 渲染成 |
|---|---|
| `## 一、xxx` | 章节卡（PART 01 标签 + 圆形序号徽章） |
| `## 开场` / `## 写在最后` / `## 下节预告` | 特殊徽章（序 / 终 / 预告） |
| `### 3.1 xxx` | 左侧橙竖条小标题 |
| 小节第一段 | 导语块（浅底 + 左竖条 + 加粗） |
| `> 引用` | 蓝色左边框引用块 |
| `==高亮==` | 黄底棕字 |
| `**加粗**` | 深蓝加粗 |
| `` `代码` `` | 行内代码 |
| ``` 代码块 ``` | pygments 内联高亮 |
| 表格 | 斑马纹表格 |
| `---` | 分隔线图片 |
| `![图注](路径)` | 居中图 + 图注 |

### 换配色 / 换文案

复制 `assets/theme-aceld.json` 改 `colors`，`banner` / `footer` 设成 `null` 就不渲染。
也可以用 `--no-banner --no-footer` 单独关掉。

---

## 四、发布：粘进编辑器 → 存草稿

```bash
# 已有编辑页
python scripts/publish.py --html work/公众号版.html --meta work/meta.json --img-dir 文章配图

# 让脚本自己开一个新建图文页
python scripts/publish.py --html work/公众号版.html --meta work/meta.json --img-dir 文章配图 --new

# 只检查图片和体积，不动浏览器
python scripts/publish.py --html work/公众号版.html --meta work/meta.json --dry-run
```

流程与判定：

```
close_dialogs → 全选 → 写剪贴板(base64) → Control+V
  → 校验 imgs > 0        ★ 闸门：为 0 立即退出，绝不用空文覆盖草稿
  → 填标题（三路兜底）
  → 轮询 data: → mmbiz（最多 3 分钟）
  → 点「保存为草稿」
  → 打印 FINAL {saved:true, mmbiz:28, data:0}
```

看到这个才算成功：

```json
{"title":"...","mmbiz":28,"data":0,"h2":14,"saved":true,"failed":false}
```

`data` 必须为 0 —— 不为 0 说明还有图没传上去，存草稿后打开就是裂图。

### 改已有草稿

编辑页 URL 带 `appmsgid=` 时，脚本会 reload 后**全选替换**，存草稿 = 更新同一份，
不会产生重复草稿。所以改文章的正确做法是：先打开原来那篇草稿，再跑脚本。

### 它永远不会点「发表」

脚本里没有「发表」这个动作。发布这一步留给人，自己看一眼预览再点。

---

## 五、常见故障

| 现象 | 原因 | 处理 |
|---|---|---|
| 粘贴后正文是空的 | 用了 `linear-gradient`，被「内容结构检测」拦了 | 改纯色，重跑 `md2wechat.py` 看 `GRADIENT: 0` |
| 粘贴后正文是空的（没渐变） | 上一次的模态框还留着 | `close_dialogs()` + `reload()`，再重跑 |
| 图片全是裂图 | 还是 `data:` 没转 mmbiz | 等久一点；或图太大，降到 1200px 分批贴 |
| 标题保存后没了 | 直接给 `textarea#title` 赋值 | 必须往 `#js_title_main .ProseMirror` 真实输入，见 constraints 第五节 |
| 点标题点不进去 | 点在元素正中心，被 `.title-editor-overlay` 吃了 | 点 `rect.x + 30` |
| 「请重新登录」 | 编辑器 URL 少了 `token=` | 从首页标签页现抓 token |
| `connect_over_cdp` 报错 | Chrome 没带调试端口 | 按第一节重启 |
| 选择器全失效 | 微信改版 | 跑 `doctor.py` 看哪个失效，按 constraints 第五节重找 |

---

## 六、文件

```
aceld-wechat/
├── SKILL.md
├── scripts/
│   ├── md2wechat.py      markdown → 内联样式 HTML（自检渐变）
│   ├── publish.py        粘贴 → mmbiz → 存草稿（零凭据，绝不发表）
│   └── doctor.py         发布前环境自检
├── assets/
│   └── theme-aceld.json  示例主题（配色 + banner/footer 文案）
└── references/
    ├── wechat-constraints.md   微信编辑器 8 类硬约束 + 踩坑记录
    └── article-style.md        标题、结构、去 AI 味、自检清单
```

依赖：`playwright`（连 CDP）、`pillow`（压图）、`pygments`（代码高亮，可选）。

```bash
pip install playwright pillow pygments
```
