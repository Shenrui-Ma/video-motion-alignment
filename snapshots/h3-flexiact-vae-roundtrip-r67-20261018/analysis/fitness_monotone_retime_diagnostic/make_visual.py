"""Render every source timestamp against Native and the fixed post-hoc mapping."""
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
protocol = json.loads((ROOT / 'PROTOCOL.json').read_text())
result = json.loads((ROOT / 'RESULT.json').read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert result['protocol_sha256'] == sha(ROOT / 'PROTOCOL.json')
media = ROOT / 'visual'
media.mkdir(exist_ok=True)
for key in ['source_video', 'native_video']:
    entry = protocol['inputs'][key]
    assert sha(entry['file']) == entry['sha256']
    folder = media / key
    folder.mkdir(exist_ok=True)
    args = ['/opt/homebrew/bin/ffmpeg', '-v', 'error', '-y', '-i', entry['file']]
    if key == 'native_video':
        args += ['-vf', 'select=not(mod(n\\,3))*lte(n\\,144)']
    subprocess.run(args + ['-fps_mode', 'passthrough', '-start_number', '0', str(folder / '%03d.png')], check=True)
    assert len(list(folder.glob('*.png'))) == 49

font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 19)
font_small = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf', 15)
mapping = [x['native_index'] for x in result['mapping']]


def frame(i, width=576):
    height = width * 2 // 3
    caption = 50
    canvas = Image.new('RGB', (width * 3, height + caption), 'black')
    draw = ImageDraw.Draw(canvas)
    keys = ['source_video', 'native_video', 'native_video']
    indices = [i, i, mapping[i]]
    for col, (key, j) in enumerate(zip(keys, indices)):
        image = Image.open(media / key / f'{j:03d}.png').convert('RGB')
        assert image.size == (1152, 768)
        canvas.paste(image.resize((width, height), Image.Resampling.LANCZOS), (col * width, 0))
    for col, label in enumerate(['参考视频', '普通编辑', '普通编辑：统一时间重采样']):
        draw.text((col * width + width // 2, height + 14), label, font=font, fill='white', anchor='mm')
    draw.text((6, height + 31), f'{i/8:.3f} s', font=font_small, fill='white')
    note = f'取原编辑 {mapping[i]/8:.3f} s'
    if not result['mapping'][i]['fit_supported']:
        note += '；该对应缺双侧上臂观测'
    draw.text((2 * width + 6, height + 31), note, font=font_small, fill='white')
    return canvas


video = media / 'source_native_monotone_retime.mp4'
cmd = ['/opt/homebrew/bin/ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
       '-s', '1728x434', '-r', '8', '-i', 'pipe:0', '-an', '-frames:v', '49', '-c:v', 'libx264',
       '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(video)]
child = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
try:
    for i in range(49):
        child.stdin.write(frame(i).tobytes())
    child.stdin.close()
    error = child.stderr.read().decode()
    assert child.wait() == 0, error
finally:
    if child.poll() is None:
        child.kill()
        child.wait()
    if not child.stdin.closed:
        child.stdin.close()
    child.stderr.close()
for name, indices in [('six_times', [0, 4, 8, 12, 16, 20])] + [
        (f'all49_{i:02d}_{i+6:02d}', list(range(i, i + 7))) for i in range(0, 49, 7)]:
    images = [frame(i, width=384) for i in indices]
    canvas = Image.new('RGB', (images[0].width, images[0].height * len(images)), 'black')
    for n, image in enumerate(images):
        canvas.paste(image, (0, image.height * n))
    canvas.save(media / (name + '.png'))
with (ROOT / 'MAPPING.csv').open('w') as handle:
    writer = csv.DictWriter(handle, fieldnames=list(result['mapping'][0]))
    writer.writeheader()
    writer.writerows(result['mapping'])
probe = json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe', '-v', 'error', '-select_streams', 'v:0',
    '-count_frames', '-show_entries', 'stream=width,height,nb_read_frames,r_frame_rate', '-of', 'json', str(video)]))
stream = probe['streams'][0]
assert (stream['width'], stream['height'], stream['nb_read_frames'], stream['r_frame_rate']) == (1728, 434, '49', '8/1')
(media / 'BINDING.json').write_text(json.dumps({'result_sha256': sha(ROOT / 'RESULT.json'), 'video_sha256': sha(video),
    'probe': probe, 'source_video_sha256': protocol['inputs']['source_video']['sha256'],
    'native_video_sha256': protocol['inputs']['native_video']['sha256'], 'mapping': mapping,
    'source_time_s': [i / 8 for i in range(49)], 'whole_frame_nearest_sampling': True}, indent=2) + '\n')
print(video)
