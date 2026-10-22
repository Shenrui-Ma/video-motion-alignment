"""Build the eight-card linear timeline and a matching local diagram preview."""
import json
from html import escape
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONT = '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'
DATA = json.loads((ROOT / 'timeline.json').read_text())
W, H = 2796, 356
CARD_W, CARD_H, GAP = 304, 256, 42
LEFT, TOP = 35, 50
image = Image.new('RGB', (W, H), '#ffffff')
draw = ImageDraw.Draw(image)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" class="timeline" viewBox="0 0 {W} {H}" role="img" aria-labelledby="timeline-title timeline-desc">',
       '<title id="timeline-title">H3 动作时序研究关键决策时间轴</title>',
       '<desc id="timeline-desc">八个按时间排列的研究节点，通过一条从左向右的箭头连接：短动作保真、参考加权、动作时间对齐、同时间Attention、自动启停、RoPE、区间对照、全程弱引导。</desc>',
       f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
checks = []


def rect(x, y, width, height, fill, radius=0, stroke=None):
    edge = f' stroke="{stroke}" stroke-width="1"' if stroke else ''
    svg.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" fill="{fill}"{edge}/>')
    draw.rounded_rectangle((x, y, x+width, y+height), radius=radius, fill=fill, outline=stroke)


def text(x, y, label, size=17, color='#334d5b', max_width=None):
    font = ImageFont.truetype(FONT, size)
    width = draw.textlength(label, font=font)
    if max_width is not None:
        assert width <= max_width, (label, width, max_width)
        checks.append({'text': label, 'width': round(width, 2), 'available': max_width})
    svg.append(f'<text x="{x}" y="{y}" dominant-baseline="text-before-edge" font-size="{size}" fill="{color}">{escape(label)}</text>')
    box = draw.textbbox((0, 0), label, font=font)
    draw.text((x, y-box[1]), label, font=font, fill=color)


def arrow(x1, x2, y):
    svg.append(f'<path d="M{x1} {y} H{x2-6} M{x2-12} {y-5} L{x2-6} {y} L{x2-12} {y+5}" fill="none" stroke="#9baab4" stroke-width="1.5"/>')
    draw.line([(x1, y), (x2-6, y)], fill='#9baab4', width=2)
    draw.line([(x2-12, y-5), (x2-6, y), (x2-12, y+5)], fill='#9baab4', width=2)


assert len(DATA['events']) == 8
for i, event in enumerate(DATA['events']):
    x = LEFT+i*(CARD_W+GAP)
    y = TOP
    current = event['state'] == 'current'
    stopped = event['state'] == 'stopped'
    fill, stroke = ('#edf7f4', '#83b9aa') if current else ('#ffffff', '#c9d5dd')
    accent = '#267b68' if current else '#945e46' if stopped else '#37647e'
    if i:
        arrow(x-GAP+7, x-2, y+CARD_H/2)
    svg.append(f'<g id="{event["id"]}" aria-label="{escape(event["date"]+"，"+event["title"]+"。"+"".join(event["lines"])+event["decision"])}">')
    rect(x, y, CARD_W, CARD_H, fill, 7, stroke)
    rect(x+20, y+20, 25, 22, accent, 3)
    text(x+25, y+23, f'{i+1:02}', 12, '#ffffff')
    text(x+56, y+22, event['date'], 14, '#6a7e8b', CARD_W-78)
    text(x+20, y+60, event['title'], 18, '#213f50', CARD_W-40)
    for j, label in enumerate(event['lines']):
        text(x+20, y+105+j*29, label, 16, '#465d6b', CARD_W-40)
    rect(x+20, y+204, CARD_W-40, 1, '#dfe7ec' if not current else '#c8dfd7')
    text(x+20, y+219, event['decision'], 14, accent, CARD_W-40)
    svg.append('</g>')
svg.append('</svg>')
svg_text = '\n'.join(svg)
(ROOT / 'timeline.svg').write_text(svg_text)
image.save(ROOT / 'timeline-preview.png', optimize=True)
image.crop((0, 0, 1400, H)).save(ROOT / 'timeline-preview-start.png', optimize=True)
image.crop((1396, 0, W, H)).save(ROOT / 'timeline-preview-end.png', optimize=True)
template = (ROOT / 'template.html').read_text()
assert template.count('__TIMELINE__') == template.count('__DATA__') == 1
html = template.replace('__TIMELINE__', svg_text).replace('__DATA__', json.dumps(DATA, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c'))
(ROOT / 'index.html').write_text(html)
(ROOT / 'audit' / 'TEXT_BOUNDS.json').write_text(json.dumps({'passed': True, 'labels': checks}, ensure_ascii=False, indent=2)+'\n')
print(ROOT / 'index.html')
