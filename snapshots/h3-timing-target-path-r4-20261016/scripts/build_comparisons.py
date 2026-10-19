"""Render equal-size, timestamp-preserving research triptychs with black footers.

Only display scaling is applied. No frame shift, interpolation, or selective
spatial cropping is used. Raw inputs remain separate and unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont

FFMPEG = '/opt/homebrew/bin/ffmpeg'
FFPROBE = '/opt/homebrew/bin/ffprobe'


def probe(path):
    result = subprocess.run([FFPROBE, '-v', 'error', '-select_streams', 'v:0',
        '-count_frames', '-show_entries',
        'stream=width,height,avg_frame_rate,nb_read_frames,duration',
        '-of', 'json', str(path)], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)['streams'][0]


def render(source, baseline, intervention, destination, label, first=0, last=141):
    paths = [Path(x).resolve() for x in (source, baseline, intervention)]
    info = [probe(x) for x in paths]
    if not all(x['avg_frame_rate'] == '24/1' and int(x['nb_read_frames']) == 141 for x in info):
        raise ValueError(f'Unexpected input frames/FPS: {info}')
    if not 0 <= first < last <= 141:
        raise ValueError('Expected a valid half-open source-frame interval')
    fonts = sorted(Path('/System/Library/AssetsV2/com_apple_MobileAsset_Font8').glob('*.asset/AssetData/PingFang.ttc'))
    if not fonts:
        raise FileNotFoundError('Existing Chinese system font not available')
    font = ImageFont.truetype(str(fonts[0]), 20, index=3)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    labels = ['1.参考视频', '2.原始 H3 编辑', '3.' + label]
    band = Image.new('RGB', (1968, 58), 'black')
    draw = ImageDraw.Draw(band)
    for i, text in enumerate(labels):
        draw.text(((i + .5)*656, 18), text, font=font, fill='white', anchor='mt')
    draw.text((16, 18), '角色替换', font=font, fill='white', anchor='lt')
    caption = destination.with_suffix('.caption.png')
    band.save(caption)
    filters = []
    for i in range(3):
        filters.append(f'[{i}:v]trim=start_frame={first}:end_frame={last},setpts=PTS-STARTPTS,'
            f'scale=656:368:flags=lanczos,setsar=1[v{i}]')
    filters.append('[v0][v1][v2]hstack=inputs=3[row]')
    filters.append(f'[3:v]trim=end_frame={last-first},setpts=PTS-STARTPTS[caption]')
    filters.append('[row][caption]vstack=inputs=2:shortest=1[out]')
    temporary = destination.with_name(destination.stem + '.partial.mp4')
    cmd = [FFMPEG, '-v', 'error', '-y', '-filter_complex_threads', '2']
    for path in paths:
        cmd += ['-i', str(path)]
    cmd += ['-loop', '1', '-framerate', '24', '-i', str(caption)]
    cmd += ['-filter_complex', ';'.join(filters), '-map', '[out]', '-an',
        '-c:v', 'libx264', '-threads', '2', '-preset', 'fast', '-crf', '18',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(temporary)]
    subprocess.run(cmd, check=True)
    out = probe(temporary)
    assert (out['width'], out['height'], int(out['nb_read_frames']), out['avg_frame_rate']) == (1968, 426, last-first, '24/1'), out
    temporary.replace(destination)
    record = dict(inputs=[dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest(), probe=d)
                          for p, d in zip(paths, info)],
                  output=str(destination), output_probe=out, labels=labels,
                  source_frame_interval_half_open=[first, last],
                  processing='Equal display scale, original frame correspondence, silent; no temporal warping or spatial cropping',
                  command=cmd)
    destination.with_suffix('.json').write_text(json.dumps(record, ensure_ascii=False, indent=2))
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('baseline')
    parser.add_argument('intervention')
    parser.add_argument('destination')
    parser.add_argument('--label', required=True)
    parser.add_argument('--first', type=int, default=0)
    parser.add_argument('--last', type=int, default=141)
    args = parser.parse_args()
    print(json.dumps(render(args.source, args.baseline, args.intervention, args.destination,
                            args.label, args.first, args.last), ensure_ascii=False))
