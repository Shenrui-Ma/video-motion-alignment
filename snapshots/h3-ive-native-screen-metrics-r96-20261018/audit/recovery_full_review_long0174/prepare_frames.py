from pathlib import Path
import json, hashlib, subprocess
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
manifest = ROOT / 'showcase/long_0174/PRESENTATION.json'
data = json.loads(manifest.read_text())
assert data['columns'] == ['source', 'native']
assert data['timeline']['valid_frames'] == 145
assert data['timeline']['fps'] == 24
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
frames = []
for item in data['inputs']:
    assert sha(item['file']) == item['sha256']
    raw = subprocess.check_output([
        '/opt/homebrew/bin/ffmpeg', '-v', 'error', '-threads', '1',
        '-i', item['file'], '-vf', 'crop=1280:720:16:8,scale=480:270',
        '-frames:v', '145', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-threads', '1', '-'])
    assert len(raw) == 145 * 480 * 270 * 3
    frames.append(raw)
font = ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc', 18)
pages = []
for first in range(0, 145, 10):
    ids = list(range(first, min(145, first + 10)))
    image = Image.new('RGB', (960, len(ids) * 300), 'black')
    draw = ImageDraw.Draw(image)
    for row, idx in enumerate(ids):
        for col, raw in enumerate(frames):
            image.paste(Image.frombytes('RGB', (480, 270), raw[idx*480*270*3:(idx+1)*480*270*3]), (col*480, row*300))
            draw.text((col*480+8, row*300+274), f'{["Source", "Native"][col]}  f{idx:03d}  {idx/24:.3f}s', font=font, fill='white')
    target = OUT / f'frames_{first:03d}_{ids[-1]:03d}.jpg'
    image.save(target, quality=96)
    pages.append({'file':str(target), 'sha256':sha(target), 'frames':ids})
ledger = {'presentation':{'file':str(manifest),'sha256':sha(manifest)}, 'inputs':data['inputs'], 'frame_indices':list(range(145)), 'pages':pages, 'scope':'All 145 valid frames; same physical timestamp; equal crop and scale.'}
(OUT/'FRAME_LEDGER.json').write_text(json.dumps(ledger, indent=2)+'\n')
print(len(pages))
