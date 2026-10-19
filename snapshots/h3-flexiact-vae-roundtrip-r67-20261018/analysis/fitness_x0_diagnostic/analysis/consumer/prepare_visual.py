"""Literal same-time source / saved endpoint contact sheets, with byte/PTS checks."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
X0 = HERE.parents[1]
R67 = X0.parents[1]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
FONT = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 18)


def extract(key):
    if key == 'source':
        receipt = R67 / 'inputs/fitness/PREPARED.json'
        folder = receipt.parent
        item = json.loads(receipt.read_text())['products']['prepared_original49']
    else:
        receipt = X0 / 'outputs' / key / 'RESULT.json'
        folder = receipt.parent
        result = json.loads(receipt.read_text())
        assert result['status'] == 'complete' and result['fallback_guard']['calls'] == 0
        item = result['products']['x0_original49']
    video = folder / item['file']
    assert sha(video) == item['sha256'] and item['selected_full158_indices'] == list(range(0, 147, 3))
    probe = json.loads(subprocess.check_output([
        '/opt/homebrew/bin/ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_frames',
        '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', str(video)]))
    pts = [float(x['best_effort_timestamp_time']) for x in probe['frames']]
    assert len(pts) == 49 and all(abs(t - i / 8) < 1e-5 for i, t in enumerate(pts))
    dest = HERE / 'visual' / key
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(['/opt/homebrew/bin/ffmpeg', '-v', 'error', '-y', '-i', str(video),
                    '-fps_mode', 'passthrough', '-start_number', '0', str(dest / '%03d.png')], check=True)
    frames = sorted(dest.glob('*.png'))
    assert len(frames) == 49
    (dest / 'BINDING.json').write_text(json.dumps({'video_sha256': sha(video),
        'receipt_sha256': sha(receipt), 'physical_times': pts,
        'frames_sha256': [sha(f) for f in frames]}, indent=2) + '\n')
    return dest


def sheet(keys, labels, indices, file):
    width, height, cap = 384, 256, 30
    canvas = Image.new('RGB', (width * len(keys), (height + cap) * len(indices)), 'black')
    draw = ImageDraw.Draw(canvas)
    for row, i in enumerate(indices):
        for col, (key, label) in enumerate(zip(keys, labels)):
            image = Image.open(HERE / 'visual' / key / f'{i:03d}.png').convert('RGB')
            assert image.size == (1152, 768)
            canvas.paste(image.resize((width, height), Image.Resampling.LANCZOS),
                         (col * width, row * (height + cap)))
            draw.text((col * width + 5, row * (height + cap) + height + 3),
                      f'{label} | {i/8:.3f}s', font=FONT, fill='white')
    canvas.save(HERE / 'visual' / file)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key', action='append', required=True)
    args = parser.parse_args()
    extract('source')
    for key in args.key:
        assert key in ['native_step002_attempt1', 'native_step005_attempt1',
                       'native_step006_attempt1', 'forced_step006_attempt1']
        extract(key)
        title = key.replace('_attempt1', '').replace('_step', ' x0 index ')
        sheet(['source', key], ['实际参考 RGB', title], [0, 4, 8, 12, 16, 20], key + '_six_times.png')
    if all((HERE / 'visual' / k).is_dir() for k in ['native_step006_attempt1', 'forced_step006_attempt1']):
        keys = ['source', 'native_step006_attempt1', 'forced_step006_attempt1']
        labels = ['实际参考 RGB', 'Native x0 index 6', '首次引导 x0 index 6']
        sheet(keys, labels, [0, 4, 8, 12, 16, 20], 'same_state_index6_six_times.png')
        for start in range(0, 49, 7):
            sheet(keys, labels, list(range(start, start + 7)), f'same_state_all49_{start:02d}_{start+6:02d}.png')
    keys = ['source', 'native_step002_attempt1', 'native_step005_attempt1', 'native_step006_attempt1']
    if all((HERE / 'visual' / k).is_dir() for k in keys):
        sheet(keys, ['实际参考 RGB', 'Native x0 index 2', 'Native x0 index 5', 'Native x0 index 6'],
              [0, 4, 8, 12, 16, 20], 'native_evolution_six_times.png')


if __name__ == '__main__':
    main()
