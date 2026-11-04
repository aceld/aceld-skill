# 刘丹冰Aceld 公众号写作与发布技能（aceld-wechat）

把「公众号文章怎么写、怎么排版、怎么发」沉淀成一套规范 + 三个脚本。
**零凭据**：不碰账号密码、不用 AppID/AppSecret、不存 Cookie 和 token。

## 这是什么

- **写作规范**：`skill/references/article-style.md` —— 标题公式、现象→病机→解法骨架、去 AI 味、配图节奏、发布前自检清单
- **排版脚本**：`skill/scripts/md2wechat.py` —— markdown → 微信内联样式 HTML（主题可换）
- **发布脚本**：`skill/scripts/publish.py` —— 粘进编辑器、图片自动转 mmbiz、**只存草稿绝不发表**
- **环境自检**：`skill/scripts/doctor.py` —— 端口 / 登录 / 选择器 / 按钮，一次全查

## 为什么不走官方 API

官方「新建草稿」接口要 AppID + AppSecret + IP 白名单，而且会**过滤排版**，
复杂样式传上去基本变形，图片还得先传素材库换 `media_id`。

这个技能走另一条路：**复用你已登录的浏览器**。

| | 官方 API | 本技能（CDP + 剪贴板） |
|---|---|---|
| 凭据 | AppID + AppSecret | **无** |
| IP 白名单 | 要配 | 不要 |
| 排版保真 | 会被过滤 | 100%（所见即所得） |
| 图片 | 先传素材库 | 粘贴时自动上传 |
| 自动化程度 | 全自动 | 需开着浏览器 |

代价是必须有一个开着调试端口的 Chrome。对「自己写自己发」这个场景，这笔交易很划算。

## 快速开始

```bash
# 0) 依赖
pip install playwright pillow pygments

# 1) 启动带调试端口的 Chrome（独立 profile，登录态会保留）
#    Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\.chrome-wechat" https://mp.weixin.qq.com/
#    macOS
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="$HOME/.chrome-wechat" https://mp.weixin.qq.com/

# 2) 扫码登录，确认地址栏出现 token=数字

# 3) 自检
python skill/scripts/doctor.py

# 4) 排版
python skill/scripts/md2wechat.py --src 文章.md --out work/公众号版.html

# 5) 存草稿
python skill/scripts/publish.py --html work/公众号版.html --meta work/meta.json --img-dir 文章配图 --new
```

看到 `{"saved":true,"mmbiz":28,"data":0}` 就成功了，去草稿箱预览、确认无误后自己点发表。

## 隐私边界

仓库里**没有任何**：

- 账号 / 密码 / 扫码凭证
- AppID / AppSecret
- Cookie / token / openid
- 服务器 IP

token 是运行时从地址栏现抓的，进程结束就没了。`assets/theme-aceld.json` 里的署名、
banner 文案都只是**示例**，改成你自己的；不想进仓库就用
`assets/theme.local.json`（已在 `.gitignore`）。

## 目录

```
aceld-wechat/
├── README.md
├── install.sh / install.ps1
├── requirements.txt
└── skill/
    ├── SKILL.md
    ├── scripts/{md2wechat,publish,doctor}.py
    ├── assets/theme-aceld.json
    └── references/{wechat-constraints,article-style}.md
```

## 安装

```bash
bash install.sh                 # → ~/.workbuddy-ai/skills/aceld-wechat
bash install.sh --claude        # → ~/.claude/skills/aceld-wechat
```

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

## 实测

用这套流程发过《凡人AI修仙》第四、五、六课：

- 第六课：112 KB HTML、12 张架构图 + 2 张装饰图、14 个章节卡、5 个表格
- 粘贴后 28 个 `<img>`（每图 2 倍图）全部转成 `mmbiz.qpic.cn`，用时约 20 秒
- 正文 11900 字，草稿保存一次成功

## License

MIT
