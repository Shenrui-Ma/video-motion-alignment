"""Build a research timeline with independently expandable nodes."""
from pathlib import Path
from html import escape, unescape
import json, math, re, subprocess, shutil, hashlib
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
AUDIT=ROOT/'audit/disclosure';AUDIT.mkdir(exist_ok=True)
VIZ=Path('/Users/researcher/.codex/visualizations/2026/10/07/01a11535-f9e3-7093-831f-b1a2e74d0fa0/h3-research-branches-detailed.html')
RENDER=Path('/Users/researcher/.codex/plugins/cache/openai-bundled/visualize/1.0.50/skills/visualize/scripts/render.py')
DATA=json.loads((ROOT/'timeline-detailed.json').read_text())
nodes=DATA['main']+DATA['branches'];index={n['id']:n for n in nodes}
fonts={s:ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf',s) for s in (14,18)}
measure=ImageDraw.Draw(Image.new('RGB',(1,1)))

def wrap(value,width,size):
    rows=[];line=''
    for word in re.findall(r'[A-Za-z][A-Za-z0-9_′/.-]*|[0-9]+(?:\.[0-9]+)?|.',value):
        if line and measure.textlength(line+word,font=fonts[size])>width-6:rows.append(line.rstrip());line=word.lstrip()
        else:line+=word
    if line:rows.append(line)
    return rows

for n in nodes:
    n['title_rows']=wrap(n['node_title'],n['width']-43,18)
    n['conclusion_rows']=wrap(n['conclusion'],n['width']-34,14)
    n['height']=math.ceil(32+len(n['title_rows'])*25.2+10+len(n['conclusion_rows'])*21)
x=24
for n in DATA['main']:n['x']=x;x+=n['width']+100
width=x-100+24
upper=['early_latent','rgb','latent'];lower=['rope','spatial','reciprocal']
index['early_latent']['x']=index['operator']['x']-220
index['rgb']['x']=index['early_latent']['x']+index['early_latent']['width']+100
index['latent']['x']=index['rgb']['x']+index['rgb']['width']+100
top_bottom=max(index[k]['height']+12 for k in upper)
main_h=max(n['height'] for n in DATA['main']);axis=top_bottom+90+main_h/2
for k in upper:index[k]['y']=12
for n in DATA['main']:n['y']=axis-n['height']/2
index['rope']['x']=index['operator']['x']-100
index['spatial']['x']=index['rope']['x']+index['rope']['width']+85
index['reciprocal']['x']=index['spatial']['x']+index['spatial']['width']+85
for k in lower:index[k]['y']=axis+main_h/2+90
width=max(width,max(n['x']+n['width'] for n in nodes)+24)
height=math.ceil(max(n['y']+n['height'] for n in nodes)+18)
edges=[]
for a,b in zip(DATA['main'],DATA['main'][1:]):edges.append({'from':a['id'],'to':b['id'],'side':'horizontal','main':True,'label':'扩大测试' if a['id']=='operator' else ''})
edges.extend([
 {'from':'operator','to':'early_latent','side':'up','label':'尝试自动控制','offset':-68},
 {'from':'early_latent','to':'rgb','side':'horizontal','label':''},
 {'from':'rgb','to':'latent','side':'horizontal','label':''},
 {'from':'operator','to':'rope','side':'down','label':''},
 {'from':'public','to':'spatial','side':'down','label':''},
 {'from':'schedules','to':'reciprocal','side':'down','label':''},
])
config={'nodes':[{'id':n['id'],'x':n['x'],'width':n['width'],'title':n['node_title']} for n in nodes], 'main':[n['id'] for n in DATA['main']],'upper':upper,'lower':lower,'edges':edges}
image=Image.new('RGB',(width,height),'white');draw=ImageDraw.Draw(image);svg=[];geometry=[]
def label(x,y,text,size=14,center=False):
    w=measure.textlength(text,font=fonts[size]);box=draw.textbbox((0,0),text,font=fonts[size])
    draw.text((x-w/2 if center else x,y-(box[3]-box[1])/2-box[1]),text,font=fonts[size],fill='#253743')
for e in edges:
    a,b=index[e['from']],index[e['to']]
    if e['side']=='horizontal':p=(a['x']+a['width'],a['y']+a['height']/2);q=(b['x']-3,b['y']+b['height']/2)
    elif e['side']=='up':p=(a['x']+20,a['y']);q=(b['x']+b['width']/2,b['y']+b['height']+3)
    else:p=(a['x']+a['width']/2,a['y']+a['height']);q=(b['x']+b['width']/2,b['y']-3)
    x1,y1=p;x2,y2=q;theta=math.atan2(y2-y1,x2-x1)
    pts=[q,(x2-7*math.cos(theta)+3.5*math.sin(theta),y2-7*math.sin(theta)-3.5*math.cos(theta)),(x2-7*math.cos(theta)-3.5*math.sin(theta),y2-7*math.sin(theta)+3.5*math.cos(theta))]
    cls='main-edge' if e.get('main') else '';color='#497594' if e.get('main') else '#84909c'
    svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="{cls}"/><polygon points="'+ ' '.join(f'{x},{y}' for x,y in pts)+f'" class="{cls}"/>')
    draw.line([p,q],fill=color,width=2);draw.polygon(pts,fill=color)
    if e['label']:
        tx=(x1+x2)/2+e.get('offset',0);ty=(y1+y2)/2-12
        svg.append(f'<text x="{tx}" y="{ty}" text-anchor="middle">{escape(e["label"])}</text>');label(tx,ty,e['label'],14,True)
    geometry.append({'from':e['from'],'to':e['to'],'points':[p,q]})
cards=[]
for n in nodes:
    x,y,w,h=n['x'],n['y'],n['width'],n['height']
    fill={'main':'#dbe8f2','stopped':'#e5e9ee','candidate':'#e6dff2','current':'#cce5dc'}[n['state']]
    draw.rounded_rectangle((x,y,x+w,y+h),radius=5,fill=fill,outline='#94a4b3')
    yy=y+28
    for row in n['title_rows']:label(x+16,yy,row,18);yy+=25.2
    yy+=8
    for row in n['conclusion_rows']:label(x+16,yy,row,14);yy+=21
    label(x+w-16,y+25,'+',14)
    body=''.join(f'<p><strong>{escape(k)}</strong>{escape(v).replace(chr(10),"<br>")}</p>' for k,v in n['sections'])
    cards.append(f'<details class="timeline-node {n["state"]}" data-node="{n["id"]}" style="left:{x}px;top:{y}px;width:{w}px"><summary class="cursor-interaction"><span class="node-title">{escape(n["node_title"])}</span><span class="node-conclusion">{escape(n["conclusion"])}</span></summary><div class="node-content">{body}</div></details>')
template=(ROOT/'disclosure_template.html').read_text()
fragment=template.replace('__STAGE_WIDTH__',str(width)).replace('__STAGE_HEIGHT__',str(height)).replace('__INITIAL_EDGES__','\n'.join(svg)).replace('__NODES__','\n'.join(cards)).replace('__CONFIG__',json.dumps(config,ensure_ascii=False).replace('<','\\u003c'))
assert not re.search(r'__[A-Z_]+__',fragment)
VIZ.write_text(fragment)
subprocess.run(['python3',str(RENDER),str(VIZ),str(ROOT/'index.html'),'--title','H3 研究进展','--force'],check=True)
page=(ROOT/'index.html').read_text();m=re.search(r'data-srcdoc="([^"]*)"',page);inner=unescape(m.group(1))
inner=re.sub(r'<script\b[^>]*\bsrc="https://unpkg.com/[^>]*></script>','',inner)
page=page[:m.start(1)]+escape(inner,quote=True)+page[m.end(1):];(ROOT/'index.html').write_text(page)
destination=Path('/Users/researcher/Downloads/H3_研究决策时间轴_20261021.html');shutil.copy2(ROOT/'index.html',destination)
assert destination.read_bytes()==(ROOT/'index.html').read_bytes()
image.save(AUDIT/'preview-full.png');image.resize((min(1700,width),round(height*min(1700/width,1)))).save(AUDIT/'preview-overview.png')
image.crop((max(0,index['early_latent']['x']-30),0,min(width,index['early_latent']['x']+1430),height)).save(AUDIT/'preview-methods.png')
(AUDIT/'CONFIG.json').write_text(json.dumps(config,ensure_ascii=False,indent=2))
(AUDIT/'LAYOUT.json').write_text(json.dumps({'width':width,'height':height,'nodes':[{k:n[k] for k in ['id','x','y','width','height']} for n in nodes],'edges':geometry},ensure_ascii=False,indent=2))
print(json.dumps({'html':str(destination),'size':[width,height],'nodes':len(nodes),'all_collapsed':True,'bytes':destination.stat().st_size},ensure_ascii=False))
