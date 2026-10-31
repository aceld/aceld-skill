---
name: aceld-diagram
description: 刘丹冰(Aceld) 风格的架构图绘制技能。沉淀其「工程架构师手绘风」——白底扁平、纵向分层、莫兰迪粉彩组件、虚线分组、序号标注、左侧鹰眼监控列、Redis虚线框/Mysql深蓝实底。当用户要画系统架构图、数据流/管道图、架构演进路线图，或要求「用 Aceld 的风格画图」「画一张扁平专业的架构图」时使用。既可调用 gen_diagram.py 自动生成 SVG，也可按 style-guide 手绘。
---

# Aceld 架构图绘制 · 工程架构师手绘风

把刘丹冰(Aceld) 多年沉淀的「架构图怎么画」变成可复用的技能。核心是**用最小可视化成本讲清系统怎么跑、数据怎么流、关键节点在哪**——不追求好看，追求一眼读懂。

---

## 0. 一句话定位

Aceld 的图是**扁平、克制、蓝图感**的：白底、无渐变无阴影、纵向分层、粉彩组件、虚线分组、序号钉关键节点。这是它和花哨架构图最本质的区别。

## 1. 核心风格清单（画之前先记住）

1. **白底 + 扁平 + 蓝图感**，零装饰（无渐变/阴影/3D）。
2. **强纵向分层（Tier）**：数据源层 → 采集层 → 消息队列层 → 消费层 → 拆分层 → 解析层 → 校验层 → 调度层 → 存储层 → DB层。每层大圆角框，右侧**青色**竖排中文标签点名。
3. **莫兰迪低饱和粉彩 + 细灰描边**，同一组件类型全图同色（详见 `references/style-guide.md` 配色 token）。
4. **组件 = 圆角矩形**，中文+英文混排、居中无衬线。
5. **虚线/点状浅灰框做分组**（Kafka Topic、消费组、层）。
6. **纵向「管道」**：同一链路用一列小圆点堆叠（Consumer→Splitter→Parser→Validator），细向下箭头连接，多列重复。
7. **序号标注**：实心圆+白字数字，**红/蓝两色区分语义**，钉在关键节点。
8. **左侧「鹰眼」监控列**：蓝色实心竖条，纵贯处理层。
9. **主层标签用青色**（Arris / Kafka / ArrisDao…）。
10. **连接线克制**：细灰/蓝线 + 小三角箭头，自上而下；ACK 等反馈用弯曲灰线带标签。
11. **队列 = 堆叠下箭头/文档**形状。
12. **存储层固定画法**：Redis 虚线白框；Mysql 深蓝灰实底白字宽框。

## 2. 两种用法

### 用法 A：自动生成（推荐，零坐标）

编辑一份声明式 spec（JSON 即可，YAML 需装 PyYAML），运行生成器产出 SVG/HTML：

```bash
python skill/scripts/gen_diagram.py examples/realtime_pipeline.json -o out.html
# 同时得到 out.html（可浏览器看）和 out.svg
```

spec 字段（见 `skill/assets/diagram.example.json`）：

| 字段 | 作用 |
|---|---|
| `meta.title/subtitle` | 标题 |
| `monitor` | 左侧鹰眼监控列 `{label,fill}`（可选） |
| `producer` | 接入层横排盒子，如 `["中台","ArrisProducer","Kafka"]` |
| `kafka_label` | 处理层右侧青色「Kafka」竖标（可选） |
| `groups[]` | 虚线分组：`title` + `pipelines[]`，每个 pipeline 是 `stages:[consumer,splitter,parser,validator]` |
| `storage[]` | 存储层 `{label, style:"dotted"\|"solid", fill?, text?}` |
| `callouts[]` | 序号标注 `{n, color:"red"\|"blue", group, pipe, stage, side, label}` |
| `tier_labels` | 右侧三层青色标签 `[接入层,处理层,存储层]` |
| `palette` | 覆盖默认配色 |

可用 stage 颜色键：`consumer/splitter/parser/validator/scheduler/worker/router/dao/kafka`。
改字段即可，**无需手写坐标**。

### 用法 B：按规范手绘 / 指导

当需要口述或手画时，照 `references/style-guide.md` 的清单与反模式执行：白底、分层、粉彩同色、虚线分组、序号钉关键点、鹰眼监控列、Redis虚线/Mysql深蓝。

## 3. 决策树

```
用户要画图？
├─ 能给出组件/分层清单 → 用法 A：写 JSON spec 跑生成器
├─ 只是想看「Aceld 风格长啥样」→ 直接打开 examples/realtime_pipeline.html
└─ 要手画 / 评审一张图 → 用法 B：按 style-guide 清单核对
```

## 4. 反模式（不要做）

❌ 渐变/阴影/3D ❌ 中文衬线字体 ❌ 同类组件不同色 ❌ 箭头乱飞无方向
❌ 不分层不分组 ❌ 一张图塞爆（宁可拆多张）❌ 关键节点不标序号

## 5. 参考

- `references/style-guide.md` —— 风格提炼 + 配色 token + 适用场景 + 反模式（**画前必读**）
- `skill/scripts/gen_diagram.py` —— 零依赖 SVG 生成器
- `skill/assets/diagram.example.json` —— spec 模板
- `examples/realtime_pipeline.json` + `.html` —— 生成效果示例
