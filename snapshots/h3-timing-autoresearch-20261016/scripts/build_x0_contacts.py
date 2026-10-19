#!/usr/bin/env python3
"""Build unaligned, uncropped six-panel diagnostic sheets from existing videos."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT = 656, 368
CAPTION, GAP, MARGIN = 60, 8, 8
VIDEO_FRAMES = (55, 64, 83)
FONT = Path('/System/Library/Fonts/Supplemental/Arial.ttf')
BOLD = Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf')


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def probe(path: Path, ffprobe: str) -> dict:
    result = subprocess.run(
        [ffprobe, '-v', 'error', '-select_streams', 'v:0', '-show_entries',
         'stream=width,height,nb_frames,r_frame_rate,avg_frame_rate,duration',
         '-of', 'json', str(path)], check=True, capture_output=True, text=True,
    )
    streams = json.loads(result.stdout)['streams']
    if len(streams) != 1:
        raise ValueError(f'Expected one selected video stream: {path}')
    info = streams[0]
    if (info['width'], info['height']) != (1312, 736):
        raise ValueError(f'Unexpected geometry; refusing to crop or distort: {path}: {info}')
    if Fraction(info['avg_frame_rate']) != 24 or Fraction(info['r_frame_rate']) != 24:
        raise ValueError(f'Expected constant 24 fps: {path}: {info}')
    if int(info['nb_frames']) <= max(VIDEO_FRAMES):
        raise ValueError(f'Insufficient source frames: {path}: {info}')
    return info


def extract(path: Path, frame: int, ffmpeg: str) -> tuple[Image.Image, list[str]]:
    # n is the original decoded video's zero-based frame index. No seeking,
    # interpolation, temporal alignment, cropping, or filtering beyond resize.
    command = [
        ffmpeg, '-v', 'error', '-i', str(path), '-map', '0:v:0',
        '-vf', f'select=eq(n\\,{frame}),scale={WIDTH}:{HEIGHT}:flags=lanczos',
        '-fps_mode', 'passthrough', '-frames:v', '1', '-an', '-sn',
        '-f', 'image2pipe', '-vcodec', 'png', '-pix_fmt', 'rgb24', '-',
    ]
    result = subprocess.run(command, check=True, capture_output=True)
    image = Image.open(io.BytesIO(result.stdout)).convert('RGB')
    image.load()
    if image.size != (WIDTH, HEIGHT):
        raise ValueError(f'Unexpected extracted size: {image.size}')
    return image, command


def build(root: Path, output: Path, ffmpeg: str, ffprobe: str) -> Path:
    decoded = root / 'outputs/x0_decoded/s05_full_seed1_native_x0'
    definitions = [
        ('source', 'Original reference', None, root / 'inputs/05_real_megumi_v.mp4'),
        ('sampler_final', 'Sampler final', None, decoded / 'sampler_final.mp4'),
        ('x0_step005', 'x0 estimate | denoising step 005 (zero-based)', 5, decoded / 'x0_step005.mp4'),
        ('x0_step010', 'x0 estimate | denoising step 010 (zero-based)', 10, decoded / 'x0_step010.mp4'),
        ('x0_step015', 'x0 estimate | denoising step 015 (zero-based)', 15, decoded / 'x0_step015.mp4'),
        ('x0_step019', 'x0 estimate | denoising step 019 (zero-based)', 19, decoded / 'x0_step019.mp4'),
    ]
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite existing review directory: {output}')
    inputs = []
    for key, label, step, path in definitions:
        inputs.append({
            'key': key, 'label': label, 'denoising_step_zero_based': step,
            'path': str(path.resolve()), 'sha256': sha256(path),
            'ffprobe': probe(path, ffprobe),
        })
    font = ImageFont.truetype(str(FONT), 18)
    bold = ImageFont.truetype(str(BOLD), 20)
    sheet_size = (3 * WIDTH + 2 * GAP + 2 * MARGIN,
                  2 * (HEIGHT + CAPTION) + GAP + 2 * MARGIN)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'script_path': str(Path(__file__).resolve()), 'script_sha256': sha256(Path(__file__)),
        'input_sources': inputs, 'video_frame_index_convention': 'zero-based decoded source frame index',
        'denoising_step_convention': 'zero-based sampler step, not a video frame number',
        'selection': list(VIDEO_FRAMES), 'layout': {
            'columns': 3, 'rows': 2, 'row_major_order': [item['key'] for item in inputs],
            'cell_video_size': [WIDTH, HEIGHT], 'caption_height': CAPTION,
            'margin': MARGIN, 'gap': GAP, 'sheet_size': list(sheet_size), 'background': 'black',
        },
        'processing': {
            'spatial_resize': '1312x736 to 656x368, exactly 0.5 scale, FFmpeg lanczos',
            'cropping': False, 'temporal_alignment': False, 'interpolation': False,
            'generative_edits': False, 'original_files_modified': False,
            'font_paths': [str(FONT), str(BOLD)],
            'ffmpeg_version': subprocess.check_output([ffmpeg, '-version'], text=True).splitlines()[0],
        }, 'sheets': [],
    }
    for frame in VIDEO_FRAMES:
        sheet = Image.new('RGB', sheet_size, 'black')
        draw = ImageDraw.Draw(sheet)
        panels = []
        for index, source in enumerate(inputs):
            image, command = extract(Path(source['path']), frame, ffmpeg)
            col, row = index % 3, index // 3
            x, y = MARGIN + col * (WIDTH + GAP), MARGIN + row * (HEIGHT + CAPTION + GAP)
            sheet.paste(image, (x, y))
            label = source['label']
            second = f'Video source frame {frame:03d} (zero-based) | t = {frame / 24:.3f} s'
            for text, face in ((label, bold), (second, font)):
                if draw.textlength(text, font=face) > WIDTH - 12:
                    raise ValueError(f'Caption exceeds panel width: {text}')
            draw.text((x + 6, y + HEIGHT + 6), label, font=bold, fill='white')
            draw.text((x + 6, y + HEIGHT + 33), second, font=font, fill=(210, 210, 210))
            panels.append({
                'panel_index_row_major': index, 'key': source['key'],
                'source_path': source['path'], 'source_sha256': source['sha256'],
                'video_frame_zero_based': frame, 'timestamp_seconds': frame / 24,
                'denoising_step_zero_based': source['denoising_step_zero_based'],
                'caption': [label, second], 'video_rectangle_xywh': [x, y, WIDTH, HEIGHT],
                'extracted_rgb_sha256': hashlib.sha256(image.tobytes()).hexdigest(),
                'extraction_command': command,
            })
        path = output / f'native_x0_video_frame_{frame:03d}.png'
        with path.open('xb') as stream:
            sheet.save(stream, format='PNG')
        # Verify serialized pixels, including each panel, before recording completion.
        reread = Image.open(path).convert('RGB')
        for panel in panels:
            x, y, w, h = panel['video_rectangle_xywh']
            pixels = reread.crop((x, y, x + w, y + h)).tobytes()
            if hashlib.sha256(pixels).hexdigest() != panel['extracted_rgb_sha256']:
                raise RuntimeError('Contact-sheet panel pixel verification failed')
        manifest['sheets'].append({
            'path': str(path), 'sha256': sha256(path), 'size': list(reread.size),
            'video_frame_zero_based': frame, 'panels': panels,
            'serialized_panel_rgb_hashes_verified': True,
        })
    target = output / 'manifest.json'
    with target.open('x') as stream:
        json.dump(manifest, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--ffmpeg', default='/opt/homebrew/bin/ffmpeg')
    parser.add_argument('--ffprobe', default='/opt/homebrew/bin/ffprobe')
    args = parser.parse_args()
    root = args.root.resolve()
    print(build(root, (args.output or root / 'review/x0_native').resolve(), args.ffmpeg, args.ffprobe))
