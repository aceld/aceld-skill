# 微信编辑器硬约束清单

这份清单全部来自实际踩坑。微信后台会改版，遇到对不上的地方先跑 `scripts/doctor.py`。

---

## 一、样式：只认元素上的内联 style

粘贴进编辑器时，微信会把内容「洗」一遍：

| 你写的 | 结果 |
|---|---|
| `<style>` 标签 | **整段丢弃** |
| `class="xxx"` | **属性丢弃**，样式全失效 |
| `<div>` 布局 | 常被改写，尽量用 `<section>` / `<p>` |
| 元素上的 `style="..."` | **保留** ✅ |

所以排版脚本必须把每个元素的样式写死在 `style` 属性里。
`scripts/md2wechat.py` 就是这么干的，它不产出任何 `<style>`。

---

## 二、绝对禁止渐变

微信 darkmode 规范里有一条 `darkmode-no-gradient`：**文字/背景不许用 `linear-gradient`**。

踩坑现场：用渐变做标题底，粘贴时弹出「内容结构检测」模态框 → 模态框遮住编辑器 →
粘贴**静默失败**，正文变成空的，而且没有任何报错。

- 一律用**纯色** `background:#edf4fa`
- `md2wechat.py` 结束时会打印 `GRADIENT: 0`，不为 0 就改掉再继续
- `doctor.py` 也会顺手扫一遍页面里有没有残留渐变

---

## 三、图片：必须内联 base64 粘贴

编辑器页面是 HTTPS，`http://127.0.0.1` 的图片会被**混合内容**策略拦掉。
（`--allow-running-insecure-content` 在新版 Chrome 已失效，别再试本地图片服务器。）

正确姿势：

1. 排版阶段图片先写成占位 URL：`src="http://127.0.0.1:8792/v2/fig01.png"`
2. 发布阶段读本地文件 → PIL 缩到最大宽 **1400px** → 转 base64 data URI
3. 写进剪贴板 `text/html`，粘进编辑器
4. 微信**自动**上传成 `mmbiz.qpic.cn`，并把 `src` 改掉

实测容量：24 张图 ≈ 1.7MB base64，2MB HTML，剪贴板无压力。
超过 ~5MB 建议分两批贴，或者先把图压到 1200px。

**必须轮询确认**：粘贴后 `img[src^="data:"]` 要变成 0、`img[src*="mmbiz"]` 要等于预期张数，
否则图还是本地的，存草稿后打开就是裂图。

---

## 四、登录：token 会轮换，别写死

- 登录态就是浏览器里的 cookie，**脚本不需要也不应该保存任何凭据**
- token 从地址栏现抓：`re.search(r"token=(\d+)", page.url)`
- 这个值**每次登录都会变**，写死在配置里迟早报「请重新登录」
- 判断是否登录：**看重定向后的 URL 有没有 token**
  直接打开 `https://mp.weixin.qq.com/` 会先渲染登录二维码，几秒后才 JS 跳到
  `/cgi-bin/home?...&token=xxx`。别被首屏二维码骗去让用户重扫。

---

## 五、编辑器 DOM（2026-11 实测）

```
正文  #ueditor_0 .ProseMirror          ← 在 .mock-iframe 里，唯一命中
标题  #js_title_main .ProseMirror      ← 标题也是 ProseMirror
      textarea#title                   ← 隐藏数据载体，getBoundingClientRect().height = 0
按钮  button/span 文本 == "保存为草稿" / "预览" / "发表"
```

几个坑：

1. **`textarea#title` 直接赋 value 不生效**（它是隐藏域，微信只从 ProseMirror 同步）。
   必须先往 ProseMirror 里真实输入，再校验 `#title.value`。
2. **点标题要点靠左**。标题外面套了一层 `.title-editor-overlay`，点元素正中心
   会被 overlay 吃掉焦点，输入进不去。用 `x = rect.x + 30`。
3. **保存按钮要点 `span`**（`.btn.btn_input.btn_primary`），不是 `button`，
   按中心坐标 `mouse.click` 最稳。

---

## 六、粘贴前后的保护动作

```text
1. close_dialogs()        # 关掉残留模态框，否则会挡住编辑器
2. reload()（仅老草稿）    # 恢复到干净状态
3. 全选 Control+A
4. 写剪贴板 ClipboardItem({text/html, text/plain})
5. Control+V
6. 校验 imgs > 0          # ★ 关键闸门
7. 填标题
8. 轮询 mmbiz
9. 点「保存为草稿」
```

**第 6 步是安全闸门**：`imgs == 0` 说明粘贴失败。这时如果继续保存，
就会用空文**覆盖掉已有草稿**。脚本必须直接 `return`，宁可这次白跑。

另外，残留的「内容结构检测」模态框会**毒害下一次粘贴**：
保存完如果留着框，下次粘贴必失败。重发前先 `close_dialogs()` + `page.reload()`。

---

## 七、原地更新草稿

编辑页 URL 带 `appmsgid=` 时，**全选替换 + 保存为草稿 = 更新同一份**，不会产生重复草稿。

所以改文章的正确流程是：
打开原来那篇草稿 → 跑 `publish.py`（它会自动 reload 并全选替换）→ 存草稿。
不要每次都开新建页，否则草稿箱会堆一堆。

---

## 八、其它

- 代码高亮：pygments 的 token 要转成 `<span style="color:#xxx">` 内联，class 会被剥
- 表格：微信会自适应宽度，`width:100%` + `border-collapse:collapse` 够用
- `<script>` / `<iframe>` / 外链 CSS：一律剥掉，不要写
- 字号：正文 16px、行高 1.9，手机上看最舒服；小于 14px 在微信里偏小
- 段落：`text-align:justify` + `letter-spacing:0.3px`，中文两端对齐更整齐
