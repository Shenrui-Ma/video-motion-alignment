"""Build the editable branch timeline, local geometry previews, and portable HTML."""
from pathlib import Path
from html import escape, unescape
import json, re, math, shutil, subprocess, hashlib
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
VIZ=Path('/Users/researcher/.codex/visualizations/2026/10/07/01a11535-f9e3-7093-831f-b1a2e74d0fa0/h3-research-branches-detailed.html')
RENDER=Path('/Users/researcher/.codex/plugins/cache/openai-bundled/visualize/1.0.50/skills/visualize/scripts/render.py')
DATA=json.loads((ROOT/'timeline-detailed.json').read_text())
FONT='/System/Library/Fonts/Supplemental/Arial Unicode.ttf'
fonts={s:ImageFont.truetype(FONT,s) for s in (14,16)}
metric=ImageDraw.Draw(Image.new('RGB',(1,1)))
AUDIT=ROOT/'audit/detailed';AUDIT.mkdir(exist_ok=True)

def wrap(text,width,size=16):
    output=[]
    for paragraph in text.split('\n'):
        words=re.findall(r'[A-Za-z][A-Za-z0-9_′/.-]*|[0-9]+(?:\.[0-9]+)?|.',paragraph)
        line=''
        for word in words:
            candidate=line+word
            if line and metric.textlength(candidate,font=fonts[size])>width-6:
                output.append(line.rstrip());line=word.lstrip()
            else:line=candidate
        output.append(line.rstrip())
    return output

def measure(n):
    rows=[(20,n['date'],14,'muted'),(47,n['title'],16,'strong')]
    y=79
    for label,body in n.get('diagram_sections', n['sections']):
        rows.append((y,label,14,'muted'));y+=22
        for line in wrap(body,n['width']-36):rows.append((y,line,16,''));y+=23
        y+=13
    status=wrap(n['status'],n['width']-48,14)
    n.update(rows=rows,height=y+len(status)*20+25,status_lines=status,status_y=y+13)

nodes=DATA['main']+DATA['branches']
for n in nodes:measure(n)
index={n['id']:n for n in nodes}
x=40;gap=150
for n in DATA['main']:n['x']=x;x+=n['width']+gap
W=x-gap+40
upper=['early_latent','rgb','latent']
index['early_latent']['x']=1050
index['rgb']['x']=1470
index['latent']['x']=2030
for k in upper:index[k]['y']=18
top_bottom=max(index[k]['y']+index[k]['height'] for k in upper)
main_h=max(n['height'] for n in DATA['main'])
axis=top_bottom+82+main_h/2
for n in DATA['main']:n['y']=axis-n['height']/2
bottom_top=max(n['y']+n['height'] for n in DATA['main'])+86
for k,x in [('rope',1320),('spatial',1960),('reciprocal',2540)]:index[k].update(x=x,y=bottom_top)
H=max(n['y']+n['height'] for n in nodes)+22

svg=[f'<svg xmlns="http://www.w3.org/2000/svg" class="timeline" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="h3-detailed-title h3-detailed-desc">',
 '<title id="h3-detailed-title">H3 研究主线、方法与集中实验</title>',
 '<desc id="h3-detailed-desc">一条横向主线连接七个研究阶段。上方分出早期 latent 停止器、VAE 与姿态自动控制、低成本 latent 观察器；下方分出 RoPE、空间对应和双向 Attention。各框包含方法、实验结果和后续决定。</desc>']
image=Image.new('RGB',(int(W),math.ceil(H)),'#ffffff');draw=ImageDraw.Draw(image)
checks=[]

def line(points,main=False,arrow=True):
    cls='main-edge' if main else 'branch-edge';color='#497594' if main else '#84909c'
    d='M'+' L'.join(f'{a:.1f} {b:.1f}' for a,b in points)
    svg.append(f'<path d="{d}" class="{cls}"/>');draw.line(points,fill=color,width=2 if main else 1)
    if arrow:
        ex,ey=points[-1];px,py=points[-2];theta=math.atan2(ey-py,ex-px)
        verts=[(ex,ey),(ex-7*math.cos(theta)+3.5*math.sin(theta),ey-7*math.sin(theta)-3.5*math.cos(theta)),(ex-7*math.cos(theta)-3.5*math.sin(theta),ey-7*math.sin(theta)+3.5*math.cos(theta))]
        svg.append('<polygon points="'+' '.join(f'{a:.1f},{b:.1f}' for a,b in verts)+f'" class="{"main-dot" if main else "muted"}" style="fill:var(--{"viz-series-1" if main else "muted-foreground"})"/>')
        draw.polygon(verts,fill=color)

def text(x,y,label,size=16,kind='',center=False,limit=None):
    width=metric.textlength(label,font=fonts[size]);left=x-width/2 if center else x
    if limit is not None:assert width<=limit,(label,width,limit)
    assert left>=0 and left+width<=W,(label,left,width,W)
    cl=('text-small ' if size==14 else '')+kind
    svg.append(f'<text x="{x:.1f}" y="{y:.1f}" class="{cl}" dominant-baseline="middle" text-anchor="{"middle" if center else "start"}">{escape(label)}</text>')
    b=draw.textbbox((0,0),label,font=fonts[size]);draw.text((left,y-(b[3]-b[1])/2-b[1]),label,font=fonts[size],fill='#657482' if kind=='muted' else '#253743')
    checks.append({'text':label,'x':left,'y':y,'width':width,'max_width':limit})

def edge_label(cx,y,label,width=132):
    for i,part in enumerate(wrap(label,width,14)):text(cx,y+i*18,part,14,'muted',True)

edge_notes=['改用参考引导','真人延后更常见','约束参考时间对应','扩大任务覆盖','验收编辑，再筛时差','比较强度与覆盖']
for i,(a,b) in enumerate(zip(DATA['main'],DATA['main'][1:])):
    line([(a['x']+a['width'],axis),(b['x']-3,axis)],True)
    edge_label((a['x']+a['width']+b['x'])/2,axis-31,edge_notes[i])
line([(4,axis),(37,axis)],True);line([(W-40,axis),(W-5,axis)],True)
core=index['operator'];cx=core['x']+core['width']/2
early=index['early_latent'];ex=early['x']+early['width']/2
join_y=top_bottom+42
line([(cx,core['y']),(cx,join_y),(ex,join_y),(ex,early['y']+early['height']+3)])
edge_label((cx+ex)/2,join_y-21,'尝试自动决定引导区间',230)
for a_id,b_id,label in [('early_latent','rgb','改用姿态观测'),('rgb','latent','省去逐步解码')]:
    a,b=index[a_id],index[b_id];ey=min(a['y']+a['height']/2,b['y']+b['height']/2)
    line([(a['x']+a['width'],ey),(b['x']-3,ey)])
    edge_label((a['x']+a['width']+b['x'])/2,ey-38,label,b['x']-a['x']-a['width']-10)
for source,target,label in [('operator','rope','调整位置编码'),('public','spatial','尝试空间对应'),('schedules','reciprocal','约束反向信息传播')]:
    a,b=index[source],index[target];ax=a['x']+a['width']/2;bx=b['x']+b['width']/2
    mid=bottom_top-42
    line([(ax,a['y']+a['height']),(ax,mid),(bx,mid),(bx,b['y']-3)])
    edge_label((ax+bx)/2,mid-21,label,190)

for n in nodes:
    x,y,w,h=n['x'],n['y'],n['width'],n['height'];current=n['state']=='current'
    svg.append(f'<g id="{n["id"]}"><rect x="{x}" y="{y}" width="{w}" height="{h}" class="node{" current" if current else ""}"/>')
    draw.rounded_rectangle((x,y,x+w,y+h),radius=5,fill='#edf3f7' if current else '#ffffff',outline='#c9d3db')
    for dy,label,size,kind in n['rows']:text(x+18,y+dy,label,size,kind,limit=w-36)
    sy=y+n['status_y'];sep=sy-19
    svg.append(f'<path d="M{x+18} {sep} H{x+w-18}" class="divider"/>');draw.line((x+18,sep,x+w-18,sep),fill='#dce2e7')
    dot='candidate' if n['state']=='candidate' else 'stopped' if n['state']=='stopped' else 'main'
    svg.append(f'<circle cx="{x+21}" cy="{sy}" r="3" class="{dot}-dot"/>');draw.ellipse((x+18,sy-3,x+24,sy+3),fill={'main':'#497594','stopped':'#a36b51','candidate':'#8470a7'}[dot])
    for i,part in enumerate(n['status_lines']):text(x+33,sy+20*i,part,14,limit=w-48)
    svg.append('</g>')
svg.append('</svg>');svg_text='\n'.join(svg)
(ROOT/'timeline.svg').write_text(svg_text)
image.save(ROOT/'timeline-detailed-preview.png')
for name,left in [('start',0),('methods',1000),('results',W-1500)]:
    image.crop((left,0,min(left+1500,W),math.ceil(H))).save(AUDIT/f'preview-{name}.png')
image.resize((min(1700,int(W)),round(H*min(1700/W,1)))).save(AUDIT/'preview-overview.png')
template=(ROOT/'detailed_template.html').read_text()
assert template.count('__TIMELINE_SVG__')==template.count('__COLUMN_STARTS__')==template.count('__METHOD_DETAILS__')==1
details=[]
for n in nodes:
    body=''.join(f'<p><strong>{escape(label)}</strong>　{escape(content).replace(chr(10),"<br>")}</p>' for label,content in n['sections'])
    details.append(f'<details><summary class="cursor-interaction">{escape(n["date"])} · {escape(n["title"])}</summary>{body}</details>')
fragment=template.replace('__TIMELINE_SVG__',svg_text).replace('__COLUMN_STARTS__',json.dumps([max(0,n['x']-40) for n in DATA['main']])).replace('__METHOD_DETAILS__','\n'.join(details))
VIZ.write_text(fragment)
subprocess.run(['python3',str(RENDER),str(VIZ),str(ROOT/'index.html'),'--title',DATA['title'],'--force'],check=True)
# The diagram has no icons/tooltips; remove the wrapper's optional CDN helpers.
page=(ROOT/'index.html').read_text();match=re.search(r'data-srcdoc="([^"]*)"',page)
assert match
inner=unescape(match.group(1));inner=re.sub(r'<script\b[^>]*\bsrc="https://unpkg.com/[^>]*></script>','',inner)
page=page[:match.start(1)]+escape(inner,quote=True)+page[match.end(1):]
(ROOT/'index.html').write_text(page)
dest=Path('/Users/researcher/Downloads/H3_研究决策时间轴_20261021.html');shutil.copy2(ROOT/'index.html',dest)
assert hashlib.sha256(dest.read_bytes()).digest()==hashlib.sha256((ROOT/'index.html').read_bytes()).digest()
(AUDIT/'TEXT_BOUNDS.json').write_text(json.dumps({'passed':True,'labels':checks},ensure_ascii=False,indent=2))
(AUDIT/'LAYOUT.json').write_text(json.dumps({'width':W,'height':H,'axis':axis,'nodes':[{k:n[k] for k in ['id','x','y','width','height']} for n in nodes]},ensure_ascii=False,indent=2))
print(json.dumps({'html':str(dest),'fragment':str(VIZ),'nodes':len(nodes),'size':[W,H],'bytes':dest.stat().st_size},ensure_ascii=False))
