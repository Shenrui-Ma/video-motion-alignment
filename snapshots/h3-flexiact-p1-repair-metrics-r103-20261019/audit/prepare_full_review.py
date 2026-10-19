"""Create exhaustive same-index review sheets from verified R103 actual media."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True, choices=[
        'human2animal_2__game_man_4', 'chest__game_girl_1'])
    parser.add_argument('--paired', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = root / ('showcase_pairs' if args.paired else 'showcase') / args.source / 'PRESENTATION.json'
    data = json.loads(manifest.read_text())
    assert sha(data['gate']['file']) == data['gate']['sha256']
    assert json.loads(Path(data['gate']['file']).read_text())['passed']
    assert data['columns'] == (['source', 'native', 'forced'] if args.paired else ['source', 'native'])
    timeline = data['timeline']
    n, fps = timeline['valid_frames'], timeline['fps']
    assert n == 147 and fps == 24
    x, y, crop_width, crop_height = timeline['crop_xywh']
    assert (x, y, crop_width, crop_height) == (0, 0, 1152, 768)
    width, height = 480, 320
    out = root / 'audit' / ('root_pair_review' if args.paired else 'root_native_review') / args.source
    out.mkdir(parents=True, exist_ok=True)
    assert not (out / 'FRAME_LEDGER.json').exists()
    frames = []
    for entry in data['inputs']:
        assert sha(entry['file']) == entry['sha256']
        raw = subprocess.check_output([
            '/opt/homebrew/bin/ffmpeg', '-v', 'error', '-threads', '1', '-i', entry['file'],
            '-vf', f'crop={crop_width}:{crop_height}:{x}:{y},scale={width}:{height}:flags=lanczos',
            '-frames:v', str(n), '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-threads', '1', '-',
        ])
        assert len(raw) == n * width * height * 3
        frames.append(raw)
    font = ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc', 16)
    labels = ['参考视频', '普通编辑', '时序引导']
    pages = []
    for start in range(0, n, 5):
        indices = list(range(start, min(n, start + 5)))
        image = Image.new('RGB', (len(frames) * width, len(indices) * (height + 26)), 'black')
        draw = ImageDraw.Draw(image)
        for row, index in enumerate(indices):
            for column, raw in enumerate(frames):
                position = index * width * height * 3
                image.paste(Image.frombytes('RGB', (width, height), raw[position:position + width * height * 3]),
                            (column * width, row * (height + 26)))
                draw.text((column * width + 4, row * (height + 26) + height + 3),
                          f'{labels[column]} | f{index:03d} | {index / fps:.3f}s', font=font, fill='white')
        path = out / f'frames_{start:03d}_{indices[-1]:03d}.jpg'
        image.save(path, quality=96)
        pages.append({'file': str(path), 'sha256': sha(path), 'indices': indices})
    (out / 'FRAME_LEDGER.json').write_text(json.dumps({
        'manifest': str(manifest), 'manifest_sha256': sha(manifest), 'inputs': data['inputs'],
        'physical_indices': list(range(n)), 'fps': fps, 'pages': pages,
        'scope': 'All actual 24fps output frames. Source 8fps frames are repeated three times; preserve provenance.',
    }, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'out': str(out), 'frames': n, 'pages': len(pages)}))


if __name__ == '__main__':
    main()
