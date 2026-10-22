from pathlib import Path
import html, math, json
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent
W,H,S = 1180,740,2
im = Image.new('RGB',(W*S,H*S),'white')
d = ImageDraw.Draw(im)
FONT='/System/Library/Fonts/Supplemental/Arial Unicode.ttf'
C={'ink':'#263540','muted':'#61717B','line':'#B9C6CD','border':'#D7E0E5','pale':'#F6F8FA','green':'#217C60','gp':'#EEF7F2','blue':'#2D6EAA','bp':'#EFF5FB','white':'#FFFFFF'}
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="740" viewBox="0 0 1180 740" role="img" aria-labelledby="fig-title fig-desc">',
'<title id="fig-title">H3 单流 DiT：双向时序 Attention 修正</title>',
'<desc id="fig-desc">一个 H3 DiT block 内，生成 T 和参考 R 各含三个时间 bin，每个 bin 含多个空间 token。两条分支基于同一组原 Q、K、V 并行计算。正向生成 query 读取同时间 bin 的参考 key 与 value，O_T prime 等于 O_T 加 alpha m_R 乘以 mu_R same 减 mu_R all。反向参考 query 读取同时间 bin 的生成 key 与 value，O_R prime 等于 O_R 加 beta m_T 乘以 mu_T same 减 mu_T all。修正加在各 head 原 Joint Attention 输出 O 上，再经 out_proj W_O、残差与 FFN 进入下个 block。更新的参考 hidden states 继续影响后续层生成。参考初始 latent 每个采样步重新提供，不回写参考文件。</desc>',
'<rect width="1180" height="740" fill="white"/>']

def rect(x,y,w,h,fill='white',stroke=None,r=0,sw=1):
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"'+(f' stroke="{stroke}" stroke-width="{sw}"' if stroke else '')+'/>')
    box=(x*S,y*S,(x+w)*S,(y+h)*S)
    d.rounded_rectangle(box,r*S,fill=fill,outline=stroke,width=round(sw*S)) if r else d.rectangle(box,fill=fill,outline=stroke,width=round(sw*S))

def text(x,y,t,size=18,fill=None,anchor='start',bold=False):
    fill=fill or C['ink']; f=ImageFont.truetype(FONT,size*S)
    svg.append(f'<text x="{x}" y="{y}" font-family="Arial, PingFang SC, Microsoft YaHei, sans-serif" font-size="{size}" fill="{fill}" text-anchor="{anchor}"'+(' font-weight="600"' if bold else '')+'>'+html.escape(t)+'</text>')
    a={'start':'ls','middle':'ms','end':'rs'}[anchor]
    d.text((x*S,y*S),t,font=f,fill=fill,anchor=a,stroke_width=0)

def line(points,color=None,width=2,arrow=False,dash=None):
    color=color or C['line']
    p=' '.join(f'{x},{y}' for x,y in points)
    svg.append(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"'+(f' stroke-dasharray="{dash}"' if dash else '')+'/>')
    if dash:
        for (x1,y1),(x2,y2) in zip(points[:-1],points[1:]):
            dist=math.hypot(x2-x1,y2-y1)
            for k in range(0,int(dist),10):
                q=min(k+5,dist)
                d.line(((x1+(x2-x1)*k/dist)*S,(y1+(y2-y1)*k/dist)*S,(x1+(x2-x1)*q/dist)*S,(y1+(y2-y1)*q/dist)*S),fill=color,width=round(width*S))
    else:d.line([(x*S,y*S) for x,y in points],fill=color,width=round(width*S),joint='curve')
    if arrow:
        x,y=points[-1]; px,py=points[-2]; theta=math.atan2(y-py,x-px); z=7
        tri=[(x,y),(x-z*math.cos(theta)+z*.48*math.sin(theta),y-z*math.sin(theta)-z*.48*math.cos(theta)),(x-z*math.cos(theta)-z*.48*math.sin(theta),y-z*math.sin(theta)+z*.48*math.cos(theta))]
        svg.append('<polygon points="'+' '.join(f'{a:.2f},{b:.2f}' for a,b in tri)+f'" fill="{color}"/>')
        d.polygon([(a*S,b*S) for a,b in tri],fill=color)

def mathtext(x,y,segments,size=22,color=None):
    color=color or C['ink']; fs=ImageFont.truetype(FONT,size*S); ss=ImageFont.truetype(FONT,16*S)
    svg.append(f'<text x="{x}" y="{y}" font-family="Arial, PingFang SC, sans-serif" font-size="{size}" fill="{color}">')
    cx=x
    for content,is_sub in segments:
        sub=' baseline-shift="sub" font-size="16"' if is_sub else ''
        svg.append(f'<tspan{sub}>{html.escape(content)}</tspan>')
        f=ss if is_sub else fs; yy=y+5 if is_sub else y
        d.text((cx*S,yy*S),content,font=f,fill=color,anchor='ls')
        cx+=d.textlength(content,font=f)/S
    svg.append('</text>')

# Header and the attention computation area.
text(28,39,'H3 单流 DiT：双向时序 Attention 修正',28,bold=True)
text(29,67,'原 QKV 并行计算两方向；修正原 Joint Attention 的每个 head 输出',17,C['muted'])
rect(24,89,1132,512,C['white'],C['border'],16)
text(43,115,'一个 block 内的 Attention',17,C['muted'])

# Two token tracks, three temporal bins each, three spatial tokens per bin.
for i,x in enumerate([153,239,325],1):
    text(x+35,142,f't{i}',17,C['muted'],'middle')
text(54,171,'生成 T',19,bold=True)
text(54,251,'参考 R',19,bold=True)
for y,color,pale in [(150,C['green'],C['gp']),(230,C['blue'],C['bp'])]:
    for x in [153,239,325]:
        rect(x,y,70,38,pale,color,6,1.2)
        for q in range(3):rect(x+10+q*18,y+10,13,18,color,None,2)
for x in [188,274,360]:
    line([(x-8,226),(x-8,192)],C['green'],2,True)
    line([(x+8,192),(x+8,226)],C['blue'],2,True)
text(153,290,'每个时间 bin 含多个空间 token',16,C['muted'])
line([(395,169),(422,169),(422,249),(395,249)],C['line'],2)
line([(422,207),(462,207)],C['muted'],2,True)

# Shared QKV and the original attention output.
rect(462,157,192,97,C['pale'],C['border'],10)
text(558,195,'原 Q / K / V',23,anchor='middle',bold=True)
text(558,225,'共用原投影',17,C['muted'],'middle')
line([(654,207),(727,207)],C['muted'],2,True)
rect(727,157,233,97,C['pale'],C['border'],10)
text(843.5,195,'原 Joint Attention',21,anchor='middle',bold=True)
text(843.5,225,'所有 token 联合计算',17,C['muted'],'middle')
line([(960,207),(1008,207)],C['muted'],2,True)
rect(1008,176,100,62,'white',C['line'],10)
text(1058,202,'原输出',16,C['muted'],'middle')
text(1058,228,'O',25,anchor='middle',bold=True)

# Shared QKV bus feeds both directions in parallel.
line([(558,254),(558,311)],C['muted'],2)
line([(558,311),(307,311),(307,334)],C['muted'],2,True)
line([(558,311),(872,311),(872,334)],C['muted'],2,True)
rect(600,275,337,25,'white')
text(601,294,'两方向均使用同一组原 Q / K / V',17,C['muted'])

# Parallel correction cards and 3-by-3 same-bin masks.
for x,col,pale,title,q,k,target,coef in [
    (62,C['green'],C['gp'],'正向：参考 → 生成','T','R','T','α'),
    (626,C['blue'],C['bp'],'反向：生成 → 参考 · 新增','R','T','R','β')]:
    rect(x,334,492,163,pale,col,12,1.3)
    text(x+22,365,title,22,col,bold=True)
    mathtext(x+22,395,[('Q',False),(q,True),(' 读取 K',False),(k,True),(' / V',False),(k,True),(' · 同时间 bin',False)],19,col)
    mx,my=x+22,418
    for row in range(3):
        for c in range(3):
            rect(mx+c*18,my+row*18,15,15,col if row==c else '#DCE5E8',None,2)
    text(x+22,486,'同 bin',16,col)
    mathtext(x+93,449,[('ΔO',False),(target,True),(f' = {coef}m',False),(k,True),('(μ',False),(k+',same',True),(' − μ',False),(k+',all',True),(')',False)],22,col)
    text(x+94,480,f'm{k}：原注意力分配给'+('参考' if k=='R' else '生成')+'的总质量',16,C['muted'])

# Original O bypasses the two delta branches until addition.
line([(1108,207),(1137,207),(1137,554),(903,554)],C['muted'],2,True)
text(1108,526,'原 O',16,C['muted'],'end')
line([(307,497),(307,518),(500,518),(500,532)],C['green'],2.4,True)
line([(872,497),(872,518),(733,518),(733,532)],C['blue'],2.4,True)
rect(366,532,537,46,'white',C['line'],9,1.4)
mathtext(385,561,[('O′ = [O',False),('T',True),(' + ΔO',False),('T',True),(',  O',False),('R',True),(' + ΔO',False),('R',True),(']',False)],22)
text(899,593,'各 head 输出相加后再投影',16,C['muted'],'middle')

# Explicit out_proj boundary and downstream propagation.
line([(42,608),(1138,608)],C['line'],1.5,False,'5 5')
rect(40,596,158,24,'white')
text(43,613,'out_proj 边界',17,C['muted'])
line([(637,578),(637,626)],C['muted'],2,True)
rect(557,626,160,54,C['pale'],C['border'],9)
mathtext(591,660,[('W',False),('O',True),(' 投影',False)],22)
line([(717,653),(757,653)],C['muted'],2,True)
rect(757,626,180,54,C['pale'],C['border'],9)
text(847,660,'残差 / FFN',21,anchor='middle',bold=True)
line([(937,653),(976,653)],C['muted'],2,True)
rect(976,626,168,54,'white',C['line'],9)
text(1060,660,'下一个 block',21,anchor='middle',bold=True)
text(43,647,'参考初始 latent',18,bold=True)
text(43,675,'每个采样步重新提供',17,C['muted'])
line([(557,704),(1143,704)],C['line'],1)
text(557,730,'参考 hidden states 更新后，继续影响后续层生成',18,C['muted'])
text(43,726,'T：生成 token　R：参考 token',16,C['muted'])
svg.append('</svg>')
(OUT/'dual_attention.svg').write_text('\n'.join(svg),encoding='utf-8')
im.resize((W,H),Image.Resampling.LANCZOS).save(OUT/'dual_attention_preview.png')
print('Wrote dual_attention.svg and dual_attention_preview.png')
