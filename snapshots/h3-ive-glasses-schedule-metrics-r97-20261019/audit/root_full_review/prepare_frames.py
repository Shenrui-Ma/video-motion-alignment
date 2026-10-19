from pathlib import Path
import hashlib, json, subprocess
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
manifest = ROOT / 'showcase/PRESENTATION.json'
data = json.loads(manifest.read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(data['gate']['file']) == data['gate']['sha256']
assert json.loads(Path(data['gate']['file']).read_text())['passed']
assert data['columns'] == ['source', 'native', 'fixed', 'extended']
width, height, n = 384, 216, 105
frames = []
for entry in data['inputs']:
    assert sha(entry['file']) == entry['sha256']
    raw = subprocess.check_output(['/opt/homebrew/bin/ffmpeg', '-v', 'error', '-threads', '1', '-i', entry['file'], '-vf', f'crop=1280:720:16:8,scale={width}:{height}:flags=lanczos', '-frames:v', str(n), '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-threads', '1', '-'])
    assert len(raw) == n * width * height * 3
    frames.append(raw)
font = ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc', 17)
labels = ['参考视频', '普通编辑', '固定引导6–14', '延长引导6–19']
pages = []
for start in range(0, n, 5):
    indices = list(range(start, min(start + 5, n)))
    im = Image.new('RGB', (4 * width, len(indices) * (height + 30)), 'black')
    draw = ImageDraw.Draw(im)
    for row, index in enumerate(indices):
        for col, raw in enumerate(frames):
            pos = index * width * height * 3
            im.paste(Image.frombytes('RGB', (width, height), raw[pos:pos + width * height * 3]), (col * width, row * (height + 30)))
            draw.text((col * width + 5, row * (height + 30) + height + 4), f'{labels[col]} | f{index:03d} | {index / 24:.3f}s', fill='white', font=font)
    path = OUT / f'frames_{start:03d}_{indices[-1]:03d}.jpg'
    im.save(path, quality=96)
    pages.append({'path': str(path), 'sha256': sha(path), 'indices': indices})
(OUT / 'FRAME_LEDGER.json').write_text(json.dumps({'presentation': str(manifest), 'presentation_sha256': sha(manifest), 'inputs': data['inputs'], 'pages': pages, 'physical_indices': list(range(n)), 'role': 'diagnostic contact sheets at unchanged frame indices'}, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'pages': len(pages), 'frames': n}))
