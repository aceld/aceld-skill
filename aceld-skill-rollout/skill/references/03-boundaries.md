# 03 · 边界：谁的文件能动、谁的一碰就废

> 铺能力这件事的风险不在技术，在**边界**。
> 改错一个文件，轻则下次更新被覆盖、重则丢掉本地 1600 行的最新版。

---

## 1. 三类目录，三种命运

| 位置 | 内容 | 能动吗 |
|---|---|---|
| `aceld-skill/<name>/skill/` | 仓库发布版 | ✅ 改，然后 commit |
| `~/.workbuddy-ai/skills/<name>/` | 本地已装副本 | ✅ 改自有；❌ 三方不碰 |
| `~/.workbuddy-ai/plugins/cache/...` | 插件市场缓存 | ❌ 绝对不碰，更新时整体重建 |

第三类是很多人会误伤的地方：市场装的技能会被复制到 `plugins/cache/`，
那里是**缓存**，改了不但会被覆盖，还可能让插件校验失败。

`audit.py` / `inject.py` 只扫前两类，第三类压根不进扫描范围——这是刻意的。

---

## 2. 自有的判定

```python
if item["name"] in repo_names:          # ① 仓库有同名目录
    return "自有(仓库)"
if item["name"].startswith("aceld-"):   # ② 命名空间
    return "自有(本地独有)"
```

①是硬证据：仓库里就是我的。
②是约定：`aceld-` 是我所有技能的命名空间前缀。

**②的意义**：允许「先在本地写、成熟了再回仓」。
`aceld-voice` 就是这样——本地有 315 行，仓库里还没有。它算自有，可以改。

---

## 3. 三方的判定与「白改」问题

```python
meta = os.path.join(dirname, "_meta.json")
if "ownerId" in open(meta).read():
    return "三方(市场)"
return "三方"
```

`_meta.json` 里有 `ownerId` = 这个技能有主人，不是你。市场更新时会：
1. 拉最新版
2. **整个目录替换**
3. 你加的块消失

所以「改了也是白改」不是道德问题，是**工程问题**：改动会被静默丢弃，
而你以为它生效了。这比没改更糟。

### 真的需要改怎么办

| 需求 | 做法 |
|---|---|
| 只想让它也遵守前置检查 | 别改它。`aceld-findskill` 的 `preflight.py` 已经覆盖「用什么技能」这一步 |
| 要改它的内容 | fork 到自己的命名空间（`aceld-<原名>`），登记到 `.findskill-sources.json` |
| 只是临时实验 | 改完别提交，用完 `sync.py --force` 恢复 |

---

## 4. 本地副本常常比仓库新（反直觉但真实）

`sync.py` 默认**只报告不覆盖**，原因写在文件头：

```
本地副本常常比仓库「更新」：
仓库是发布版，本地是工作版。比如 aceld-course 本地 1600+ 行、仓库 250 行。
```

实测数据：

| 技能 | 仓库 | 本地 | 差异原因 |
|---|---|---|---|
| `aceld-course` | 254 行 | 1634 行 | 本地是正在写的工作版 |
| `aceld-findskill` | 208 行 | 208 行 | 一致 |
| `aceld-voice` | — | 315 行 | 还没回仓 |

如果 `sync.py` 默认 `repo → local` 覆盖，`aceld-course` 那 1380 行当场蒸发。

所以三种模式：

```bash
python sync.py                                 # 只报告（默认，最安全）
python sync.py --apply                         # 只装「本地还没有」的
python sync.py --force aceld-diagram --apply   # 强制覆盖指定技能，自动备份
```

`--force` 的备份是 `shutil.move(dest, dest + ".bak.YYYYmmddHHMMSS")`——
**移动**不是复制，所以磁盘不翻倍，且原目录一定不残留。

**回滚**：把 `.bak.<时间戳>` 改回原名即可。

---

## 5. 备份文件会被扫描排除

`.bak` 目录里也有 `SKILL.md`，如果不排除，`audit.py` 会把它们当成
「一堆缺块的技能」报出来，噪音淹没真问题。

```python
def is_backup(name):
    return ".bak" in name or name.endswith(".zip")
```

`scan_repo` / `scan_local` 都先过这道。

---

## 6. 命名与许可

### 命名

| 规则 | 原因 |
|---|---|
| 目录名 = frontmatter 的 `name` | 加载器按目录找，不一致会找不到 |
| 小写 + 连字符 | 部分 Agent 不接受大写/下划线 |
| 自有技能加 `aceld-` 前缀 | `classify()` 靠它认领 |
| 一个技能只干一类事 | `aceld-course` 不塞 PDF 表单填充 |

### 许可

仓库根 `LICENSE` 是 MIT，所有自有技能 frontmatter 写 `license: MIT`。

三方技能的许可**不影响你要不要改它**——不管 MIT 还是 GPL，
改市场装的技能都会被覆盖。许可只在「fork 之后」才有意义：

| 原许可 | fork 后能不能闭源 |
|---|---|
| MIT / Apache-2.0 / BSD | ✅ 可以，保留原声明 |
| MPL-2.0 | ⚠️ 改了的那几个文件要同许可 |
| GPL / AGPL | ❌ 分发要同许可（AGPL 连 SaaS 也算） |

细节见 `aceld-findskill/references/04-security.md`。

---

## 7. 别碰的东西

| 别碰 | 为什么 |
|---|---|
| `plugins/cache/` | 插件市场缓存，会被重建 |
| `_meta.json` | 市场的元数据，改了校验失败 |
| `~/.workbuddy-ai/mcp.json` 之外的工具配置 | 与本技能无关，改坏了排查成本极高 |
| 别人的 `.findskill-sources.json` 条目 | 登记错来源会让 `preflight` 显示假「无更新」 |

最后一条踩过：`aceld-voice` 被误登记成 `aceld/aceld-skill` 的来源，
于是 `preflight` 每次都告诉它「上游有更新」——而实际上游根本没有这个技能。
修法是从 `.findskill-sources.json` 里 pop 掉那条。

---

## 8. 边界速查

```
要改的文件在 ~/.workbuddy-ai/skills/<name>/ ?
├─ 名字以 aceld- 开头 ──────────────→ ✅ 改
├─ 仓库里有同名目录 ────────────────→ ✅ 改，记得 commit 到仓库
├─ _meta.json 有 ownerId ──────────→ ❌ 跳过（市场装的）
└─ 其它 ──────────────────────────→ ⚠️ 先确认是不是手动 clone 的

要改的文件在 plugins/cache/ ? ───────→ ❌ 绝对不碰
```
