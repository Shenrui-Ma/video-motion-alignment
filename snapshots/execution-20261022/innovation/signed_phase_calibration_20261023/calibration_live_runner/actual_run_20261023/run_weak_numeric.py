"""Task-local CPU launcher; frozen numerical implementation is unchanged."""
import fcntl
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path('/data/research-user/h3_inference_20261023/live_phase_pair_20261023')
code = root/'analysis_runner_13123f64'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
env = dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
deployment = json.loads((code/'DEPLOYMENT.json').read_text())
assert all(sha(code/n) == v for n,v in deployment['files_sha256'].items())
gate = json.loads((root/'jobs/global_weak/TRAJECTORY_GATE.json').read_text())
assert gate['passed'] is True and gate['case'] == 'short_0358' and gate['method'] == 'global_weak'
assert gate['callback_count'] == gate['actual_model_forward_count'] == 20
assert gate['completed_blocks'] == 1000 and gate['extra_model_forward_calls'] == 0
assert gate['actual_video_sha256'] == '2250079333307c9edf005cc48cb89eed09e0cc072d7125b094f66354803c6562'
assert sha(Path(gate['actual_video_file'])) == gate['actual_video_sha256']
target = root/'numerical/global_weak'
target.mkdir(exist_ok=True)
receipt = {'schema':'h3-live-weak-numerical-receipt-v1','cpu_only':True,
           'probability_analysis_performed':False,'policy_changed':False,'captures':[]}
with (code/'numeric.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for row in gate['captures']:
        step = row['step_zero_based']; assert step in (9,19) and row['layer_zero_based'] == 25
        output = target/f'step{step:03d}.json'
        assert sha(Path(row['qk_file'])) == row['qk_sha256']
        if not output.exists():
            subprocess.run([sys.executable,str(code/'replay_diagnostics/diagnose.py'),
                '--capture',row['qk_file'],'--capture-sha256',row['qk_sha256'],
                '--output',str(output)],check=True,env=env)
        data = json.loads(output.read_text())
        assert data['capture_sha256'] == row['qk_sha256'] and data['forward_identity'] == row['forward_identity']
        assert data['policy_sha256'] == deployment['files_sha256']['replay_diagnostics/POLICY.json']
        receipt['captures'].append({'step':step,'file':str(output),'sha256':sha(output),
            'passed':data['numerical_definition_pass'],
            'max_nrmse':max(x['nrmse'] for b in data['branches'].values() for x in b['full']),
            'min_exact_fraction':min(x['exact_fraction'] for b in data['branches'].values() for x in b['full'])})
    receipt['passed'] = all(row['passed'] for row in receipt['captures'])
    (code/'WEAK_NUMERICAL_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))
