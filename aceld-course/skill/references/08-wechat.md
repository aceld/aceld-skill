# 08 · 公众号草稿发布（可选）

> **铁则：只保存草稿，永远不自动点发表。** 发表这一步永远由人来做。

## 1. 流程

```
文字版.md
  → md2html / md2wechat（内联样式 HTML）
  → Playwright 驱动调试 Chrome 操作后台
  → 粘贴正文 → 补代码高亮 → 保存草稿
```

## 2. 浏览器环境

```bash
# ★ 必须用非默认 profile，否则 DevTools 拒绝启动
#   （报 requires a non-default data directory）
chrome.exe --remote-debugging-port=9222 --user-data-dir=<专用目录>
```

- 后台起 Chrome 必须用任务管理器的后台模式；shell `&` 起的进程会随会话结束被杀
- Python 连上去：`connect_over_cdp("http://127.0.0.1:9222")`
- 用户扫码登录后进草稿箱，点卡片 hover 出的「编辑」，**编辑器在新标签页打开**

## 3. ★编辑器 URL 必须带 token

从已登录的任意标签页 URL 里抓 `token=(\d+)`，拼到编辑器 URL 上，否则页面显示「请重新登录」。

**token 会轮换**，每次重新抓，不要写死。

**判断是否已登录**：打开 `https://mp.weixin.qq.com/` 会先渲染登录二维码，
几秒后 JS 自动重定向到 `/cgi-bin/home?...&token=xxx`。
**看重定向后的 URL 有没有 token，不要被首屏二维码骗去让用户重扫。**

## 4. ★编辑器 DOM 关键认知

1. **页面里有两个 `.ProseMirror`**：第一个是**标题框**（父级 `title-editor__input`，只 32 字），
   第二个才是**正文**（`#ueditor_0 .ProseMirror`）。
   查正文结构一定要用 `#ueditor_0 .ProseMirror`，用第一个会误判「正文是空的」。
2. **`window.__mpBodyChecktextView` 就是 ProseMirror 的 EditorView**（有 `.state` 含 schema、有 `.dispatch`）。
   DOM 元素的 `pmViewDesc` 拿不到 view（parent 为 null），别在它身上浪费时间。
3. **schema 里没有 section 节点**（只有 para / heading / blockquote / code / codeblock / horizontal / image / video）。
   DOM 里看到的 `<section style="...">` 是**带 style 的 para** 渲染出来的。
4. **`#title` 是 `<textarea>` 且 `visibility:hidden; height:0`**：
   `setter.call()` 报 Illegal invocation；`locator.click()` 因不可见超时。

   **可靠做法**（二选一）：
   ```python
   # 方案 A：JS 设值 + 派发事件
   ed.evaluate("""t => { const el = document.querySelector('#title');
                         el.value = t;
                         el.dispatchEvent(new Event('input', {bubbles:true}));
                         el.dispatchEvent(new Event('change', {bubbles:true})); }""", title)
   # 方案 B：聚焦后键盘输入
   # t.focus() → Ctrl+A → Delete → keyboard.type(中文, delay=40) → blur
   ```

## 5. ★粘贴正文：真剪贴板，不要合成事件

| 做法 | 结果 |
|---|---|
| 构造 `ClipboardEvent` 派发 | ❌ 正文为空 |
| `navigator.clipboard.write(text/html)` + `Ctrl+V` | ✅ 可行 |
| `execCommand('insertHTML')` | 部分场景被剥样式 |

```python
ctx.grant_permissions(["clipboard-read", "clipboard-write"])
page.evaluate("""async (html) => {
    const item = new ClipboardItem({
        'text/html':  new Blob([html],  {type: 'text/html'}),
        'text/plain': new Blob([html.replace(/<[^>]+>/g, '')], {type: 'text/plain'}),
    });
    await navigator.clipboard.write([item]);
}""", html)
page.keyboard.press("Control+V")
```

## 6. ★图片：内联 base64，不要起本地图床

HTTPS 的编辑器会拦 `http://127.0.0.1` 的图片（混合内容），
`--allow-running-insecure-content` 在新版 Chrome 已失效。

**正解：把图片转成 `data:` URI 内联进 HTML，编辑器会自动上传成平台 CDN。**

```python
# 先缩图，控制体积（24 张图 → base64 后约 1.7MB，剪贴板无压力）
img = Image.open(p)
if img.width > 1400:
    img = img.resize((1400, int(img.height * 1400 / img.width)), Image.LANCZOS)
buf = io.BytesIO()
img.convert("RGB").save(buf, "JPEG", quality=90)   # RGBA 图要存 PNG
b64 = base64.b64encode(buf.getvalue()).decode()
src = "data:image/jpeg;base64," + b64
```

粘贴后校验 `document.querySelectorAll('img').length > 0` 且图片 src 已变成平台域名，再保存。

## 7. ★禁用渐变背景（最危险的一个坑）

平台的暗色模式规范禁止「文字背景用渐变」（`darkmode-no-gradient`）。

用 `linear-gradient` 做底色，**粘贴时会弹出「内容结构检测」模态框**，
遮罩挡住编辑器 → **粘贴静默失败，正文变空**，且提示会列出一大串「第 N 段 darkmode-no-gradient」。

**一律用纯色底。** 需要层次感就用「浅色块 + 细边框 + 圆角」。

## 8. ★残留模态框会毒害下一次粘贴

上一次保存后如果留着「内容结构检测」框没关，下次再粘贴同样被遮挡。

**发布前必做**：

```python
close_dialogs(page)      # 关掉所有可见模态框
page.reload()            # 恢复已存草稿
# 等正文加载完成（textLen > 500）
```

**粘贴后必须校验 `imgs > 0` 才允许点保存**，否则会拿空文章覆盖好草稿。
失败就重试，两次都失败就中止并报错，不要硬保存。

## 9. 代码高亮

平台的编辑器会剥掉「只包含空白字符的 span」（哪怕有 style），
但保留「同时包含非空白文本和空白的 span」。

正确做法（token 流 + whitespace merge）：

```python
from pygments import lex
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name

def highlight(lang, code):
    lexer = get_lexer_by_name(lang or "text", stripall=True)
    style = get_style_by_name("friendly")

    # 1) whitespace token 的文本合并进相邻的 non-whitespace token
    merged, pending = [], ""
    for ttype, value in lex(code, lexer):
        if value.strip() == "" and value != "":
            pending += value
        else:
            if pending:
                value = pending + value
                pending = ""
            merged.append((value, style.style_for_token(ttype)))
    if pending and merged:
        t, st = merged[-1]
        merged[-1] = (t + pending, st)

    # 2) 每个 token 包 span；token 内的 \n 变 <br>
    parts = []
    for text, st in merged:
        color = st.get("color") or "0f172a"
        attrs = ["color:#" + color]
        if st.get("bold"):
            attrs.append("font-weight:bold")
        for idx, line in enumerate(escape(text).split("\n")):
            if idx > 0:
                parts.append("<br>")
            if line:
                parts.append('<span style="%s">%s</span>' % (";".join(attrs), line))
    return "".join(parts)
```

插入方式：对每个 `pre` 选中其 `code` 内容 → 聚焦正文 → `execCommand('insertHTML', false, html)`。
**pre 内 insertHTML 保留 span style，p 内会被剥。**

## 10. 结构修复要走 state 层

症状：文章最外层大框连续套了 3 层（误操作产生），视觉上一个框包全文。

**错误做法**：直接 DOM `appendChild` 移动 + dispatch input → ProseMirror 直接回滚。

**正确做法**：通过 EditorView 发正规 transaction。

```javascript
const view = window.__mpBodyChecktextView;
const doc  = view.state.doc;
const l0 = doc.child(0);           // 外层 para（多余的框）
const l2 = l0.child(0).child(0);   // 最内层（包着全部内容块）
// 位置：l0@0 → 中层@1 → l2@2 → l2 内容@3
const slice = doc.slice(3, 2 + l2.nodeSize - 1);
const tr = doc.tr.replace(1, l0.nodeSize - 1, slice);
view.dispatch(tr);
```

`slice.childCount` 等于被提升的内容块数，可用来校验。修复后确认直接子块数、视频 iframe、彩色 span 数不变。

## 11. 原地更新同一份草稿

编辑页 URL 带 `appmsgid=` 时，**全选替换粘贴 + 保存为草稿 = 更新同一份**，不会产生重复草稿。

改版重发的正确顺序：

```
关弹窗 → reload 恢复已存草稿 → 全选 → 粘贴 → 校验 imgs>0 → 保存
```

## 12. 保存确认

- 点「保存为草稿」（右下角绿色按钮）
- 新版编辑器保存**无 toast**，确认方式是看左侧「历史版本」列表是否出现新时间戳
- 出现「确定 / 继续保存 / 继续插入」等二次确认框时，点「确定」

## 13. 自查

- [ ] 只存草稿，没有点发表
- [ ] 图片全部变成平台域名（不是 `data:` 也不是 `127.0.0.1`）
- [ ] 正文没有渐变背景
- [ ] 保存前 `imgs > 0`
- [ ] 保存后左侧历史版本有新记录
