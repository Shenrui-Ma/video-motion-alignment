"""Render seven verified videos with identical crop/frame index; CPU-only.

Run with bundled Python (Pillow) and ffmpeg. Bindings file schema is documented
in README.md. This script writes only its explicit output directory.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROLES = ['source', 'native', 'early', 'fixed', 'late', 'split', 'global_weak']
LABELS = ['参考视频', '普通编辑', '1–9 步引导', '7–15 步引导', '12–20 步引导', '1–4＋16–20 步引导', '全程弱引导 α=0.25']


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def probe(ffprobe, path):
    return json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-select_streams', 'v:0', '-count_frames', '-show_entries', 'stream=width,height,nb_read_frames,r_frame_rate', '-of', 'json', str(path)], text=True))['streams'][0]


def render(bindings, output, ffmpeg='ffmpeg', ffprobe='ffprobe', font_path=None):
    b = json.loads(bindings.read_text())
    assert b['case_id'] == 'short_0177' and b['cohort'] == 'interval_short0177_20261024'
    assert b['valid_frames'] == 60 and b['fps'] == 24 and b['crop_xywh'] == [16, 8, 1280, 720]
    assert set(b['videos']) == set(ROLES)
    output.mkdir(parents=True, exist_ok=True)
    dirs = {}
    for role in ROLES:
        r = b['videos'][role]
        path = Path(r['file']); path = path if path.is_absolute() else bindings.parent / path
        assert sha(path) == r['sha256'], (role, 'SHA')
        info = probe(ffprobe, path)
        num, den = map(int, info['r_frame_rate'].split('/'))
        assert num / den == 24 and int(info['nb_read_frames']) >= 60, (role, info)
        assert info['width'] >= 1296 and info['height'] >= 728, (role, info)
        folder = output / 'frames' / role; folder.mkdir(parents=True, exist_ok=True); dirs[role] = folder
        subprocess.run([ffmpeg, '-v', 'error', '-y', '-threads', '2', '-i', str(path), '-vf', 'crop=1280:720:16:8,trim=end_frame=60,setpts=PTS-STARTPTS', '-fps_mode', 'passthrough', '-frames:v', '60', '-start_number', '0', str(folder / '%06d.png')], check=True)
        assert len(list(folder.glob('*.png'))) == 60, role
    if font_path is None:
        font_path = next(str(p) for p in [Path('/System/Library/Fonts/PingFang.ttc'), Path('/System/Library/Fonts/STHeiti Light.ttc'), Path('/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc')] if p.exists())
    font = ImageFont.truetype(font_path, 22)
    target = output / 'comparison.mp4'
    command = [ffmpeg, '-v', 'error', '-y', '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', '1920x1232', '-framerate', '24', '-i', '-', '-an', '-c:v', 'libx264', '-threads', '2', '-preset', 'fast', '-crf', '19', '-pix_fmt', 'yuv420p', str(target)]
    proc = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        for frame in range(60):
            canvas = Image.new('RGB', (1920, 1232), 'black')
            strip = Image.new('RGB', (4480, 384), 'black') if frame == 30 else None
            for i, role in enumerate(ROLES):
                image = Image.open(dirs[role] / f'{frame:06d}.png').convert('RGB')
                image.thumbnail((640, 360), Image.Resampling.LANCZOS)
                panel = Image.new('RGB', (640, 384), 'black')
                panel.paste(image, ((640 - image.width) // 2, (360 - image.height) // 2))
                ImageDraw.Draw(panel).text((320, 372), LABELS[i], font=font, fill='white', anchor='mm')
                xy = (640, 0) if i == 0 else (((i-1) % 3) * 640, 384 if i <= 3 else 768)
                canvas.paste(panel, xy)
                if strip is not None: strip.paste(panel, (i * 640, 0))
            if strip is not None: strip.save(output / 'same_frame.jpg', quality=92)
            proc.stdin.write(canvas.tobytes())
        proc.stdin.close()
        assert proc.wait() == 0, 'ffmpeg failed'
    except BaseException:
        proc.kill(); proc.wait(); raise
    info = probe(ffprobe, target)
    assert int(info['nb_read_frames']) == 60
    record = dict(task_id='short_0177', cohort=b['cohort'], roles=ROLES, valid_frames=60, fps=24, width=1920, height=1232,
        caption_height=24, bottom_controls_padding=80, screenshot_frame=30,
        screenshot_selection='统一有效时长中点，同帧编号和裁剪', full_decode_frames=60,
        crop_xywh=b['crop_xywh'], inputs={r: {'job': b['videos'][r]['job_id'], 'sha256': b['videos'][r]['sha256']} for r in ROLES},
        files={p.name: sha(p) for p in [target, output / 'same_frame.jpg']})
    (output / 'PRESENTATION.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--bindings', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--ffmpeg', default='ffmpeg'); p.add_argument('--ffprobe', default='ffprobe'); p.add_argument('--font')
    a = p.parse_args(); render(a.bindings, a.output, a.ffmpeg, a.ffprobe, a.font)
