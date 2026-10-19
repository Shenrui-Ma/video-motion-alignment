"""Extract six fixed frames from an already archived R74 result. No inference."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
from PIL import Image, ImageDraw

out = Path(__file__).resolve().parent
p = Path('/Users/researcher/Downloads/H3_Benchmark_完整对比归档_20261018/未成对结果/R74/r74_chest__game_man_5_seed2026101701_native_00001_.mp4')
canvas = Image.new('RGB', (1536, 720))
draw = ImageDraw.Draw(canvas)
frames = [0, 24, 48, 72, 96, 144]
for j, n in enumerate(frames):
    encoded = subprocess.check_output([
        '/opt/homebrew/bin/ffmpeg', '-v', 'error', '-i', str(p),
        '-vf', f'select=eq(n\\,{n}),scale=512:342', '-frames:v', '1',
        '-f', 'image2pipe', '-vcodec', 'png', '-'])
    canvas.paste(Image.open(io.BytesIO(encoded)), (j % 3 * 512, j // 3 * 360))
    draw.text((j % 3 * 512 + 5, j // 3 * 360 + 343), f'frame {n} | {n / 24:.3f}s', fill='white')
canvas.save(out / 'r74_chest_game5_native_six.png')
(out / 'VISUAL_INPUT.json').write_text(json.dumps(dict(video=str(p),
    sha256=hashlib.sha256(p.read_bytes()).hexdigest(), frames=frames), indent=2) + '\n')
