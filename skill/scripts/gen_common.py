# -*- coding: utf-8 -*-
"""幻灯片设计系统：CSS + 动效 JS 库 + 页眉页脚生成

所有配色集中在 CSS 变量里，改主题只改这一处。
署名与系列名从 course.yaml 读取（见 config.py）。
"""
from config import cfg

CSS = r"""
<style>
:root{
  --bg0:#070b16; --bg1:#0d1428; --bg2:#141d38;
  --ink:#e8eeff; --dim:#93a4c9; --faint:#5f7093;
  --cyan:#22d3ee; --violet:#a78bfa; --gold:#fbbf24;
  --red:#fb7185; --green:#34d399; --blue:#60a5fa; --pink:#f472b6;
  --line:rgba(140,170,255,.17); --card:rgba(140,175,255,.055);
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1920px;height:1080px;overflow:hidden;
  font-family:"Microsoft YaHei","PingFang SC",sans-serif;
  background:var(--bg0);color:var(--ink);-webkit-font-smoothing:antialiased}
.slide{position:absolute;inset:0;display:none}
.slide.on{display:block}
.bg{position:absolute;inset:0;z-index:0;
  background:
    radial-gradient(1250px 720px at 76% 10%,rgba(34,211,238,.11),transparent 62%),
    radial-gradient(1050px 720px at 10% 90%,rgba(167,139,250,.11),transparent 62%),
    linear-gradient(158deg,var(--bg0) 0%,var(--bg1) 46%,var(--bg2) 100%)}
.grid{position:absolute;inset:0;z-index:1;opacity:.4;
  background-image:linear-gradient(rgba(140,170,255,.055) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(140,170,255,.055) 1px,transparent 1px);
  background-size:80px 80px}
.inner{position:absolute;inset:0;z-index:2;padding:104px 92px 140px 92px}
.crumb{position:absolute;left:92px;top:38px;font-size:20px;color:var(--faint);letter-spacing:.4px;z-index:3}
.crumb b{color:#8ea3cc;font-weight:600}
.sign{position:absolute;right:150px;top:36px;font-size:21px;z-index:3;letter-spacing:1px;
  color:rgba(190,210,255,.62)}
.sign b{color:rgba(255,255,255,.8);font-weight:700}
.pageno{position:absolute;right:96px;top:38px;font-size:20px;color:var(--faint);z-index:3}
/* 斜向水印（可选，不需要就把 .wm 去掉） */
.wm{position:absolute;left:50%;top:50%;z-index:4;pointer-events:none;
  transform:translate(-50%,-50%) rotate(-22deg);
  font-size:132px;font-weight:900;letter-spacing:14px;white-space:nowrap;
  color:rgba(160,190,255,.055);text-shadow:0 0 40px rgba(120,160,255,.03)}
h1{font-size:62px;font-weight:800;line-height:1.2;letter-spacing:.5px;
  background:linear-gradient(96deg,#ffffff 6%,#bfe6ff 48%,#c9b8ff 94%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent}
.sub{margin-top:14px;font-size:28px;color:var(--dim);letter-spacing:.5px}
.rule{margin-top:20px;width:110px;height:6px;border-radius:6px;
  background:linear-gradient(90deg,var(--cyan),var(--violet))}
.card{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:26px 30px}
.mono{font-family:Consolas,"Courier New",monospace}
.c-cyan{color:var(--cyan)}.c-violet{color:var(--violet)}.c-gold{color:var(--gold)}
.c-red{color:var(--red)}.c-green{color:var(--green)}.c-blue{color:var(--blue)}
.c-pink{color:var(--pink)}.c-dim{color:var(--dim)}.c-ink{color:var(--ink)}
.k{color:var(--gold);font-weight:700}
.tag{display:inline-block;padding:7px 18px;border-radius:999px;font-size:20px;
  border:1px solid var(--line);color:var(--dim);background:rgba(140,175,255,.06)}
.center{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%}
</style>
"""

JS = r"""
<script>
const EASE={out:p=>1-Math.pow(1-p,3),inOut:p=>p<.5?4*p*p*p:1-Math.pow(-2*p+2,3)/2,
  back:p=>1+2.4*Math.pow(p-1,3)+1.4*Math.pow(p-1,2),lin:p=>p};
const FX={
 fadeUp:(el,p)=>{const e=EASE.out(p);el.style.opacity=e;el.style.transform=`translateY(${(1-e)*46}px)`},
 fadeIn:(el,p)=>{el.style.opacity=EASE.out(p)},
 fadeLeft:(el,p)=>{const e=EASE.out(p);el.style.opacity=e;el.style.transform=`translateX(${(1-e)*64}px)`},
 fadeRight:(el,p)=>{const e=EASE.out(p);el.style.opacity=e;el.style.transform=`translateX(${-(1-e)*64}px)`},
 pop:(el,p)=>{const e=EASE.back(Math.min(1,p));el.style.opacity=Math.min(1,p*2.4);el.style.transformBox='fill-box';el.style.transformOrigin='center';el.style.transform=`scale(${.8+.2*e})`},
 growX:(el,p)=>{const e=EASE.out(p);el.style.opacity=1;el.style.transformBox='fill-box';el.style.transformOrigin='left center';el.style.transform=`scaleX(${e})`},
 growY:(el,p)=>{const e=EASE.out(p);el.style.opacity=1;el.style.transformBox='fill-box';el.style.transformOrigin='top center';el.style.transform=`scaleY(${e})`},
 growDown:(el,p)=>{const e=EASE.out(p);el.style.opacity=1;el.style.transformBox='fill-box';el.style.transformOrigin='top center';el.style.transform=`scaleY(${e})`},
 draw:(el,p)=>{el.style.opacity=1;const L=el.getTotalLength?el.getTotalLength():600;el.style.strokeDasharray=L;el.style.strokeDashoffset=L*(1-EASE.out(p))},
 count:(el,p)=>{const a=+el.dataset.from||0,b=+el.dataset.to||100,d=+el.dataset.dec||0;
   el.textContent=(a+(b-a)*EASE.out(p)).toFixed(d)},
 hl:(el,p)=>{const e=EASE.out(p);el.style.opacity=1;el.style.boxShadow=`0 0 0 ${2+4*e}px rgba(251,191,36,${.14+.5*e}),0 0 52px rgba(251,191,36,${.32*e})`;
   el.style.borderColor=`rgba(251,191,36,${.3+.55*e})`;el.style.transform=`scale(${1+.03*e})`},
 dim:(el,p)=>{const e=EASE.out(p);el.style.opacity=1-.6*e;el.style.filter=`grayscale(${.75*e})`},
 rise:(el,p)=>{const e=EASE.out(p);el.style.opacity=e;el.style.transform=`translateY(${(1-e)*90}px) scale(${.96+.04*e})`},
 pulse:(el,p)=>{const e=EASE.out(p);el.style.transform=`scale(${1+.1*Math.sin(p*Math.PI)})`},
 type:(el,p)=>{el.style.opacity=1;const full=el.dataset.text||'';const n=Math.round(full.length*EASE.out(p));el.textContent=full.slice(0,n)},
 show:(el,p)=>{el.style.opacity=p>.5?1:0}
};
let STEPS=[];
const NOHIDE=new Set(['hl','dim','count','pulse']);
function buildSteps(list){
  STEPS=list.map(s=>({t:s[0],sel:s[1],fx:s[2],dur:s[3]===undefined?0.6:s[3]}));
  STEPS.forEach(s=>document.querySelectorAll(s.sel).forEach(el=>{
    if(!el.dataset.fxInit){ if(!NOHIDE.has(s.fx)) el.style.opacity=0; el.dataset.fxInit=1 }}));
}
function seek(t){
  for(const s of STEPS){
    if(t<s.t) continue;
    const p=Math.min(1,(t-s.t)/s.dur);
    document.querySelectorAll(s.sel).forEach(el=>{try{FX[s.fx](el,p)}catch(e){}});
  }
  // 循环动画：元素沿路径往返（与时间轴同步，逐帧可精确复现）
  document.querySelectorAll('[data-walk]').forEach(el=>{
    const a=el.dataset.walk.split(',').map(Number);
    const x0=a[0],y0=a[1],x1=a[2],y1=a[3],per=a[4]||9;
    const cyc=t/per, ph=cyc-Math.floor(cyc);
    const e=ph<.5?2*ph*ph:1-Math.pow(-2*ph+2,2)/2;
    const q=(Math.floor(cyc)%2===0)?e:1-e;
    const bob=Math.sin(t*6.5)*5;
    el.setAttribute('transform',`translate(${x0+(x1-x0)*q},${y0+(y1-y0)*q+bob})`);
  });
}
function resetAll(){
  document.querySelectorAll('[data-fx-init]').forEach(el=>{
    el.style.opacity=0;el.style.transform='none';el.style.boxShadow='';el.style.filter=''});
  document.querySelectorAll('.static').forEach(el=>{el.style.opacity=1;el.style.transform='none'});
}
function showSlide(i){
  document.querySelectorAll('.slide').forEach((s,k)=>s.classList.toggle('on',k===i));
  resetAll(); window.__slide=i;
}
window.seek=seek;window.buildSteps=buildSteps;window.resetAll=resetAll;window.showSlide=showSlide;
</script>
"""


def crumb(txt, page, chapter_tag="", watermark=True):
    """页眉页脚：左上面包屑 + 右上署名 + 页码（+ 可选斜向水印）"""
    c = cfg()
    series = c.text("course_title", "My Course")
    author = c.text("author", "Your Name")
    tag = chapter_tag or ""
    wm = '<div class="wm">%s</div>' % author if watermark else ""
    return (
        wm
        + '<div class="crumb">%s<b>&lt;%s&gt;</b> / %s</div>'
        % (series, tag, txt)
        + '<div class="sign">%s</div>' % author
        + '<div class="pageno">%02d</div>' % page
    )


def head(title, sub="", alias=None):
    """页面主标题 + 副标题 + 装饰线；alias 是耳熟能详的简称（只上画面，不进语音）"""
    h = '<h1 id="t0">%s' % title
    if alias:
        name, color = alias
        h += ' <span style="font-size:.52em;color:%s;letter-spacing:0">%s</span>' % (color, name)
    h += "</h1>"
    if sub:
        h += '<div class="sub">%s</div>' % sub
    return h + '<div class="rule"></div>'
