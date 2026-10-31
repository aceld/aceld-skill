# 02 · 注入：哨兵、锚点、版本号

> 注入要解决的不是「写进去」，而是「**能安全地再写一遍**」。
> 没有幂等，第二次注入就变成「同一个能力出现两遍」，第三次就没人敢碰了。

---

## 1. 哨兵长什么样

```markdown
<!-- aceld-rollout:begin 开工前置检查 v1 -->
> ### ⚑ 开工前置检查（每次先跑，30 秒）
>
> ```bash
> python ~/.workbuddy-ai/skills/aceld-findskill/scripts/preflight.py "本次任务关键词"
> ```
> ...
<!-- aceld-rollout:end -->
```

- `begin` 行带两个参数：**marker**（能力名）和 **版本号**
- `end` 行是固定字符串，没有参数
- 用 HTML 注释而不是可见标题：不占版面、不影响渲染、`grep` 定位精确

为什么不用中文标题当锚？因为标题会被人改。今天叫「开工前置检查」，
明天有人改成「⚑ 开工前必跑」，所有靠标题定位的工具全部失效。
注释没人会去动它。

---

## 2. 幂等的实现

`inject.py` 对每个技能做四步：

```
1. 找 sentinel_region(lines, marker)   → 有：拿到 [start, end) 待替换
2. 没有则找 legacy_region(lines, marker) → 手写老块（裸标题）
3. 都没有 → anchor_index() 算插入点，标记为 insert
4. 有 → 替换区间，标记为 replace
```

统计输出区分了这几种：

| 计数 | 含义 |
|---|---|
| `insert` | 原来没有，新插入 |
| `replace` | 有哨兵块，替换内容 |
| `legacy` | 有手写老块，转成哨兵块 |
| `same` | 内容一模一样，跳过（真正的幂等证明） |
| `remove` | `--remove` 摘掉 |
| `skip3` | 三方技能，跳过 |
| `fail` | 出错（锚点找不到等） |

判断「内容一样」不看整块字符串，而是比对**块体**（去掉哨兵行的部分）：

```python
if old_body.strip() == new_body.strip():
    return "same"
```

这样即使版本号从 v1 升到 v2、但正文没变，也不会白写一次盘。

---

## 3. 手写老块：`legacy` 与 40 行规则

`legacy_region()` 找的是「没有哨兵、但有同名标题」的段落。
`aceld-findskill` 就有一个手写的「开工前置检查」标题。

但这里有个陷阱：**文档里会引用同名标题当示例**。
`aceld-findskill` 第 140 行的那个标题，其实是真块；而别的文件里
「## 3. 哨兵块」一节中出现的标题只是演示。

`inject.py` 的判定：

```python
if legacy and legacy[0] >= 40:
    print("  ! %-32s 第 %d 行的同名标题视为文档示例，不替换" % (name, legacy[0] + 1))
    legacy = None
```

40 行以外出现的同名标题，一律按「文档示例」处理，改走锚点插入。

**为什么是 40**：真块如果存在，一定在文件靠前位置（否则本来就该被移到前面）；
靠后的同名标题，几乎必然是「在讲这个能力」而不是「就是这个能力」。

---

## 4. 三个锚点

```bash
--anchor after-intro                    # 默认
--anchor after-heading --heading "## 0. 一分钟速览"
--anchor append
```

### `after-intro`（默认，推荐）

找一级标题后**第一个 `---` 分隔线**，插在它前面。

SKILL.md 的通用结构是：

```markdown
# 标题

一句话定位。

---

## 1. ...
```

插在 `---` 之前 → 落在一句话定位之后、第一节之前。第一屏可见，
而且不打乱原有的 `## 1. / ## 2.` 编号。

### `after-heading`

有固定骨架的技能，可以把块钉在某个具体标题**之前**。
适合「前面已经有一大段说明，after-intro 会插得太靠上」的情况。

### `append`（不推荐）

追加到末尾。`inject.py` 会打印警告：

```
! aceld-course  append 到末尾，此处大概率不会被读到
```

除非你**故意**要放在最后（例如附录型能力），否则别用。

---

## 5. 版本号：什么时候必须升

```bash
--version v1    # 默认
```

规则只有一条：**块体内容变了就升版本**。

| 改动 | 升版本？ | 原因 |
|---|---|---|
| 改了一个命令、加了一条注意事项 | ✅ 升 | `--verify` 靠版本区分「旧版还在」和「已是新版」 |
| 只调了缩进/空格 | ❌ 不升 | 正文语义没变 |
| 换整个能力 | ✅ 升，甚至换 marker | 是不同能力了 |
| 摘掉块（`--remove`） | — | 版本号随块一起消失 |

版本号写在哨兵行里，`audit.py` 直接读出来：

```python
ver = m.group(1).replace(marker, "").strip() or "v?"
```

所以 `<!-- aceld-rollout:begin 开工前置检查 v2 -->` 会显示成 `v2 ✓ 生效`。

**常见错误**：改了块内容但忘了升版本 → 审计表上还是 `v1 ✓ 生效`，
看起来一切正常，实际有一半技能是新版、一半是旧版，而工具分辨不出来。

---

## 6. 原子写：为什么必须 tmp + replace

这是本项目最严重的一次事故，必须写清楚。

临时脚本用 `COV.get(name)` 取某个技能的「覆盖声明」，
但 `aceld-voice` 在仓库里不存在 → 返回 `None` →
`"\n".join(out)` 里混进 `None` → 抛 `TypeError`。

而代码是这么写的：

```python
with open(path, "w") as f:      # ← 先截断
    f.write("\n".join(out))      # ← 再抛异常
```

**`open(path, "w")` 会立刻把文件清空**。异常发生在写之前，于是
`aceld-course/skill/SKILL.md`（251 行）变成 0 字节。

抢救靠 `git checkout --`，因为刚好还没提交。如果已提交就是丢一次工作。

所以 `inject.py` 一律这样写：

```python
if a.apply:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out).rstrip("\n") + "\n")
    os.replace(tmp, path)        # 同盘原子替换，要么全成功要么全不变
```

三个细节：

- `newline="\n"`：Windows 上别写出 CRLF，git diff 会变成整文件重写
- `rstrip("\n") + "\n"`：文件尾恰好一个换行
- `os.replace` 而不是 `os.rename`：Windows 上 `rename` 目标存在会失败

**推论**：任何「读 → 改 → 写回同一个文件」的脚本都必须原子写。
这条对 `sync.py` 里的备份逻辑同样适用。

---

## 7. 回滚

```bash
python inject.py --marker "开工前置检查" --remove            # dry-run
python inject.py --marker "开工前置检查" --remove --apply    # 真删
```

`--remove` 只删哨兵区间（含两行哨兵），块外的东西一律不动。
这就是「差异外置」的好处——每个技能特有的「覆盖声明」写在块外，
摘块的时候它自然保留。

手写老块（`无哨兵`）**不会**被 `--remove` 摘掉，因为分不清
「这个标题是块」还是「这个标题在讲块」。这种情况得手动删，
删完再 `audit.py --verify` 确认。

---

## 8. 完整的一次注入

```bash
cd aceld-skill/aceld-skill-rollout/skill

# 1. 先干跑，看清楚会动哪些文件
python scripts/inject.py --block assets/block-preflight.md --marker "开工前置检查"

# 2. 确认 insert/replace/skip3 的数字对得上
python scripts/inject.py --block assets/block-preflight.md --marker "开工前置检查" --apply

# 3. 立刻验证
python scripts/audit.py --verify

# 4. 同步到本地已装副本
python scripts/sync.py
python scripts/sync.py --apply

# 5. 再验证一次（本地那几行也要 ≤30 行）
python scripts/audit.py --verify
```

干跑输出长这样：

```
  + aceld-course [repo]                insert  @ 10/254
  ~ aceld-findskill [repo]             replace @ 18/208
  = aceld-skill-rollout [repo]         same
  - feishu-voice                        skip3（三方，会被市场更新覆盖）

insert 1 / replace 1 / same 1 / skip3 5 / fail 0
（dry-run，加 --apply 才写盘）
```

`fail 0` 是关键：任何一个 `fail` 都不要 `--apply`，先看是哪一步错了。
