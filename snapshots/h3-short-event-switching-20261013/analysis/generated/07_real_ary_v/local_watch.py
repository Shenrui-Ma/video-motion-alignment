import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path('/Users/researcher/DevProjects/h3-short-event-switching-20261013')
CASE = ROOT / 'analysis/generated/07_real_ary_v'
DEADLINE = datetime.fromisoformat('2026-10-13T12:35:01+00:00').timestamp()
RUNS = [f'07_real_ary_v_{arm}_s{seed}' for seed in (1, 2) for arm in ('a', 'b')]
STOP = False


def now():
    return datetime.now(timezone.utc).isoformat()


def save(name, data):
    target = CASE / name
    temporary = target.with_suffix(target.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(target)


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def stop_handler(signum, frame):
    global STOP
    STOP = True


def render(path, label):
    folder = CASE / label
    folder.mkdir(exist_ok=True)
    frames = folder / 'frames'
    frames.mkdir(exist_ok=True)
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                            '-show_streams', '-show_format', '-of', 'json', str(path)],
                           check=True, capture_output=True, text=True)
    info = json.loads(probe.stdout)
    video = info['streams'][0]
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(path), '-fps_mode', 'passthrough',
                    '-q:v', '2', str(frames / 'f%04d.jpg')], check=True)
    files = sorted(frames.glob('f*.jpg'))
    pages = []
    for start in range(0, len(files), 24):
        canvas = Image.new('RGB', (1920, 294 * 6), 'white')
        draw = ImageDraw.Draw(canvas)
        for j, fp in enumerate(files[start:start + 24]):
            with Image.open(fp) as original:
                im = original.convert('RGB').resize((480, 269))
            x, y = (j % 4) * 480, (j // 4) * 294
            canvas.paste(im, (x, y))
            draw.text((x + 5, y + 272), f'{label} | f{start+j:03d} | {(start+j)/24:.4f}s', fill='black')
        page = folder / f'allframes_p{start//24+1}.jpg'
        canvas.save(page, quality=95)
        pages.append(str(page))
    details = []
    for start in (42, 54, 66):
        canvas = Image.new('RGB', (640 * 3, 504 * 4), 'white')
        draw = ImageDraw.Draw(canvas)
        for j, fp in enumerate(files[start:start + 12]):
            with Image.open(fp) as original:
                im = original.convert('RGB').crop((400, 0, 1040, 480))
            x, y = (j % 3) * 640, (j // 3) * 504
            canvas.paste(im, (x, y))
            draw.text((x + 5, y + 483), f'{label} | f{start+j:03d} | {(start+j)/24:.4f}s', fill='black')
        page = folder / f'face_detail_f{start:03d}_{start+11:03d}.jpg'
        canvas.save(page, quality=95)
        details.append(str(page))
    record = {'source_file': str(path), 'sha256': sha(path), 'probe': info,
              'decoded_frames': len(files), 'expected_media_match': len(files) == 141 and
              video.get('r_frame_rate') == '24/1' and video.get('width') == 1312 and
              video.get('height') == 736, 'all_frame_pages': pages, 'detail_pages': details,
              'rendered_at_utc': now(), 'visual_review_performed_by_renderer': False}
    save(f'{label}/evidence_manifest.json', record)
    return record


def admission(run):
    hp = ROOT / 'logs' / f'{run}_history.json'
    if not hp.exists():
        return {'state': 'waiting_for_history'}
    try:
        h = json.loads(hp.read_text())
    except (OSError, json.JSONDecodeError):
        return {'state': 'history_not_readable_yet'}
    status = h.get('status', {})
    events = [x[0] for x in status.get('messages', []) if isinstance(x, list) and x]
    if status.get('status_str') != 'success' or status.get('completed') is not True or 'execution_success' not in events:
        return {'state': 'history_not_success', 'status_str': status.get('status_str'), 'events': events}
    prompt = h.get('prompt', [])
    graph = prompt[2] if isinstance(prompt, list) and len(prompt) > 2 and isinstance(prompt[2], dict) else {}
    node = graph.get('14', {})
    if node.get('class_type') != 'SaveVideo' or node.get('inputs', {}).get('filename_prefix') != run:
        return {'state': 'save_video_14_identity_mismatch'}
    files = h.get('outputs', {}).get('14', {}).get('images', [])
    candidates = [x for x in files if x.get('type') == 'output' and
                  x.get('filename', '').startswith(run + '_') and
                  x.get('filename', '').endswith('.mp4') and 'benchmark' not in x.get('filename', '')]
    if len(candidates) != 1:
        return {'state': 'formal_output_not_unique', 'candidate_count': len(candidates)}
    item = candidates[0]
    mp4 = ROOT / 'outputs' / item['filename']
    if not mp4.exists() or mp4.stat().st_size == 0:
        return {'state': 'successful_history_waiting_for_local_mp4', 'filename': item['filename']}
    stat = mp4.stat()
    if time.time() - stat.st_mtime < 20:
        return {'state': 'waiting_for_mp4_write_to_settle', 'filename': item['filename']}
    return {'state': 'admitted', 'history_file': str(hp), 'history_sha256': sha(hp),
            'history_status': status, 'save_video_14': node, 'save_video_14_output': item,
            'mp4': str(mp4), 'mp4_sha256': sha(mp4), 'accepted_at_utc': now()}


CASE.mkdir(parents=True, exist_ok=True)
registration = {'pid': os.getpid(), 'started_at_utc': now(), 'command': [sys.executable, str(Path(__file__).resolve())],
                'deadline_utc': datetime.fromtimestamp(DEADLINE, timezone.utc).isoformat(),
                'poll_seconds': 30, 'scope': 'local CPU reads of case history/output; writes only this case directory',
                'exit_conditions': ['all four formal outputs admitted and CPU evidence rendered', 'deadline', 'SIGTERM/SIGINT', 'STOP file'],
                'state': 'running'}
save('watcher_registration.json', registration)
signal.signal(signal.SIGTERM, stop_handler)
signal.signal(signal.SIGINT, stop_handler)
print(json.dumps({'watcher_started': registration}, ensure_ascii=False), flush=True)
ready = {}
states = {}
last_summary = None
try:
    for label, path in [('SOURCE', ROOT / 'inputs/07_real_ary_v.mp4'),
                        ('VAE', ROOT / 'outputs/07_real_ary_v_reference_vae_reconstruction_00001_.mp4')]:
        manifest = CASE / label / 'evidence_manifest.json'
        if not manifest.exists():
            render(path, label)
    while time.time() < DEADLINE and not STOP and not (CASE / 'STOP').exists():
        for run in RUNS:
            if run in ready:
                continue
            result = admission(run)
            states[run] = result
            if result['state'] == 'admitted':
                label = run.removeprefix('07_real_ary_v_').upper()
                try:
                    evidence = render(Path(result['mp4']), label)
                    ready[run] = {'admission': result, 'evidence': evidence}
                    print(json.dumps({'ready_for_independent_visual_review': run, 'manifest': str(CASE / label / 'evidence_manifest.json')}, ensure_ascii=False), flush=True)
                except Exception as exc:
                    states[run] = {'state': 'cpu_evidence_render_error', 'error': repr(exc)}
        snapshot = {'updated_at_utc': now(), 'deadline_utc': registration['deadline_utc'],
                    'ready': ready, 'pending': {k: v for k, v in states.items() if k not in ready}}
        save('watch_status.json', snapshot)
        summary = {k: v['state'] for k, v in states.items()}
        if summary != last_summary:
            print(json.dumps({'status_change': summary, 'ready_count': len(ready)}, ensure_ascii=False), flush=True)
            last_summary = summary
        if len(ready) == 4:
            break
        for _ in range(30):
            if STOP or (CASE / 'STOP').exists() or time.time() >= DEADLINE:
                break
            time.sleep(1)
finally:
    registration.update({'state': 'exited', 'exited_at_utc': now(), 'ready_count': len(ready),
                         'reason': 'all_four_rendered' if len(ready) == 4 else 'deadline_or_stop'})
    save('watcher_registration.json', registration)
    print(json.dumps({'watcher_exited': registration}, ensure_ascii=False), flush=True)
