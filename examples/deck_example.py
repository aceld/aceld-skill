# -*- coding: utf-8 -*-
"""页面定义示例：四种典型版式 + 触发词写法

把本文件复制到课程工程的 slides/ 目录，改名为 deck_a.py，然后：
    python scripts/build_deck.py --modules deck_a

★ 三条铁律：
  1. 一块内容 = 一个 id = 一个触发词
  2. 讲稿里说「第一/第二」的页面，内容块 id 从 1 开始，标题占 0 号
  3. 触发词必须是该段正文的原样子串，且位置严格递增
"""
import os
import sys

# 让 gen_common 能被导入（正常使用时由 build_deck.py 注入路径）
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "skill", "scripts"))

from gen_common import head  # noqa: E402

S = []
TOTAL = 4          # 总页数，用于页眉页码


# ---------------- P0：三张卡片（最常见的一种）----------------
S.append((0, "开场", TOTAL, r"""
<div class="inner" style="display:flex;flex-direction:column;justify-content:center">
  %s
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:26px;margin-top:56px">
    <div class="card" id="c1">
      <div class="c-cyan" style="font-size:22px;letter-spacing:2px">现象 一</div>
      <div style="margin-top:14px;font-size:30px;font-weight:700">查好了航班<br/>但订不了</div>
      <div class="c-dim" style="margin-top:14px;font-size:22px">得你自己点</div>
    </div>
    <div class="card" id="c2">
      <div class="c-violet" style="font-size:22px;letter-spacing:2px">现象 二</div>
      <div style="margin-top:14px;font-size:30px;font-weight:700">写好了脚本<br/>但跑不了</div>
      <div class="c-dim" style="margin-top:14px;font-size:22px">得你自己开终端</div>
    </div>
    <div class="card" id="c3">
      <div class="c-gold" style="font-size:22px;letter-spacing:2px">现象 三</div>
      <div style="margin-top:14px;font-size:30px;font-weight:700">改好了代码<br/>但测不了</div>
      <div class="c-dim" style="margin-top:14px;font-size:22px">得你自己跑一遍</div>
    </div>
  </div>
  <div id="sum" style="margin-top:48px;font-size:34px;font-weight:700;color:var(--ink)">
    它不是不聪明，是只能停在<span class="k">「说」</span>这一步
  </div>
</div>""" % head("三个让你心里咯噔一下的现象", "你有没有遇到过"), [
    # [触发词, 选择器, 动效, 持续秒]
    ("你有没有遇到过", "#t0", "fadeUp", 0.6),
    ("它帮你查好了航班", "#c1", "rise", 0.5),
    ("它帮你写好了脚本", "#c2", "rise", 0.5),
    ("它帮你改好了代码", "#c3", "rise", 0.5),
    ("只能停在说这一步", "#sum", "fadeUp", 0.6),
]))


# ---------------- P1：流程图 + 逐个揭示（注意 id 从 1 开始）----------------
S.append((1, "概念", TOTAL, r"""
<div class="inner" style="display:flex;flex-direction:column;justify-content:center">
  %s
  <h1 id="r0" style="margin-top:40px;font-size:52px">大模型是脑，Agent 是<span class="c-gold">脑加手脚</span></h1>
  <div style="display:flex;align-items:center;gap:18px;margin-top:52px">
    <div class="card" id="r1" style="flex:1;text-align:center">
      <div class="c-cyan" style="font-size:26px">脑</div>
      <div style="margin-top:10px;font-size:30px;font-weight:700">模型</div>
    </div>
    <div id="r2" style="font-size:40px;color:var(--gold)">＋</div>
    <div class="card" id="r3" style="flex:1;text-align:center">
      <div class="c-violet" style="font-size:26px">手脚</div>
      <div style="margin-top:10px;font-size:30px;font-weight:700">工具 · 执行环境</div>
    </div>
    <div id="r4" style="font-size:40px;color:var(--gold)">＝</div>
    <div class="card" id="r5" style="flex:1;text-align:center;border-color:rgba(251,191,36,.5)">
      <div class="c-gold" style="font-size:26px">Agent</div>
      <div style="margin-top:10px;font-size:30px;font-weight:700">能干活的东西</div>
    </div>
  </div>
  <div id="r6" class="tag" style="margin-top:44px;align-self:flex-start">
    感知 → 思考 → 行动 → 观察，这是一个环，不是一条线
  </div>
</div>""" % head("差的那一步，叫行动", "补的不是智力，是手脚"), [
    ("所以要补的其实不是智力", "#t0", "fadeUp", 0.6),
    ("大模型是脑，负责想", "#r0", "fadeUp", 0.5),
    ("负责想", "#r1", "rise", 0.5),
    ("Agent 是脑加手脚", "#r2", "pop", 0.4),
    ("负责想完之后还能动", "#r3", "rise", 0.5),
    ("还能动", "#r4", "pop", 0.4),
    ("它就多了一个闭环", "#r5", "rise", 0.5),
    ("注意，这是一个环", "#r6", "fadeUp", 0.6),
]))


# ---------------- P2：代码页，逐行出现 ----------------
CODE = [
    ("think := 我需要什么信息", "codel1"),
    ("result := 调用工具(think)", "codel2"),
    ("observe := 读取结果(result)", "codel3"),
    ("if 还需要信息 { 回到第一步 }", "codel4"),
]
code_html = "\n".join(
    '<div class="mono" id="%s" style="font-size:30px;line-height:1.9;color:#c8d4ea">'
    '<span class="c-dim">%d</span>&nbsp;&nbsp;%s</div>' % (cid, k + 1, txt)
    for k, (txt, cid) in enumerate(CODE))

S.append((2, "四种模式", TOTAL, r"""
<div class="inner" style="display:flex;flex-direction:column;justify-content:center">
  %s
  <div class="card" style="margin-top:44px;padding:40px 48px">
    %s
  </div>
  <div id="note" class="tag" style="margin-top:40px;align-self:flex-start">
    三步循环起来，就是 ReAct
  </div>
</div>""" % (head("ReAct：边想边做", "走一步看一步"), code_html), [
    ("第一种模式叫 ReAct", "#t0", "fadeUp", 0.6),
    ("第一步，思考", "#codel1", "fadeUp", 0.5),
    ("第二步，行动", "#codel2", "fadeUp", 0.5),
    ("第三步，观察", "#codel3", "fadeUp", 0.5),
    ("然后回到第一步", "#codel4", "fadeUp", 0.5),
    ("这三步循环起来", "#note", "fadeUp", 0.6),
]))


# ---------------- P3：总结页（列表逐条出现）----------------
ITEMS = [
    ("大模型只会说，不会做", "s1"),
    ("Agent 补的是手脚", "s2"),
    ("闭环是 感知 · 思考 · 行动 · 观察", "s3"),
    ("四种模式底层都是 想 — 做 — 看", "s4"),
    ("模式会变，逻辑不变", "s5"),
]
items_html = "\n".join(
    '<div id="%s" style="display:flex;gap:22px;margin-top:26px">'
    '<div class="c-gold" style="font-size:28px;font-weight:800;min-width:56px">%02d</div>'
    '<div style="font-size:34px;font-weight:700">%s</div></div>' % (sid, k + 1, txt)
    for k, (txt, sid) in enumerate(ITEMS))

S.append((3, "收尾", TOTAL, r"""
<div class="inner" style="display:flex;flex-direction:column;justify-content:center">
  %s
  <div style="margin-top:40px">%s</div>
</div>""" % (head("五句话记住这一课", ""), items_html), [
    ("最后用五句话收一下", "#t0", "fadeUp", 0.6),
    ("第一，大模型只会说", "#s1", "fadeLeft", 0.45),
    ("第二，Agent 补的是手脚", "#s2", "fadeLeft", 0.45),
    ("第三，闭环是", "#s3", "fadeLeft", 0.45),
    ("第四，四种模式", "#s4", "fadeLeft", 0.45),
    ("第五，模式会变", "#s5", "fadeLeft", 0.45),
]))
