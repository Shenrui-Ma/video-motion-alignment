"""Render preregistered source-event intervals; no generated-outcome labels."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / 'inputs/source_manifest.json').read_text())
im = Image.new('RGB', (1500, 800), '#f7f9fc')
d = ImageDraw.Draw(im)


def font(size):
    return ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', size)


d.text((50, 32), '这轮实际研究的短事件：完整过程与决定性姿态分开', font=font(31), fill='#18324b')
d.text((50, 82), '零起始帧号 · 24 FPS · 每段 141 帧 / 5.875 秒 · 图中范围为输入片段标注', font=font(21), fill='#4d6073')
x0, x1 = 260, 1420
scale = (x1 - x0) / 141
labels = {'05_real_megumi_v': '真人 Megumi', '06_anime_eye_insert': '动画换人', '07_real_ary_v': '真人 Ary'}
for k, clip in enumerate(manifest['clips']):
    y = 190 + k * 175
    event = clip['event']
    lo, hi = event['transition_frames_inclusive']
    core = event['decisive_frames_inclusive']
    d.text((50, y - 18), labels[clip['clip_id']], font=font(25), fill='#18324b')
    d.text((50, y + 25), f'完整 {event["full_event_duration_seconds"]:.3f} 秒', font=font(20), fill='#435a71')
    d.line((x0, y, x1, y), fill='#cad4df', width=7)
    d.rounded_rectangle((x0 + lo * scale, y - 13, x0 + (hi + 1) * scale, y + 13), radius=6, fill='#ed9650')
    d.rectangle((x0 + core[0] * scale, y - 14, x0 + (core[1] + 1) * scale, y + 14), fill='#b32e45')
    for frame in range(0, 141, 12):
        x = x0 + frame * scale
        d.ellipse((x - 4, y + 34, x + 4, y + 42), fill='#277aba')
    for frame in (0, 24, 48, 72, 96, 120, 140):
        d.text((x0 + frame * scale - 12, y - 48), str(frame), font=font(17), fill='#5b6e80')
    sampled = ('2 FPS 语义采样未命中短事件。' if clip['clip_id'].startswith('06')
               else '2 FPS 语义采样命中第 60 帧。')
    d.text((x0, y + 57), f'完整事件 {lo}–{hi} 帧；核心 {core[0]}–{core[1]} 帧。{sampled}', font=font(20), fill='#28445e')
d.rounded_rectangle((50, 704, 1450, 775), radius=10, fill='#eaf0f7')
d.text((72, 716), '橙色：手靠近脸并离开的完整过程   深红：最清晰姿态   蓝点：实际语义采样帧', font=font(20), fill='#23405d')
d.text((72, 746), '三段的稠密 VAE 回解都保留手—脸关系；“语义帧未命中”不等于整模型看不到动作。', font=font(20), fill='#23405d')
path = ROOT / 'analysis/source_event_map.png'
im.save(path)
print(path)
