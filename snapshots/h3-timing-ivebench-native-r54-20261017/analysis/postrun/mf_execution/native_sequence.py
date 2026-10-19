"""Root-delegated sequential Native MF evaluation; quality values stay in artifacts."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = Path('/data3/researcher/h3_runs/ivebench_official_metric_20261017')
PYTHON = '/data3/researcher/ComfyUI/.venv/bin/python'
GPU = 'GPU-REDACTED'
FREEZE = 'd46b5c807c56aeb39e219e71271c7e5f050873ee74c5fe342988a3c1cb63dd45'
LOCK = Path('/data3/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock')
INPUT_SHA = {
    'short_0210': 'f6fe49986c84595b6c863099e2cfbfac6046bb5b964d3dbcaba587bda118f8c5',
    'short_0230': '1a8c4d99e2525ce5ea14395e52ad15eb4b53dd343ad4e21b89a1faa4b1717a63',
    'short_0263': 'fbc58018d8b68b3548ead2fefaa2d6444fa65c210492d93eceb644f2f8e284b1',
    'short_0352': '4a59cad0c0f46d903f70b0434d5c7548a9bd791522d34c69c2e55f8b7ee49d7b',
    'short_0370': 'e8f938ce807f0d657fa67bb83c245ab607575b7ae36a4b69be688f4a8af3f628',
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def identity(pid):
    p = Path('/proc') / str(pid)
    return {'uid': p.stat().st_uid, 'start_ticks': p.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19],
            'cmdline_sha256': sha(p / 'cmdline')}


def verify_runtime(plan):
    require(sha(ROOT / 'RUNTIME_FREEZE_HOST41.json') == FREEZE, 'runtime freeze changed')
    frozen = read(ROOT / 'RUNTIME_FREEZE_HOST41.json')
    require(all(sha(ROOT / item['file']) == item['sha256'] for item in frozen['files']), 'runtime member changed')
    require(sha(ROOT / frozen['checkpoint']['file']) == frozen['checkpoint']['sha256'], 'checkpoint changed')
    require(plan['runtime_freeze_sha256'] == FREEZE and plan['gpu_uuid'] == GPU, 'plan/runtime GPU differs')
    require([c['pair_id'] for c in plan['cases']] == list(INPUT_SHA), 'fixed case order differs')
    for case in plan['cases']:
        require(sha(case['release_manifest']) == INPUT_SHA[case['pair_id']], 'released input changed')
    profile = read(HERE / 'MEMORY_REQUIREMENT.json')
    for item in profile['source_reports']:
        report = ROOT / 'tracks/source' / item['pair_id'] / 'REPORT.json'
        require(sha(report) == item['report_sha256'], 'measured memory source report changed')
        require(read(report)['peak_reserved_bytes'] == item['peak_reserved_bytes'], 'measured peak differs')
    require(profile['require_free_bytes'] == max(r['peak_reserved_bytes'] for r in profile['source_reports']) + 2 * 1024**3,
            'actual peak plus2GiB requirement differs')
    sys.path.insert(0, str(ROOT / 'metric_runtime'))
    from ive_mf_adapter import verify_vendor
    verify_vendor()


def verify_own_release(pid, generation):
    """Require our completed tracker to leave NVML; record other users independently."""
    deadline = time.monotonic() + 10
    while True:
        current = identity(pid) if (Path('/proc') / str(pid)).exists() else None
        same_generation = current is not None and str(current['start_ticks']) == str(generation['start_ticks'])
        require(not same_generation, 'tracker generation still present')
        raw = subprocess.check_output(['nvidia-smi', '-i', GPU, '--query-compute-apps=pid',
                                       '--format=csv,noheader,nounits'], text=True, timeout=2)
        pids = [int(x.strip()) for x in raw.splitlines() if x.strip()]
        if pid not in pids or current is not None:
            return {'original_generation_absent': True, 'own_nvml_pid_absent': pid not in pids,
                    'pid_reused': current is not None, 'other_compute_pids': pids, 'gpu_uuid': GPU}
        if time.monotonic() >= deadline:
            raise TimeoutError('tracker NVML tail remains after10seconds')
        time.sleep(.25)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--recovery-release', type=Path, required=True)
    ap.add_argument('--recovery-release-sha256', required=True)
    a = ap.parse_args()
    require(sha(a.recovery_release) == a.recovery_release_sha256 and read(a.recovery_release)['status'] == 'released',
            'root prerequisite recovery release missing')
    plan = read(HERE / 'NATIVE_EVALUATION_PLAN.json')
    verify_runtime(plan)
    from shared_resource import check_gpu
    os.environ['CUDA_VISIBLE_DEVICES'] = GPU
    authority = {'scope': 'Root delegated all5 Native tracker/official MF on host41 GPU2 after recovered R53 release',
                 'runtime_freeze_sha256': FREEZE, 'inputs': INPUT_SHA, 'gpu_uuid': GPU,
                 'prior_recovery_release': str(a.recovery_release), 'prior_recovery_release_sha256': a.recovery_release_sha256,
                 'quality_blind_until_R55_policy_freeze': True, 'planned_denominator': 5}
    auth = HERE / 'ROOT_NATIVE_AUTHORIZATION.json'
    if auth.exists():
        require(read(auth) == authority, 'delegation differs')
    else:
        write(auth, authority)
    environment = dict(os.environ, CUDA_VISIBLE_DEVICES=GPU, OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2',
                       TMPDIR=str(ROOT / 'temp'), TMP=str(ROOT / 'temp'), TEMP=str(ROOT / 'temp'))
    rows = []
    with LOCK.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for case in plan['cases']:
            pair = case['pair_id']
            check_gpu(GPU)
            report_path = ROOT / 'tracks/native' / pair / 'REPORT.json'
            require(not report_path.exists(), 'existing Native tracking requires explicit resume review')
            preflight = ROOT / 'preflight/native' / pair / 'PREFLIGHT.json'
            if not preflight.exists():
                with (HERE / (pair + '_preflight.log')).open('x') as log:
                    subprocess.run(case['preflight_command'], check=True, stdout=log, stderr=subprocess.STDOUT,
                                   env=dict(environment, CUDA_VISIBLE_DEVICES=''), timeout=180)
            pre = read(preflight)
            require(pre['passed'] and pre['check_only'] and pre['input_manifest']['sha256'] == INPUT_SHA[pair], 'preflight differs')
            command = list(case['preCUDA_gate_command'])
            command[command.index(str(ROOT / 'metric_runtime/launch_tracking_gate.py'))] = str(HERE / 'tracking_gate.py')
            control = Path(command[command.index('--control') + 1])
            require(not control.exists(), 'existing gate requires explicit resume review')
            with (HERE / (pair + '_tracking.log')).open('x') as log:
                child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=environment, cwd=ROOT)
                deadline = time.monotonic() + 8
                while not (control / 'ready.json').exists() and time.monotonic() < deadline and child.poll() is None:
                    time.sleep(.05)
                ready = read(control / 'ready.json')
                require(ready['pid'] == child.pid and ready['identity'] == identity(child.pid), 'preCUDA generation identity differs')
                require(ready['identity']['uid'] == os.getuid() == 1004 and ready['CUDA_started'] is False, 'preCUDA owner/state differs')
                require(ready['arguments'] == command[command.index('--') + 1:] and ready['gpu_uuid'] == GPU, 'preCUDA arguments differ')
                require(all(sha(b['file']) == b['sha256'] for b in ready['bindings']), 'preCUDA bindings changed')
                admission = check_gpu(GPU)
                write(control / 'delegated_native_admission.json', {'authority_sha256': sha(auth), 'ready_sha256': sha(control / 'ready.json'),
                                                                  'resource_check': admission, 'exact_process_generation_verified': True})
                write(control / 'go.json', ready)
                print(json.dumps({'event': 'admitted', 'pair_id': pair, 'pid': child.pid}), flush=True)
                code = child.wait(timeout=240)
            require(code == 0, 'tracker failed')
            released = verify_own_release(child.pid, ready['identity'])
            report = read(report_path)
            require(report['passed'] and report['method'] == 'native' and report['pair_id'] == pair
                    and report['pid'] == child.pid and report['input_manifest']['sha256'] == INPUT_SHA[pair], 'tracking result binding differs')
            require(sha(report_path.parent / 'tracks.npz') == report['tracks_sha256'], 'tracking data changed')
            score_command = case['cpu_score_command']
            score_path = Path(score_command[score_command.index('--output') + 1])
            score_path.parent.mkdir(parents=True, exist_ok=True)
            with (HERE / (pair + '_score.log')).open('x') as log:
                subprocess.run(score_command, check=True, stdout=log, stderr=subprocess.STDOUT,
                               env=dict(environment, CUDA_VISIBLE_DEVICES=''), timeout=180)
            score = read(score_path)
            require(score['pair_id'] == pair and score['method'] == 'native' and score['cuda_initialized'] is False,
                    'CPU score identity/state differs')
            row = {'pair_id': pair, 'pid': child.pid, 'original_generation_absent': True, 'gpu_release': released,
                   'tracking_seconds': report['tracking_seconds'], 'wall_seconds': report['wall_seconds'],
                   'tracks_sha256': report['tracks_sha256'], 'report_sha256': sha(report_path), 'score_sha256': sha(score_path)}
            write(HERE / (pair + '_RECEIPT.json'), row)
            rows.append(row)
            print(json.dumps({'event': 'completed', 'pair_id': pair, 'tracking_seconds': row['tracking_seconds'],
                              'scored': True, 'quality_blind': True}), flush=True)
        write(HERE / 'NATIVE_MF_COMPLETE.json', {'passed': True, 'planned_denominator': 5, 'completed': len(rows),
                                              'quality_blind': True, 'receipts': rows})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
