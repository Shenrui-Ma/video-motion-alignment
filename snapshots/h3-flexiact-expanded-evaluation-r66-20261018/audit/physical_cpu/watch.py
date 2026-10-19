"""CPU-only .9 consumption of actual R66 pairs after their local intake is ready."""
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
ADMIN = Path(__file__).resolve().parent
REMOTE = '/data5/researcher/h3_runs/flexiact_expanded_evaluation_r66_20261018'
SSH_COMMAND = 'ssh -J H3_SERVER_B -o ConnectTimeout=10'
SSH = shlex.split(SSH_COMMAND) + ['H3_SERVER_A']
PY = '/home/researcher/miniconda3/envs/comfyui/bin/python'
sys.path.insert(0, str(ROOT / 'scripts'))
from common import PAIR_KEYS, bound, read, save, sha


def remote_state(pair):
    code = 'from pathlib import Path;import json;r=Path(' + repr(REMOTE) + ');p=' + repr(pair) + ';print(json.dumps({"native":(r/"poses"/p/"native/COMPLETE.json").is_file(),"forced":(r/"poses"/p/"forced/COMPLETE.json").is_file(),"score":(r/"scores/physical"/(p+".json")).is_file()}))'
    result = subprocess.run(SSH + [shlex.join(['python3', '-c', code])], check=True, capture_output=True, text=True, timeout=40)
    return json.loads(result.stdout)


def phase(pair, name):
    cmd = ['env', 'CUDA_VISIBLE_DEVICES=', 'PYTHONDONTWRITEBYTECODE=1', 'OMP_NUM_THREADS=4', 'OPENBLAS_NUM_THREADS=4', 'MKL_NUM_THREADS=4', PY, REMOTE + '/audit/physical_cpu/run.py', '--pair', pair, '--phase', name]
    started = time.monotonic()
    result = subprocess.run(SSH + [shlex.join(cmd)], capture_output=True, text=True, timeout=360)
    path = ADMIN / 'logs' / (pair + '_' + name + '_' + str(time.time_ns()) + '.log')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.stdout + '\nSTDERR\n' + result.stderr)
    if result.returncode == 75:
        return False
    if result.returncode:
        raise RuntimeError('physical phase failed; inspect ' + str(path))
    print(json.dumps({'event': 'PHYSICAL_PHASE_COMPLETED', 'pair': pair, 'phase': name, 'elapsed_seconds': time.monotonic() - started}), flush=True)
    return True


def download(pair):
    for relative in ('poses/' + pair + '/', 'scores/physical/' + pair + '.json'):
        dest = ROOT / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        cmd = ['rsync', '-az', '-e', SSH_COMMAND]
        if relative.endswith('/'):
            dest.mkdir(exist_ok=True)
            cmd += ['--include=*/', '--include=*.json', '--exclude=*']
        subprocess.run(cmd + ['H3_SERVER_A:' + REMOTE + '/' + relative, str(dest)], check=True, timeout=180)
    report = read(ROOT / 'scores/physical' / (pair + '.json'))
    for method in ('native', 'forced'):
        folder = ROOT / 'poses' / pair / method
        receipt = read(folder / 'COMPLETE.json')
        assert sha(folder / (method + '.pose.json')) == receipt['pose']['sha256']
        assert sha(folder / 'COMPLETE.json') == report['generated_pose_receipts'][method]['sha256']
    output = ADMIN / 'receipts' / (pair + '.json')
    save(output, {'pair': pair, 'physical_report': bound(ROOT / 'scores/physical' / (pair + '.json')), 'CPU_only': True, 'all_fixed_views_retained': True})
    rows = report['result']['paired_lag_summary']
    counts = {m: sum(x['methods'][m]['status'] == 'qualified_exploratory' for x in rows) for m in ('native', 'forced')}
    print(json.dumps({'event': 'PHYSICAL_PAIR_READY', 'pair': pair, 'report': str(ROOT / 'scores/physical' / (pair + '.json')), 'qualified_windows_features': counts, 'denominator': len(rows)}), flush=True)


def main():
    while True:
        for pair in PAIR_KEYS:
            ready = ROOT / 'audit/consumer_takeover/receipts' / pair / 'LOCAL_MEDIA_READY.json'
            if not ready.exists() or (ADMIN / 'receipts' / (pair + '.json')).exists():
                continue
            state = remote_state(pair)
            if not state['score']:
                subprocess.run(['rsync', '-az', '-e', SSH_COMMAND, str(ROOT / 'incoming' / pair) + '/', 'H3_SERVER_A:' + REMOTE + '/incoming/' + pair + '/'], check=True, timeout=180)
                if not phase(pair, 'check'):
                    continue
                busy = False
                for method in ('native', 'forced'):
                    if not state[method] and not phase(pair, 'pose-' + method):
                        busy = True
                        break
                if busy or not phase(pair, 'evaluate'):
                    continue
            download(pair)
        if all((ADMIN / 'receipts' / (pair + '.json')).exists() for pair in PAIR_KEYS):
            print('ALL_EIGHT_PHYSICAL_PAIRS_COMPLETE', flush=True)
            return
        time.sleep(30)


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        save(ADMIN / ('FAILURE_' + str(time.time_ns()) + '.json'), {'error': repr(error), 'traceback': traceback.format_exc(), 'GPU_started': False})
        raise
