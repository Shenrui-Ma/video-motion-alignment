"""CPU-only full original-frame sheets for the unrun source/prompt review."""
from pathlib import Path
import hashlib
import json
import subprocess
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[1]
source = root / 'inputs/source_human2animal_2_original.mp4'
provenance = json.loads((root / 'inputs/source_human2animal_2_provenance.json').read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(source) == provenance['source_original_sha256']
out = root / 'audit/root_prompt_review/human2animal_2'
out.mkdir(parents=True, exist_ok=True)
assert not (out / 'FRAME_LEDGER.json').exists()
raw = subprocess.check_output(['/opt/homebrew/bin/ffmpeg', '-v', 'error', '-threads', '1', '-i', str(source), '-vf', 'scale=360:240:flags=lanczos', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-threads', '1', '-'])
size = 360 * 240 * 3
assert len(raw) == size * 49
font = ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc', 15)
pages = []
for start in range(0, 49, 16):
    indices = list(range(start, min(start + 16, 49)))
    sheet = Image.new('RGB', (1440, ((len(indices) + 3) // 4) * 268), 'black')
    draw = ImageDraw.Draw(sheet)
    for j, i in enumerate(indices):
        x, y = (j % 4) * 360, (j // 4) * 268
        sheet.paste(Image.frombytes('RGB', (360, 240), raw[i*size:(i+1)*size]), (x, y))
        draw.text((x + 4, y + 244), f'source f{i:02d} | {i/8:.3f}s | input f{3*i:03d}', fill='white', font=font)
    path = out / f'frames_{indices[0]:02d}_{indices[-1]:02d}.jpg'
    sheet.save(path, quality=96)
    pages.append({'path': str(path), 'sha256': sha(path), 'indices': indices})
(out / 'FRAME_LEDGER.json').write_text(json.dumps({'source': str(source), 'source_sha256': sha(source), 'fps': 8, 'frames': 49, 'input_fps': 24, 'input_repeat': 3, 'pages': pages}, indent=2) + '\n')
print(json.dumps({'pages': pages}, indent=2))
