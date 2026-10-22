"""Source-only inspection. Fixed five official files; no model, tracker, or generation."""
import concurrent.futures
import hashlib
import io
import json
from pathlib import Path
import subprocess
import time
import urllib.request
from PIL import Image, ImageDraw

B = Path(__file__).resolve().parent
REVISION = '1e6cb655c0a537f6093edcf18e2607fb03e76734'

def save(name, obj):
    (B / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def download(item):
    name = Path(item['path']).name
    dest = B / 'candidate_sources' / name
    url = f'https://huggingface.co/datasets/Coraxor/IVEBench/resolve/{REVISION}/{item["path"]}'
    start = time.monotonic()
    if dest.exists():
        raw = dest.read_bytes()
        headers = {}
    else:
        with urllib.request.urlopen(url, timeout=60) as response:
            raw = response.read(item['size'] + 1)
            headers = dict(response.headers)
        assert len(raw) == item['size'], (name, len(raw), item['size'])
        assert hashlib.sha256(raw).hexdigest() == item['lfs']['oid'], name
        dest.write_bytes(raw)
    assert len(raw) == item['size']
    assert hashlib.sha256(raw).hexdigest() == item['lfs']['oid']
    return {'file': str(dest), 'url': url, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'headers': headers, 'elapsed_s': time.monotonic() - start}

def inspect(record):
    path = Path(record['file'])
    probe = json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe', '-v', 'error', '-show_streams', '-show_frames', '-select_streams', 'v:0', '-show_entries', 'stream=codec_type,width,height,nb_frames,avg_frame_rate,r_frame_rate,duration:frame=best_effort_timestamp_time', '-of', 'json', str(path)], timeout=30))
    stream = probe['streams'][0]
    pts = [float(x['best_effort_timestamp_time']) for x in probe['frames']]
    assert len(pts) > 1 and all(b > a for a, b in zip(pts, pts[1:]))
    indices = sorted({round(i * (len(pts) - 1) / 11) for i in range(12)})
    sheet = Image.new('RGB', (1600, 3 * 250), '#111111')
    draw = ImageDraw.Draw(sheet)
    for j, index in enumerate(indices):
        raw = subprocess.check_output(['/opt/homebrew/bin/ffmpeg', '-v', 'error', '-threads', '2', '-i', str(path), '-vf', f'select=eq(n\\,{index}),scale=400:225:force_original_aspect_ratio=decrease', '-frames:v', '1', '-f', 'image2pipe', '-c:v', 'png', '-threads', '1', 'pipe:1'], timeout=30)
        image = Image.open(io.BytesIO(raw))
        x, y = (j % 4) * 400, (j // 4) * 250
        sheet.paste(image, (x + (400 - image.width) // 2, y + 25))
        draw.text((x + 5, y + 5), f'{path.stem} | {index} | {pts[index]:.3f}s', fill='white')
    out = B / 'source_review' / (path.stem + '.jpg')
    sheet.save(out, quality=93)
    return {**stream, 'file': str(path), 'sha256': record['sha256'], 'pts_s': pts, 'decoded_frames': len(pts), 'contact_sheet_indices': indices, 'contact_sheet': str(out), 'contact_sheet_sha256': hashlib.sha256(out.read_bytes()).hexdigest(), 'review_protocol': '12 uniformly indexed source frames; full image with aspect preserved; no H3 output'}

if __name__ == '__main__':
    permission = json.loads((B / 'SCOPE_DECISION.json').read_text())
    assert permission['allow_source_only_general_editing_review'] is True
    items = json.loads((B / 'OFFICIAL_LFS_INFO.json').read_text())
    proposed = json.loads((B / 'PROPOSED_SOURCE_ONLY_FIVE.json').read_text())
    assert len(items) == 5
    assert {Path(x['path']).name for x in items} == {x['src_video_name'] for x in proposed['pairs']}
    for folder in ['candidate_sources', 'source_review']:
        (B / folder).mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(download, items))
    save('DOWNLOAD_RECEIPTS.json', receipts)
    probes = [inspect(x) for x in receipts]
    save('SOURCE_TIMEBASE.json', probes)
    print([(Path(x['file']).name, x['width'], x['height'], x['decoded_frames'], x['pts_s'][-1]) for x in probes])
