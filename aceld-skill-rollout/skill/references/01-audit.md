# 01 · 审计：先搞清「有没有」和「会不会生效」

> 铺能力之前必须先审计。不审计就注入，等于闭着眼改文件——
> 你会得到 7 个「有块」的技能，其中 2 个块在 140 行，1 个块在文档示例里。

---

## 1. 为什么审计是第一步

真实的第一次尝试是这样的：

1. 在 5 个 SKILL.md 末尾各加了一节「能力缺口处理」
2. `grep -l "能力缺口" */*.md` 全部命中，认为完成
3. 三个月后发现：**一次都没被执行过**

原因很简单——Agent 是从上往下读 SKILL.md 的。读到「## 1. 阶段一：知识点设计」
就已经开始干活了，永远翻不到最后那一节。

所以审计要回答的不是「有没有这段文字」，而是三个递进的问题：

| 问题 | 怎么答 | 答错的后果 |
|---|---|---|
| 有块吗？ | 找 marker / sentinel | 以为没写，重复写一遍 |
| 块在什么位置？ | 行号 vs 总行数 | 写了但永远读不到 |
| 这个技能该不该改？ | 自有 / 三方分类 | 改了下次更新被覆盖 |

---

## 2. 有效性判定：前 30 行

```python
TOP_LINES = 30
ok_pos = bool(has and line_no <= TOP_LINES)
```

**30 行**是个经验阈值，不是玄学：

- frontmatter 占 8–10 行（name / description / license / metadata）
- 一级标题 + 一句话定位占 3–6 行
- 再往下就该是第一节了

所以 30 行内插入，块就落在「第一屏」——读者打开文件、还没滚动就看见。

`audit.py` 输出的 `位置` 列就是 `块起始行/总行数`：

```
aceld-course [repo]   自有(仓库)   ✓   10/254    v1 ✓ 生效
aceld-findskill       自有(仓库)   ✓   140/208   v1 ✗ 太靠后
```

`140/208` 意味着：块在文件 67% 的位置。它在 `## 7. 维护` 底下，
是「查文档时才会看到」的位置，不是「开工时必然看到」的位置。

---

## 3. 三个真实的假阳性（都出在文本解析上）

### 假阳性 1：frontmatter 的 description 里提到了 marker

`aceld-findskill` 的 description 写了「含开工前置检查」，于是
`grep -n "开工前置检查"` 第 3 行就命中 → 判成「第 3 行有块 → 生效」。

实际真块在 140 行。

**修法**：`code_mask()` 把 frontmatter 整段标记为「不算正文」。

```python
if lines and lines[0].strip() == "---":
    for j in range(1, len(lines)):
        if lines[j].strip() == "---":
            for k in range(0, j + 1):
                mask[k] = True
            i = j + 1
            break
```

### 假阳性 2：文档里演示了哨兵语法

`aceld-skill-rollout` 自己的 SKILL.md 在「## 3. 哨兵块」一节里，
用 ```markdown 代码块演示了 `<!-- aceld-rollout:begin ... -->` 长什么样。

结果这行示例被当成真哨兵 → 判成「101 行有块」。而真块在 13 行。

**修法**：同一个 `code_mask()`，围栏代码块内的行一律不算正文。

### 假阳性 3：围栏里套围栏，mask 提前闭合

`code_mask` 第一版用的是 `fence = not fence`（见到 ``` 就翻转）。
但文档里常出现 ```markdown 里嵌 ```bash：

````markdown
```markdown
<!-- aceld-rollout:begin 示例 v1 -->   ← 这一行在 ```bash 之后
```bash
python x.py
```
```
````

`fence = not fence` 会在内层 ```bash 处就认为「代码块结束了」，
于是示例文字被当成正文，假阳性 2 又回来了。

**修法**：只有**不带信息的裸围栏**才算闭合。

```python
s = lines[j].lstrip()
bare = s.rstrip() in ("```", "~~~")     # ```bash 不算闭合
```

---

## 4. 归属分类：自有 vs 三方

```python
def classify(item, repo_names):
    if item["name"] in repo_names:          # 仓库里有同名目录
        return "自有(仓库)"
    if item["name"].startswith("aceld-"):   # 命名空间约定
        return "自有(本地独有)"
    if "_meta.json" 里含 "ownerId":         # 市场装的
        return "三方(市场)"
    return "三方"
```

判定顺序不能反：**先看仓库，再看命名，最后才看 `_meta.json`**。
反过来的话，自己在本地手写但还没进仓库的技能会被误判成三方。

四类在审计表里长这样：

| 归属 | 含义 | 处理 |
|---|---|---|
| 自有(仓库) | 仓库有 + 本地也装了 | 改，然后 commit |
| 自有(本地独有) | 只在本地（如 `aceld-voice`） | 改，考虑回仓 |
| 三方(市场) | `_meta.json` 有 `ownerId` | **跳过** |
| 三方 | 其它（如手动 clone 的） | 跳过，除非确认要 fork |

---

## 5. 怎么读这张矩阵表

```
技能                                 归属             有块     位置           版本/生效
----------------------------------------------------------------------------------------
aceld-course [repo]                自有(仓库)         ✓      10/254       v1 ✓ 生效
aceld-diagram [repo]               自有(仓库)         ✓      10/121       v1 ✓ 生效
aceld-findskill [repo]             自有(仓库)         ✓      18/208       v1 ✓ 生效
aceld-skill-rollout [repo]         自有(仓库)         ✓      13/158       v1 ✓ 生效
aceld-course                       自有(仓库)         ✓      11/1634      v1 ✓ 生效
aceld-findskill                    自有(仓库)         ✓      18/208       v1 ✓ 生效
aceld-voice                        自有(本地独有)       ✓      8/315        v1 ✓ 生效
architecture-diagram               三方             ✗      -            跳过(三方)
feishu-voice                       三方(市场)         ✗      -            跳过(三方)

自有技能 7 个（仓库 4 + 本地 8），生效 7 个
三方技能 5 个已跳过（改了会被市场更新覆盖）
```

逐列读：

| 列 | 该看什么 |
|---|---|
| 技能 | `[repo]` 后缀 = 仓库里那一份，不带 = 本地已装副本。**同名两行是正常的** |
| 有块 | `✓` 找到了（哨兵或裸标题）；`✗` 没找到 |
| 位置 | `起始行/总行数`。分母大而分子小 = 靠前，好 |
| 版本/生效 | `v1 ✓ 生效` / `v1 ✗ 太靠后` / `无哨兵`（手写老块） |

**`无哨兵` 要当问题处理**：手写的老块没有 sentinel，
`inject.py` 再跑一次会在锚点**另插一份**，得到两个块。

---

## 6. `--verify` 多查了什么

普通模式只看「有块 + 位置」。`--verify` 额外三条：

1. **哨兵存在**：`无哨兵` 记问题（否则以后没法幂等改）
2. **块内引用的脚本真的存在**：正则抽 `.../scripts/*.py`，逐个 `resolve_script()`
3. **仓库与本地一致**：同名技能两边 `has` 不同 → 报「仓库与本地不一致」

第 2 条踩过一个坑，值得单说：

块里写的是 `python ~/.workbuddy-ai/skills/aceld-findskill/scripts/preflight.py`。
抽取正则若不含 `~`（`[\w./\\-]*scripts/...`），会截成 `/.workbuddy-ai/...`；
而 Windows 上 `os.path.isabs("/foo")` **返回 True**（只要以分隔符开头就算绝对），
于是被当成真绝对路径去 `isfile()`，当然不存在 → 7 条假错。

修法两条一起：

```python
# 1. 正则加 ~
re.findall(r"([\w~./\\-]*scripts/[\w.-]+\.py)", block_text)

# 2. 绝对路径只认盘符（或 POSIX 的 /）
if ref.startswith("~"):
    cands.append(os.path.expanduser(ref))
elif _WIN_ABS.match(ref) or (os.name != "nt" and ref.startswith("/")):
    cands.append(ref)
```

---

## 7. 拿不到仓库时怎么办

`find_repo()` 的顺序：

```
--repo 参数  →  $ACELD_SKILL_REPO  →  从 cwd 向上找 aceld-course/skill/SKILL.md
```

都失败时只审计本地，并在第一行打印「（未找到，只审计本地）」。
这时所有 `aceld-` 开头的技能都会被判成「自有(本地独有)」，审计仍然可用，
但「仓库/本地一致性」这条检查会失效——所以铺能力时最好先 `cd` 到仓库根。

---

## 8. 什么时候该重跑审计

| 时机 | 为什么 |
|---|---|
| 注入之后 | 确认位置真的 ≤30 行，别信「我插在开头了」 |
| 同步之后 | 确认本地副本也拿到了块 |
| 装/删了技能之后 | 三方名单会变 |
| 发布之前 | 就是 `--verify`，全绿才 commit |
| 每月一次 | 市场更新可能把三方技能版本换掉，顺手确认没被误改 |
