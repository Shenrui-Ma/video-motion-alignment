"""Render completed same-frame valid-prefix comparisons with a Chinese caption band."""
import argparse
import io
import subprocess
from PIL import Image, ImageDraw, ImageFont
from common import *
from bindings import official

LABELS = ('1.参考视频', '2.编辑后视频', '3.编辑＋时序引导后视频')

def choose_font(requested=None):
    choices = [Path(requested)] if requested else [Path('/System/Library/Fonts/STHeiti Light.ttc'), Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
    font = next((path for path in choices if path.is_file()), None)
    require(font is not None, 'provide existing Chinese font with --font')
    return font

def caption_strip(font):
    image = Image.new('RGB', (3840, 88), 'black'); draw = ImageDraw.Draw(image)
    large = ImageFont.truetype(str(font), 32); small = ImageFont.truetype(str(font), 22)
    draw.text((14, 9), '视频编辑', font=small, fill='white')
    for column, label in enumerate(LABELS):
        draw.text((column * 1280 + (1280 - draw.textlength(label, font=large)) / 2, 42), label, font=large, fill='white')
    return image

def render(source, ffmpeg, ffprobe, font):
    ready = ROOT / 'prepared' / source / 'READY.json'; require(read(ready)['passed'] is True, 'actual prepared pair is pending')
    manifest = ROOT / 'prepared' / source / 'METRIC_INPUTS.json'
    require(read(ready)['metric_inputs']['sha256'] == sha(manifest), 'prepared manifest changed')
    row = read(manifest)
    paths = [Path(row['source_score_video']['file'])] + [Path(row['edited'][method]['score_video']['file']) for method in METHODS]
    # Relocation is permitted only for files with the exact prepared SHA.
    paths = [ROOT / 'prepared' / source / (name + '_score.mp4') for name in ('source',) + METHODS]
    expected = [row['source_score_video']] + [row['edited'][method]['score_video'] for method in METHODS]
    for path, binding in zip(paths, expected):
        require(sha(path) == binding['sha256'], 'presentation video changed')
    count = entry(source)['input_protocol']['effective_frame_count']
    for path in paths:
        official.validate_time_view(official.media_info(path, ffprobe), count)
    output = ROOT / 'showcase' / source; output.mkdir(parents=True, exist_ok=False)
    caption = output / 'caption.png'; caption_strip(font).save(caption)
    videos = []
    for name, length in [('full_valid', count), ('first2seconds', min(count, 48))]:
        dest = output / (name + '.mp4'); command = [ffmpeg, '-v', 'error', '-nostdin', '-n']
        for path in paths:
            command += ['-threads', '2', '-i', str(path)]
        command += ['-framerate', '24', '-loop', '1', '-i', str(caption)]
        filters = [f'[{i}:v]trim=end_frame={length},setpts=PTS-STARTPTS,setsar=1[v{i}]' for i in range(3)] + ['[v0][v1][v2]hstack=inputs=3:shortest=1[images]', '[images][3:v]vstack=inputs=2:shortest=1[out]']
        command += ['-filter_complex', ';'.join(filters), '-map', '[out]', '-frames:v', str(length), '-an', '-vsync', '0', '-c:v', 'libx264', '-crf', '17', '-bf', '0', '-preset', 'fast', '-pix_fmt', 'yuv420p', '-threads', '2', '-movflags', '+faststart', str(dest)]
        subprocess.run(command, check=True, timeout=300)
        info = official.media_info(dest, ffprobe)
        require((info['width'], info['height'], info['count']) == (3840, 808, length) and all(abs(t - i / 24) <= 1e-6 for i, t in enumerate(info['pts_s'])), 'rendered timeline/shape differs')
        videos.append({'name': name, 'video': bound(dest), 'physical_frame_range': [0, length - 1], 'fps': 24})
    frames = [round(i * (count - 1) / 5) for i in range(6)]
    canvas = Image.new('RGB', (1920, 408 * 6), 'black'); draw = ImageDraw.Draw(canvas); small = ImageFont.truetype(str(font), 18)
    for row_index, frame in enumerate(frames):
        for column, path in enumerate(paths):
            data = subprocess.check_output([ffmpeg, '-v', 'error', '-threads', '1', '-i', str(path), '-vf', f'select=eq(n\\,{frame}),scale=640:360:flags=lanczos', '-frames:v', '1', '-threads', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'], timeout=90)
            canvas.paste(Image.open(io.BytesIO(data)).convert('RGB'), (column * 640, row_index * 408))
            label = LABELS[column]; draw.text((column * 640 + (640 - draw.textlength(label, font=small)) / 2, row_index * 408 + 374), label, font=small, fill='white')
        draw.text((6, row_index * 408 + 362), f'{frame / 24:.3f}s', font=ImageFont.truetype(str(font), 13), fill='#bcbcbc')
    figure = output / 'six_times.png'; canvas.save(figure)
    save(output / 'PRESENTATION.json', {'source': source, 'gate': bound(ROOT / 'incoming' / source / 'PAIR_RUNTIME_GATE.json'), 'prepared': bound(manifest), 'videos': videos, 'figure': bound(figure), 'figure_frame_indices': frames, 'figure_selection': 'six uniform times over the frozen valid source prefix', 'fixed_denominator': 7})
    return output

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--source', choices=PAIRS, required=True); p.add_argument('--font'); p.add_argument('--ffmpeg', default='ffmpeg'); p.add_argument('--ffprobe', default='ffprobe')
    a = p.parse_args(); verify_runtime()
    with cpu_lock():
        print(render(a.source, a.ffmpeg, a.ffprobe, choose_font(a.font)))
