# examples

| 目录 / 文件 | 是什么 |
|---|---|
| `demo-pack/` | 由 `assets/candidates.example.json` 跑出来的**格式演示**资料包（`pack.md` + `pack.json`）。链接与热度数字都是占位，**不要当真实资料引用**，只用来看输出长什么样 |
| `real-probe-2026-11-05.md` | 一次**真实检索 + 真实 WebFetch 核验**的留痕：演示「近半年」过滤怎么生效，以及为什么两条看起来不错的文章最终都被淘汰 |

复现演示包：

```bash
S=~/.workbuddy-ai/skills/aceld-websearch
python $S/scripts/rank.py -i $S/assets/candidates.example.json -o ./demo-pack
python $S/scripts/verify.py ./demo-pack/pack.json
```

预期：候选 7 → 入选 2 / 淘汰 5，校验 `PASS`。
五条淘汰各自演示了一条硬门槛：超窗、热度不足、付费墙+指标未核验、T3 聚合、无公开热度。
