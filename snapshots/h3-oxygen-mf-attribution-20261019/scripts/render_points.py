"""Plot the existing full-trajectory contribution at actual source track positions."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PARENT = Path('/Users/researcher/DevProjects/h3-ivebench-expanded-metrics-r73-20261018')
points = json.loads((ROOT / 'results/SOURCE_POINT_DELTAS.json').read_text())
summary = json.loads((ROOT / 'results/SUMMARY.json').read_text())
source = Path(summary['inputs']['source']['path'])
assert hashlib.sha256(source.read_bytes()).hexdigest() == summary['inputs']['source']['sha256']
with np.load(source, allow_pickle=False) as archive:
    tracks = archive['tracks'][0]
    visibility = archive['visibility'][0]
font_path = '/System/Library/Fonts/Supplemental/Arial.ttf'
font = ImageFont.truetype(font_path, 17)
heading = ImageFont.truetype(font_path, 24)
small = ImageFont.truetype(font_path, 18)
peak = max(abs(point['score_delta']) for point in points)
metadata = []
for image_number, frame in enumerate([0, 48, 72], 1):
    plain = Image.open(ROOT / f'figures/source_{image_number:02}.png').convert('RGB')
    assert plain.size == (1280, 720)
    canvas = Image.new('RGB', (1280, 840), '#10141b')
    canvas.paste(plain, (0, 120))
    draw = ImageDraw.Draw(canvas)
    draw.text((20, 12), f'Oxygen0252 | source frame {frame:02} | {frame/24:.3f}s', fill='white', font=heading)
    draw.text((20, 46), 'Whole-trajectory MF contribution: guided minus ordinary; labels = point IDs', fill='#d7dce5', font=small)
    draw.text((20, 74), 'Blue: gain | Red: loss | Circle area: magnitude | Hollow: source tracker visibility <= 0.5', fill='#d7dce5', font=small)
    omitted = []
    for point in points:
        index = point['source_id']
        x, y = map(float, tracks[frame, index])
        if not (0 <= x < 1280 and 0 <= y < 720):
            omitted.append(index)
            continue
        y += 120
        delta = point['score_delta']
        radius = 5 + 14 * (abs(delta) / peak) ** .5
        color = '#47c6ff' if delta >= 0 else '#ff6f75'
        bounds = (x-radius, y-radius, x+radius, y+radius)
        draw.ellipse(bounds, fill=color if visibility[frame, index] > .5 else None, outline='white', width=2)
        text = str(index)
        box = draw.textbbox((0, 0), text, font=font)
        tx = min(1278-(box[2]-box[0]), max(2, x+radius+2))
        ty = min(818, max(122, y-8))
        draw.text((tx, ty), text, font=font, fill='white', stroke_width=2, stroke_fill='black')
    output = ROOT / f'figures/point_contributions_frame_{frame:03}.png'
    canvas.save(output)
    metadata.append({'frame': frame, 'seconds': frame/24, 'output': str(output), 'outside_image_ids': omitted})
(ROOT / 'figures/PLOT_METADATA.json').write_text(json.dumps({
    'definition': 'Colors and sizes show each matched trajectory contribution to the complete 98-frame MF difference. Positions are raw source tracks at the stated frame. These are not per-frame scores or anatomy labels.',
    'peak_absolute_contribution': peak, 'frames': metadata,
}, indent=2) + '\n')
