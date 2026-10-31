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

## 4. 仓库目录名 ≠ 技能名（最容易丢东西的一处）

`sync.py` 一开始是拿**仓库目录名**去比对本地目录的。于是它报：

```
~ aceld-course  不一致（仓库 25 / 本地 24 文件）→ 不动，需 --force aceld-course
```

看着像「版本不一致」，其实是**两个不同的技能**被放在一起比：

| | 仓库 `aceld-course/` | 本地 `aceld-course/` |
|---|---|---|
| 是什么 | 去个人化的**开源通用版** | 作者的**个人实战工作版** |
| SKILL.md | 254 行，7 章 + `references/01-10` 分章 | 1634 行，14 章，含三/四/五课复盘 |
| 脚本 | 12 个通用脚本 | `slides_a~d.py` 等本课专用 |
| 装出来叫 | **`course-studio`**（frontmatter 的 `name:`） | `aceld-course` |

仓库 `aceld-course/install.sh` 里写得很清楚：

```bash
NAME="course-studio"
```

也就是说：仓库目录名只是**归类用的文件夹**，真正的技能标识是 `skill/SKILL.md` 的 `name:`。
按目录名同步，等于拿 254 行的通用版去覆盖 1634 行的个人版 —— 1380 行当场蒸发。

### 修法：按 `name:` 决定本地目录名

```python
def read_skill_name(path):
    lines = read_lines(path)
    if not lines or lines[0].strip() != "---":
        return os.path.basename(os.path.dirname(os.path.dirname(path)))
    for ln in lines[1:40]:
        if ln.strip() == "---":
            break
        m = re.match(r"^name:\s*(.+?)\s*$", ln)
        if m:
            return m.group(1).strip().strip("\"'")
    return os.path.basename(os.path.dirname(os.path.dirname(path)))
```

改完的映射（实测）：

| 仓库目录 | 技能名（本地目录） |
|---|---|
| `aceld-course/` | `course-studio` |
| `aceld-diagram/` | `aceld-diagram` |
| `aceld-findskill/` | `aceld-findskill` |
| `aceld-skill-rollout/` | `aceld-skill-rollout` |

于是本地 `aceld-course`（个人版）**根本不在比对范围内**，怎么同步都不会被碰；
而仓库的通用版老老实实装成 `course-studio`，两者并存、互不干扰。

`audit.py` 的表格会把映射显式打出来：

```
aceld-course [repo]→course-studio  自有(仓库)   ✓   10/254   v1 ✓ 生效
aceld-course                       自有(本地独有) ✓   11/1634  v1 ✓ 生效
course-studio                      自有(仓库)   ✓   10/254   v1 ✓ 生效
```

### 三种同步模式

```bash
python sync.py                                 # 只报告（默认，最安全）
python sync.py --apply                         # 只装「本地还没有」的
python sync.py --force course-studio --apply   # 强制覆盖指定技能，自动备份
python sync.py --mirror --apply                # 以仓库为准，覆盖所有不一致的
```

`--mirror` 是 `publish.py` 用的模式：既然提交了，本地就该跟仓库一样。
备份是 `shutil.move(dest, <skills-backup>/<name>.bak.YYYYmmddHHMMSS)`——
**移动**不是复制，磁盘不翻倍，且原目录一定不残留。

**回滚**：把 `skills-backup/<name>.bak.<时间戳>` 移回 `skills/<name>` 即可。

---

## 5. 备份目录绝对不能放在 skills/ 里面（真实事故）

第一版 `sync.py` / `install.sh` 的备份是就地改名：

```python
bak = dest + ".bak." + time.strftime("%Y%m%d%H%M%S")   # ← 错
shutil.move(dest, bak)
```

看着很自然：原目录不见了、备份就在旁边、回滚方便。**但它会让技能消失。**

技能加载器扫描 `~/.workbuddy-ai/skills/` 时，是**按子目录**逐个加载的，
它不认识 `.bak.` 这个命名约定。于是每装一次就多一个「同名技能」：

| 技能 | 真目录 | `.bak` 目录 | 列表里出现 |
|---|---|---|---|
| `aceld-course` | 1 | 0 | 1 次 |
| `aceld-diagram` | 1 | 1 | **2 次** |
| `aceld-findskill` | 1 | 2 | **3 次** |
| `aceld-skill-rollout` | 1 | 3 | **4 次** |

用户的反馈是「**我怎么找不到 aceld-findskill 技能**」——
列表里同一个名字出现三遍、还都带着过期内容，根本分不清哪个是真的。

### 正确做法：备份放技能目录外面

```python
def backup_root(local):
    """与 skills/ 同级，例如 ~/.workbuddy-ai/skills-backup/"""
    return os.path.join(os.path.dirname(os.path.abspath(local)), "skills-backup")
```

`install.sh` / `install.ps1` 同理，`$BACKUP_ROOT="$(dirname "$(dirname "$DEST")")/skills-backup"`。

### `audit.py --verify` 会把残留报出来

```
✗ 备份目录留在技能目录里：aceld-findskill.bak.20261031121932
  （会被当成同名技能，列表出现重复；应移到 skills-backup/）
```

`is_backup()` 仍然保留，用于让 `audit.py` / `sync.py` **跳过**散落的备份：

```python
def is_backup(name):
    return ".bak" in name or name.endswith(".zip")
```

注意两者的区别：`is_backup` 只解决「我的扫描器别被自己骗」，
**解决不了「加载器被备份骗」**——那个只能靠把备份移出去。

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
