"""Bounded isolated VAE resource measurement on currently idle GPU2."""
from pathlib import Path
import hashlib
import json
import os
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'r19_hardware_bridge/execution.json'
if (ROOT / 'execution.json').exists():
    raise RuntimeError('Existing execution requires review')
args = json.loads(OLD.read_text())['command']
args[2] = str(ROOT / 'peak_decode.py')
args[args.index('--gpu-uuid') + 1] = 'GPU-REDACTED'
args[args.index('--output') + 1] = str(ROOT / 'archived_native010.mp4')
env = os.environ.copy()
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    env[k] = '4'
env['CUDA_VISIBLE_DEVICES'] = ''
record = {'status': 'running', 'started_unix': time.time(), 'command': args, 'NFE': 0}
def save():
    (ROOT / 'execution.json').write_text(json.dumps(record, indent=2) + '\n')
save()
p = None
try:
    with (ROOT / 'decode.log').open('x') as log:
        p = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        record['pid'] = p.pid
        record['uid'] = Path('/proc', str(p.pid)).stat().st_uid
        record['start_ticks'] = Path('/proc', str(p.pid), 'stat').read_text().split(') ', 1)[1].split()[19]
        save()
        record['exit_code'] = p.wait(timeout=180)
    assert record['exit_code'] == 0
    data = json.loads((ROOT / 'archived_native010.json').read_text())
    assert data['status'] == 'complete'
    assert data['decoded_tensor_sha256'] == 'b909923b104228887a7678828422c871bed60470fb565f15ff81024f84474f69'
    assert data['preencode_rgb24_sha256'] == '6e2d3554a6446bfbf3cf1f3b0ea064981dc8fec528ff904a6af1b53519a9d2aa'
    assert data['output_sha256'] == hashlib.sha256((ROOT / 'archived_native010.mp4').read_bytes()).hexdigest()
    assert 'retrying with tiled VAE' not in (ROOT / 'decode.log').read_text()
    record['allocator'] = json.loads((ROOT / 'allocator_peak.json').read_text())
    record['status'] = 'complete'
except BaseException as error:
    record['status'] = 'failed'
    record['error'] = repr(error)
    raise
finally:
    if p is not None and p.poll() is None:
        os.killpg(p.pid, signal.SIGTERM)
        try:
            p.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
    record['child_absent'] = p is None or not Path('/proc', str(p.pid)).exists()
    record['compute_after'] = subprocess.check_output(['nvidia-smi', '--id=GPU-REDACTED', '--query-compute-apps=pid', '--format=csv,noheader,nounits'], text=True).strip()
    record['finished_unix'] = time.time()
    record['wall_seconds'] = record['finished_unix'] - record['started_unix']
    save()
print(json.dumps(record), flush=True)
