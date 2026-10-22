"""Build a self-contained research timeline and a matching diagram preview."""
import json
from html import escape
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONT = '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'
W, H = 1440, 820
LEFT, DAY, TOP, ROW = 190, 80, 108, 68
image = Image.new('RGB', (W, H), '#ffffff')
draw = ImageDraw.Draw(image)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" class="timeline" viewBox="0 0 {W} {H}" role="img" aria-labelledby="timeline-title timeline-desc">',
       '<title id="timeline-title">H3研究方向、实验分支与关键决策，10月7日至21日</title>',
       '<desc id="timeline-desc">从背景泄漏转向动作时间对齐；同时间Attention发展出自动决策、空间与相位改动、区间比较、双向结构分支。点击条带可查看详细记录。</desc>',
       f'<rect width="{W}" height="{H}" fill="#ffffff"/>']


def rect(x, y, w, h, fill, radius=0, cls=''):
    svg.append(f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}"/>')
    draw.rounded_rectangle((x,y,x+w,y+h),radius=radius,fill=fill)


def text(x, y, s, size=16, fill='#233d4c', anchor='start'):
    svg.append(f'<text x="{x}" y="{y}" dominant-baseline="text-before-edge" font-size="{size}" fill="{fill}" text-anchor="{anchor}">{escape(s)}</text>')
    font=ImageFont.truetype(FONT,size)
    box=draw.textbbox((0,0),s,font=font)
    width=draw.textlength(s,font=font)
    px=x-(width/2 if anchor=='middle' else width if anchor=='end' else 0)
    draw.text((px,y-box[1]),s,font=font,fill=fill)


def line(points, color='#e4e9ec', width=1):
    svg.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in points)+f'" stroke="{color}" stroke-width="{width}" fill="none"/>')
    draw.line(points,fill=color,width=width)


def x(day): return LEFT+(day-7)*DAY
def y(row): return TOP+row*ROW


text(28,30,'研究方向',15,'#667a87')
text(LEFT,25,'2026 / 10',13,'#667a87')
for d in range(7,22):
    text(x(d)+DAY/2,55,f'{d:02d}',14,'#667a87','middle')
    line([(x(d),82),(x(d),H-49)])
line([(x(22),82),(x(22),H-49)])
lanes=['背景泄漏','研究问题','Attention 引导','自动决策','latent 观察','公开数据与评测','空间特征匹配','RoPE 时间相位','去噪引导区间','双向 Attention']
for i,name in enumerate(lanes):
    text(28,y(i)+14,name,16)
    line([(22,y(i)+59),(W-30,y(i)+59)],'#f0f3f5')

# Draw branch connections behind bars, keeping label areas clear.
connections=[[(x(8.9),y(0)+46),(x(8.9),y(1)+24),(x(12),y(1)+24)],
             [(x(15.8),y(1)+46),(x(15.8),y(2)+24),(x(16.05),y(2)+24)],
             [(x(16.2),y(2)+46),(x(16.2),y(3))],
             [(x(20.8),y(3)+46),(x(20.8),y(4))],
             [(x(17.3),y(2)+46),(x(17.3),y(5))],
             [(x(19.25),y(5)+46),(x(19.25),y(6))],
             [(x(20.3),y(6)+46),(x(20.3),y(7))],
             [(x(20.3),y(7)+46),(x(20.3),y(8))],
             [(x(21.4),y(2)+46),(x(21.4),y(9))]]
for points in connections:line(points,'#c1ccd3',2)

bars=[
 ('background',0,7,9,'抠图排除干扰','10.08 停止','stopped'),
 ('question',1,12,15,'短事件保真','转查动作遗漏与时间偏移','done'),
 ('question',1,15,22,'转向动作时间对齐','从手势缺失与变形，转到编辑后的动作发生时间','done'),
 ('attention',2,13,16,'参考权重 2× / 3×','真人换人出现时序改善','done'),
 ('attention',2,16,22,'同时间 Attention 重分配','保留参考总概率，调整参考特征的时间分配','done'),
 ('automatic',3,16,21,'自动选窗 → 姿态反馈启停','公开数据触发不足；10.20 停止逐步 RGB 方案','stopped'),
 ('latent',4,20,22,'latent 时差估计','保留离线候选','candidate'),
 ('benchmark',5,17,22,'FlexiAct / IVEBench','先验收编辑，再检查时差；保留 MF 与简短任务句','done'),
 ('spatial',6,19,21,'空间 Value 匹配','归档，未沿用','stopped'),
 ('phase',7,20,21,'相位复测','未沿用','stopped'),
 ('schedule',8,20,21,'区间对照','3组 → 10组','done'),
 ('schedule',8,21,22,'全程弱','当前优先','current'),
 ('reciprocal',9,21,22,'双向约束','保留候选','candidate'),
]
colors={'done':('#e8f0f6','#aac4d6'),'stopped':('#f5ece6','#d8b59f'),'candidate':('#efebf6','#bbaed4'),'current':('#dcefe9','#62a99b')}
for group,row,start,end,title,detail,status in bars:
    bx,by,bw=x(start)+3,y(row),DAY*(end-start)-6
    svg.append(f'<a href="#records-section" data-group="{group}" aria-label="{escape(title)}：{escape(detail)}">')
    fill,accent=colors[status]
    rect(bx,by,bw,48,fill,4,'bar')
    rect(bx,by,4,48,accent,2)
    small=bw<100
    title_size=14 if small else 16
    detail_size=12 if small else 13
    for label,size in [(title,title_size),(detail,detail_size)]:
        assert draw.textlength(label,font=ImageFont.truetype(FONT,size)) <= bw-(8 if small else 20), label
    if small:
        text(bx+bw/2,by+6,title,title_size,anchor='middle')
        text(bx+bw/2,by+28,detail,detail_size,'#62717e','middle')
    else:
        text(bx+13,by+5,title,title_size)
        text(bx+13,by+28,detail,detail_size,'#62717e')
    svg.append('</a>')
text(LEFT,H-29,'条带按日期排列；停止与保留状态截至 10.21。',12,'#7a8c97')
svg.append('</svg>')
svg_text='\n'.join(svg)
(ROOT/'timeline.svg').write_text(svg_text)
image.save(ROOT/'timeline-preview.png',optimize=True)
data=json.loads((ROOT/'timeline.json').read_text())
template=(ROOT/'template.html').read_text()
assert template.count('__TIMELINE__')==template.count('__DATA__')==1
html=template.replace('__TIMELINE__',svg_text).replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c'))
(ROOT/'index.html').write_text(html)
print(ROOT/'index.html')
