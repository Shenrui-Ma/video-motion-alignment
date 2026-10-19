"""Six equally spaced fixed frames from each released, effective-prefix pair."""
from pathlib import Path
import fcntl
import hashlib
import io
import json
import shutil
import subprocess
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
POST = HERE.parent
REMOTE = Path('/data3/researcher/h3_runs/timing_ivebench_native_r54_20261017/analysis/postrun')
OUTPUT = HERE / 'fixed_native_review'
FFMPEG = shutil.which('ffmpeg')
FONT = '/System/Library/Fonts/PingFang.ttc'
if not Path(FONT).exists():
    FONT = '/System/Library/Fonts/STHeiti Light.ttc'
font = ImageFont.truetype(FONT, 21)
small = ImageFont.truetype(FONT, 16)

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def save(p, d):
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')

with Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    manifest_path = POST / 'captured/batch/batch_summary/METRIC_MANIFEST.json'
    manifest = json.loads(manifest_path.read_text())
    assert sha(manifest_path) == '9caa76699d1ea59a342c73aeb428ade23d3a7ea07ddd499423cf9d6fd6088e60'
    plan = []
    for pair in manifest['pairs']:
        n = len(pair['score_frame_indices'])
        plan.append({'pair_id': pair['pair_id'], 'effective_frames': n,
                     'fixed_indices': [round(i * (n - 1) / 5) for i in range(6)],
                     'source': pair['source_score_video'], 'native': pair['edited']['native']['score_video']})
    OUTPUT.mkdir(exist_ok=False)
    save(OUTPUT / 'FIXED_PLAN.json', {'manifest_sha256': sha(manifest_path), 'selection': 'six equally spaced valid-prefix frames including first/last',
                                    'display_size_per_video': [640, 360], 'frame_rate': 24, 'cases': plan})
    for case in plan:
        dest = OUTPUT / case['pair_id']
        dest.mkdir()
        arrays = {}
        for role in ['source', 'native']:
            item = case[role]
            video = POST / Path(item['file']).relative_to(REMOTE)
            assert sha(video) == item['sha256']
            selection = '+'.join('eq(n\\,%d)' % index for index in case['fixed_indices'])
            command = [FFMPEG, '-v', 'error', '-threads', '2', '-i', str(video), '-vf',
                       "select='" + selection + "',scale=640:360:flags=lanczos,setsar=1", '-filter_threads', '1',
                       '-fps_mode', 'passthrough', '-frames:v', '6', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1']
            raw = subprocess.check_output(command, timeout=90)
            assert len(raw) == 6 * 640 * 360 * 3
            arrays[role] = [Image.frombytes('RGB', (640, 360), raw[i*640*360*3:(i+1)*640*360*3]) for i in range(6)]
        pages = []
        for i, frame in enumerate(case['fixed_indices']):
            image = Image.new('RGB', (1280, 404), 'black')
            image.paste(arrays['source'][i], (0, 0))
            image.paste(arrays['native'][i], (640, 0))
            draw = ImageDraw.Draw(image)
            draw.text((320, 381), '1. 参考视频', font=font, fill='white', anchor='mm')
            draw.text((960, 381), '2. 普通编辑', font=font, fill='white', anchor='mm')
            draw.text((12, 382), f'{frame:03d} | {frame / 24:.3f}s', font=small, fill='#b6bdc8', anchor='lm')
            image.save(dest / f'frame{frame:03d}.png')
            pages.append(image)
        sheet = Image.new('RGB', (1280, 404 * 6), 'black')
        for i, image in enumerate(pages):
            sheet.paste(image, (0, i * 404))
        sheet.save(dest / 'contact_sheet.png')
    inventory = {str(p.relative_to(OUTPUT)): sha(p) for p in sorted(OUTPUT.rglob('*')) if p.is_file()}
    save(OUTPUT / 'FILE_INVENTORY.json', inventory)
    print(json.dumps({'cases': len(plan), 'comparison_frames': len(plan) * 6, 'files': len(inventory),
                      'inventory_sha256': sha(OUTPUT / 'FILE_INVENTORY.json')}))
