"""Monitor actual pair gates, prepare CPU inputs, then await root-owned trackers."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
ADMIN = Path(__file__).resolve().parent
REMOTE = '/data3/researcher/h3_runs/flexiact_expanded_evaluation_r66_20261018'
PRODUCER = '/data3/researcher/h3_runs/timing_flexiact_expanded_r66_20261018'
HOST = 'H3_SERVER_B'
PY = '/data3/researcher/ComfyUI/.venv/bin/python'
SSH = ['ssh', '-o', 'ConnectTimeout=10', HOST]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import PAIR_KEYS, METHODS


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p, value):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_suffix(p.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(p)


def jobs_complete(jobs):
    return len(jobs) == 2 and {x['method'] for x in jobs} == set(METHODS) and all(
        x['job'] == 'success' and x['history'].get('completed') is True
        and x['history'].get('status_str') == 'success' for x in jobs)


def snapshot():
    code = '''import json
from pathlib import Path
root=Path(REMOTE)
producer=Path(PRODUCER)
def read_live(p):
 try:return json.loads(p.read_text())
 except (FileNotFoundError,json.JSONDecodeError):return {}
rows=[]
for pair in PAIRS:
 gate=read_live(producer/'analysis/postrun'/pair/'PAIR_RUNTIME_GATE.json')
 jobs=[]
 for method in ['native','forced']:
  run='r66_'+pair+'_seed2026101701_'+method
  j=read_live(producer/'logs'/(run+'_job.json'));h=read_live(producer/'logs'/(run+'_history.json'))
  jobs.append({'method':method,'job':j.get('status'),'history':h.get('status',{})})
 tracks={method:(read_live(root/'tracks'/method/pair/'REPORT.json').get('passed') is True and (root/'tracks'/method/pair/'R66_BINDING.json').is_file()) for method in ['native','forced']}
 scores={method:(root/'scores'/method/pair/'SCORE.json').is_file() for method in ['native','forced']}
 rows.append({'pair':pair,'gate_passed':gate.get('passed'),'jobs':jobs,'tracks':tracks,'scores':scores,'collection':(root/'incoming'/pair/'COLLECTION.json').is_file(),'incoming_exists':(root/'incoming'/pair).exists(),'prepared':(root/'prepared'/pair/'READY.json').is_file(),'prepared_exists':(root/'prepared'/pair).exists(),'presentation':(root/'showcase'/(pair+'_PRESENTATION.json')).is_file(),'checkpoints':(root/'showcase'/(pair+'_fixed_checkpoints.json')).is_file()})
print(json.dumps(rows))
'''
    code = 'REMOTE=' + repr(REMOTE) + '\nPRODUCER=' + repr(PRODUCER) + '\nPAIRS=' + repr(list(PAIR_KEYS)) + '\n' + code
    p = subprocess.run(SSH + [shlex.join(['python3', '-c', code])], text=True, capture_output=True, timeout=35)
    if p.returncode:
        raise RuntimeError('Read-only snapshot failed: ' + p.stderr[-1200:])
    return json.loads(p.stdout)


def phase(pair, name, args):
    stamp = str(time.time_ns())
    log = ADMIN / 'logs' / (pair + '_' + name + '_' + stamp + '.log')
    env = ['env', 'CUDA_VISIBLE_DEVICES=', 'PYTHONDONTWRITEBYTECODE=1', 'OMP_NUM_THREADS=1', 'OPENBLAS_NUM_THREADS=1', 'MKL_NUM_THREADS=1', PY]
    started = time.monotonic()
    p = subprocess.run(SSH + [shlex.join(env + [REMOTE + '/audit/consumer_takeover/run_cpu_phase.py', name, *args])], text=True, capture_output=True, timeout=600)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(p.stdout + '\nSTDERR\n' + p.stderr)
    if p.returncode == 75:
        return False
    if p.returncode:
        raise RuntimeError(name + ' failed; see ' + str(log))
    save(ADMIN / 'receipts' / pair / (name + '_' + stamp + '.json'), {'phase': name, 'pair': pair, 'elapsed_wall_seconds': time.monotonic() - started, 'log': str(log), 'GPU_started': False})
    return True


def rsync(relative, local, json_only=False):
    local = Path(local)
    local.parent.mkdir(parents=True, exist_ok=True)
    cmd = ['rsync', '-a', '-e', 'ssh -o ConnectTimeout=10']
    if json_only:
        cmd += ['--include=*/', '--include=*.json', '--exclude=*']
        local.mkdir(parents=True, exist_ok=True)
    cmd += [HOST + ':' + REMOTE + '/' + relative, str(local)]
    subprocess.run(cmd, check=True, timeout=180)


def download_pair(pair):
    rsync('incoming/' + pair + '/', ROOT / 'incoming' / pair)
    collection = read(ROOT / 'incoming' / pair / 'COLLECTION.json')
    for name, digest in collection['files'].items():
        assert Path(name).name == name and sha(ROOT / 'incoming' / pair / name) == digest
    rsync('prepared/' + pair + '/', ROOT / 'prepared' / pair, json_only=True)
    for suffix in ['_full_valid.mp4', '_first2seconds.mp4', '_PRESENTATION.json']:
        rsync('showcase/' + pair + suffix, ROOT / 'showcase' / (pair + suffix))
    if pair.startswith('human2animal_'):
        for suffix in ['_fixed_checkpoints.jpg', '_fixed_checkpoints.json']:
            rsync('showcase/' + pair + suffix, ROOT / 'showcase' / (pair + suffix))
        fixed = read(ROOT / 'showcase' / (pair + '_fixed_checkpoints.json'))
        assert sha(ROOT / 'showcase' / (pair + '_fixed_checkpoints.jpg')) == fixed['figure_sha256']
    presentation = read(ROOT / 'showcase' / (pair + '_PRESENTATION.json'))
    for row in presentation['videos']:
        assert sha(ROOT / 'showcase' / Path(row['video']['file']).name) == row['video']['sha256']
    receipt = {'pair': pair, 'full_video': str(ROOT / 'showcase' / (pair + '_full_valid.mp4')), 'intake_sha256': sha(ROOT / 'incoming' / pair / 'COLLECTION.json'), 'presentation_sha256': sha(ROOT / 'showcase' / (pair + '_PRESENTATION.json')), 'PT_downloaded': False}
    save(ADMIN / 'receipts' / pair / 'LOCAL_MEDIA_READY.json', receipt)
    print(json.dumps(dict(receipt, event='PAIR_PREPARED_TARGET_TRACKERS_REQUIRED')), flush=True)


def gallery():
    videos = [ROOT / 'showcase' / (pair + '_full_valid.mp4') for pair in PAIR_KEYS if (ADMIN / 'receipts' / pair / 'LOCAL_MEDIA_READY.json').exists()]
    if not videos:
        return
    output = Path('/Users/researcher/Downloads/H3_R66_FlexiAct_扩充样例_完整对照_20261018.html')
    cmd = [sys.executable, str(ADMIN / 'make_target_showcase.py')]
    for video in videos:
        cmd += ['--video', str(video)]
    p = subprocess.run(cmd + ['--output', str(output)], check=True, capture_output=True, text=True, timeout=180)
    save(ADMIN / ('SHOWCASE_' + str(len(videos)).zfill(2) + '.json'), {'html': str(output), 'sha256': sha(output), 'full_valid_frames': 147, 'videos': [str(x) for x in videos]})
    print(json.dumps({'event': 'SHOWCASE_READY', 'html': str(output), 'pairs': len(videos)}), flush=True)


def scores_ready(pair):
    for method in METHODS:
        rsync('scores/' + method + '/' + pair + '/', ROOT / 'scores' / method / pair, json_only=True)
        rsync('tracks/' + method + '/' + pair + '/', ROOT / 'tracks' / method / pair, json_only=True)
    stamp = str(time.time_ns())
    relative = 'reports/MF_SUMMARY_' + stamp + '.json'
    if not phase(pair, 'summarize', ['--output', REMOTE + '/' + relative]):
        return False
    rsync(relative, ROOT / relative)
    rows = {method: read(ROOT / 'scores' / method / pair / 'SCORE.json') for method in METHODS}
    receipt = {'pair': pair, 'scores': {m: rows[m]['score'] for m in METHODS}, 'summary': str(ROOT / relative), 'GPU_started_by_consumer': False}
    save(ADMIN / 'receipts' / pair / 'SCORED.json', receipt)
    gallery()
    print(json.dumps(dict(receipt, event='PAIR_SCORED')), flush=True)
    return True


def main():
    while True:
        states = snapshot()
        for state in states:
            pair = state['pair']
            if state['gate_passed'] is not True:
                if state['gate_passed'] is False:
                    raise RuntimeError('Actual pair gate failed: ' + pair)
                if any(x['job'] in ('error', 'unknown_missing', 'submission_uncertain') or x['history'].get('status_str') == 'error' for x in state['jobs']):
                    raise RuntimeError('Actual producer job failure requires root review: ' + pair)
                if jobs_complete(state['jobs']):
                    phase(pair, 'verify_pair', ['--pair', pair])
                continue
            if not state['collection']:
                if state['incoming_exists']:
                    raise RuntimeError('Incomplete intake requires inspection: ' + pair)
                if not phase(pair, 'collect_pair', ['--producer-root', PRODUCER, '--pair', pair]):
                    continue
                state['collection'] = True
            if not state['prepared']:
                if state['prepared_exists']:
                    raise RuntimeError('Incomplete prepared directory requires inspection: ' + pair)
                if not phase(pair, 'prepare_pair', ['--pair', pair]):
                    continue
                state['prepared'] = True
                print(json.dumps({'event': 'TARGET_TRACK_INPUTS_READY', 'pair': pair, 'remote': REMOTE + '/prepared/' + pair}), flush=True)
            if not state['presentation']:
                if not phase(pair, 'make_triptych', ['--pair', pair]):
                    continue
                state['presentation'] = True
            if pair.startswith('human2animal_') and not state['checkpoints']:
                if not phase(pair, 'make_checkpoints', ['--pair', pair]):
                    continue
            if not (ADMIN / 'receipts' / pair / 'LOCAL_MEDIA_READY.json').exists():
                download_pair(pair)
                gallery()
            for method in METHODS:
                if state['tracks'][method] and not state['scores'][method]:
                    if phase(pair, 'score_one', ['--pair', pair, '--method', method]):
                        state['scores'][method] = True
            if all(state['scores'].values()) and not (ADMIN / 'receipts' / pair / 'SCORED.json').exists():
                scores_ready(pair)
        if all((ADMIN / 'receipts' / pair / 'SCORED.json').exists() for pair in PAIR_KEYS):
            print(json.dumps({'event': 'ALL_EIGHT_PAIRS_CPU_COMPLETE'}), flush=True)
            return
        time.sleep(30)


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        save(ADMIN / ('FAILURE_' + str(time.time_ns()) + '.json'), {'error': repr(error), 'traceback': traceback.format_exc(), 'GPU_started': False, 'automatic_retry': False})
        raise
