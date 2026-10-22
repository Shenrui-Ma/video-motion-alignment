"""Decode every frame and export descriptive scene proxies plus temporal sheets."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw

WIDTH, HEIGHT = 384, 216


def scene_proxies(frames):
    pixels = frames.astype(np.float32)
    region = np.zeros((HEIGHT, WIDTH), dtype=bool)
    region[:int(HEIGHT * 0.35), :int(WIDTH * 0.30)] = True
    region[:int(HEIGHT * 0.35), int(WIDTH * 0.70):] = True
    red, green, blue = pixels[..., 0], pixels[..., 1], pixels[..., 2]
    sky = (green > 1.15 * red) & (blue > 1.15 * red) & (pixels.max(axis=-1) > 65)
    dark = pixels.max(axis=-1) < 50
    return sky[:, region].mean(axis=1), dark[:, region].mean(axis=1)


def analyze(video, out):
    out.mkdir(parents=True, exist_ok=True)
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                            '-of', 'json', str(video)], capture_output=True, check=True)
    metadata = json.loads(probe.stdout)
    stream = next(s for s in metadata['streams'] if s['codec_type'] == 'video')
    numerator, denominator = map(int, stream['avg_frame_rate'].split('/'))
    fps = numerator / denominator
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video),
                              '-map', '0:v:0', '-vf', f'scale={WIDTH}:{HEIGHT}',
                              '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'],
                             capture_output=True, check=True)
    size = WIDTH * HEIGHT * 3
    if len(decoded.stdout) % size:
        raise ValueError('Decoded RGB data is not a whole number of frames')
    frames = np.frombuffer(decoded.stdout, np.uint8).reshape(-1, HEIGHT, WIDTH, 3)
    if len(frames) == 0:
        raise ValueError('No decoded frames')
    sky, dark = scene_proxies(frames)
    with (out / 'frame_metrics.csv').open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['frame', 'seconds', 'upper_corner_cyan_fraction', 'upper_corner_dark_fraction'])
        writer.writerows((i, i / fps, float(sky[i]), float(dark[i])) for i in range(len(frames)))
    indices = np.unique(np.linspace(0, len(frames) - 1, min(12, len(frames))).round().astype(int))
    sheet = Image.new('RGB', (WIDTH * 4, (HEIGHT + 24) * ((len(indices) + 3) // 4)), '#eeeeee')
    draw = ImageDraw.Draw(sheet)
    for j, index in enumerate(indices):
        x, y = (j % 4) * WIDTH, (j // 4) * (HEIGHT + 24)
        sheet.paste(Image.fromarray(frames[index]), (x, y))
        draw.text((x + 5, y + HEIGHT + 4), f'frame {index} | {index / fps:.2f} s', fill='black')
    sheet.save(out / 'temporal_sheet.jpg', quality=92)
    result = {'video': str(video.resolve()), 'sha256': hashlib.sha256(video.read_bytes()).hexdigest(),
              'probe': metadata, 'decoded_frame_count': len(frames), 'fps': fps,
              'analysis_size': [WIDTH, HEIGHT], 'sampled_frame_indices': indices.tolist(),
              'descriptive_proxies': {'upper_corner_cyan_mean': float(sky.mean()),
                                      'upper_corner_dark_mean': float(dark.mean())},
              'limitations': ['Upper-corner proxies describe scene change, not a semantic leakage detector.',
                              'Lighting, camera, roofs and subject occlusion can change these proxies.',
                              'Semantic claims require paired source/reference visual inspection.']}
    (out / 'analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({k: result[k] for k in ['video', 'decoded_frame_count', 'fps', 'descriptive_proxies']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('video', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    analyze(args.video, args.output)
