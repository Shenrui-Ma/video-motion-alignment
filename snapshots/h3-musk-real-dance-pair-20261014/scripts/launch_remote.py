"""Task-local admission, provenance and isolated process lifecycle bootstrap."""
from pathlib import Path
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

import service

r = service.RUN
for directory in ['custom_nodes', 'input', 'output', 'temp', 'user', 'logs', 'processes', 'audit', 'analysis']:
    (r / directory).mkdir(exist_ok=True)
for name, target in {
    'H3EventEmphasis': r / 'extensions/H3EventEmphasis',
    'H3PairAudit': r / 'extensions/H3PairAudit',
    'H3EventAudit': r / 'extensions/H3EventAudit',
    'ComfyUI-KJNodes': Path('/data3/researcher/h3_runs/closure_tutorials_53592/01-anime/custom_nodes/ComfyUI-KJNodes'),
}.items():
    p = r / 'custom_nodes' / name
    if not p.exists():
        p.symlink_to(target, target_is_directory=True)
for name in ['05_real_megumi_v.mp4', 'elon_musk_royal_society.jpg']:
    dst = r / 'input' / name
    if dst.is_symlink():
        raise RuntimeError('Input must be a real file under input root')
    shutil.copy2(r / 'inputs' / name, dst)
# Validate the relocated write guard before any model load.
path = r / 'extensions/H3EventAudit/__init__.py'
function = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'audit_root')
ns = {'Path': Path}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), ns)
assert ns['audit_root'](str(r / 'audit')) == r / 'audit'
parent = json.loads((r / 'configs/parent_runtime_provenance.json').read_text())
hashes = json.loads((r / 'configs/model_hashes_host41.json').read_text())
prov = {'actual_host': '192.0.2.1', 'models': {}, 'inputs': {}, 'code': {}, 'checked_unix': time.time()}
for key, old in parent['models'].items():
    p = Path(service.MODELS) / key
    s = p.stat()
    match = s.st_size == old['bytes'] and s.st_mtime_ns == old['mtime_ns']
    if not match:
        raise RuntimeError('Model metadata changed: ' + key)
    actual_hash = hashes[key]['sha256']
    if actual_hash != old['prior_full_sha256']:
        raise RuntimeError('Model SHA mismatch: ' + key)
    prov['models'][key] = dict(old, path=str(p), resolved=str(p.resolve()), size_mtime_match=True, sha256=actual_hash, full_hash_recomputed=False, full_sha_source='h3-silverwolf-baseline-20261014 fresh full hashes; current size and mtime matched')
for p in (r / 'inputs').iterdir():
    prov['inputs'][p.name] = {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
for p in list((r / 'scripts').glob('*.py')) + list((r / 'extensions').rglob('*.py')):
    prov['code'][str(p.relative_to(r))] = hashlib.sha256(p.read_bytes()).hexdigest()
core_manifest = r / 'configs/parent_core_hashes.json'
old_hashes = json.loads(core_manifest.read_text())
prov['core_matches'] = {rel: hashlib.sha256((service.CORE / rel).read_bytes()).hexdigest() == h for rel, h in old_hashes.items()}
assert all(prov['core_matches'].values())
service.write_json(r / 'configs/runtime_provenance.json', prov)
env = dict(os.environ, LC_ALL='C', LANG='C', PYTHONDONTWRITEBYTECODE='1')
with (r / 'logs/supervisor.log').open('ab', buffering=0) as log:
    supervisor = subprocess.Popen(['python3', '-u', str(r / 'scripts/supervise_service.py')], cwd=r / 'scripts',
        stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True, env=env)
print(json.dumps({'supervisor_pid': supervisor.pid}), flush=True)
try:
    for _ in range(150):
        if supervisor.poll() is not None:
            raise RuntimeError('Supervisor exited; inspect admission/start logs')
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{service.PORT}/object_info/H3EventAuditReference', timeout=2) as response:
                info = json.load(response)
            assert 'musk_real_dance_pair_20261014' in info['H3EventAuditReference']['input']['required']['audit_dir'][1]['default']
            break
        except Exception:
            time.sleep(2)
    else:
        raise RuntimeError('Service readiness deadline exceeded')
    for role, name in [('watchdog', 'lease_watchdog.py'), ('controller', 'run_queue.py')]:
        with (r / 'logs' / (role + '.log')).open('ab', buffering=0) as log:
            p = subprocess.Popen(['python3', '-u', str(r / 'scripts' / name)], cwd=r / 'scripts',
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True, env=env)
        rec = {'pid': p.pid, 'identity': service.identity(p.pid), 'role': role}
        service.write_json(r / 'processes' / (role + '.json'), rec)
        print(json.dumps(rec), flush=True)
except BaseException:
    registry = r / 'processes/service.json'
    if registry.exists():
        service.stop()
    raise
