"""Frozen offline pose/physical diagnostics for actual completed R72 pairs."""
import argparse
import collections
import contextlib
import fcntl
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

os.environ['CUDA_VISIBLE_DEVICES'] = ''
ROOT = Path(__file__).resolve().parent

def read(path):
    return json.loads(Path(path).read_text())

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()

def bound(path):
    return {'file': str(path), 'sha256': sha(path)}

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def verify(pair):
    protocol = read(ROOT / 'PROTOCOL.json')
    for item in protocol['bindings']:
        assert sha(ROOT / item['relative']) == item['sha256'], item['relative']
    definition = protocol['pairs'][pair]
    incoming = ROOT / 'inputs' / pair
    gate = read(incoming / 'PAIR_RUNTIME_GATE.json')
    assert gate['schema'] == 'r72-paired-runtime-gate-v1' and gate['passed'] is True
    assert gate['source_id'] == pair and all(x is True for x in gate['checks'].values())
    for key in ['producer_seal', 'input_video_equal', 'native_vae_calls_equal',
                'qwen_presentation_equal', 'actual_initial_AV_noise_equal', 'independent_prompt_conditioning']:
        assert gate['checks'][key] is True
    for arm in ['p0', 'p1']:
        run = gate['runs'][arm]
        assert run['run_id'] == definition['expected_run_prefix'] + arm
        assert run['NFE'] == run['Euler_updates'] == 20 and run['routed_blocks'] == 0
        assert run['valid_frames'] == 147 and run['evaluation_indices'] == list(range(0,147,3))
        assert sha(incoming / (arm+'.mp4')) == run['video']['sha256']
    source_path = ROOT / 'source_pose' / (definition['motion']+'.pose.json')
    source = read(source_path)
    manifest = read(ROOT / 'source_pose/MANIFEST.json')['sources'][definition['motion']]
    assert sha(source_path) == manifest['pose_sha256']
    assert source['video']['sha256'] == definition['source_video_sha256'] == manifest['video_sha256']
    return protocol, gate, source_path, source

@contextlib.contextmanager
def lock(protocol):
    path = Path(protocol['cpu_lock'])
    assert path.exists(), 'existing shared CPU lock must exist'
    with path.open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield

def pose(pair, arm):
    protocol, gate, source_path, source = verify(pair)
    for path, digest in protocol['pose_protocol']['frozen_external'].items():
        assert sha(path) == digest, path
    dest = ROOT / 'poses' / pair / arm
    receipt_path = dest / 'COMPLETE.json'
    if receipt_path.exists():
        r = read(receipt_path)
        assert sha(dest / (arm+'.pose.json')) == r['pose']['sha256']
        assert r['video']['sha256'] == gate['runs'][arm]['video']['sha256']
        return
    assert not dest.exists(), 'preserve incomplete attempt for inspection'
    dest.mkdir(parents=True)
    video = ROOT / 'inputs' / pair / (arm+'.mp4')
    command = [sys.executable, str(ROOT/'vendor/pose_probe.py'), '--video', str(video),
               '--output-dir', str(dest), '--threads', '4', '--stride', '1']
    started = time.monotonic()
    with (dest/'pose.log').open('x') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
            env=dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='4', MKL_NUM_THREADS='4',
                     OPENBLAS_NUM_THREADS='4', NUMEXPR_NUM_THREADS='4', PYTHONDONTWRITEBYTECODE='1'), timeout=240)
    assert result.returncode == 0, 'CPU pose failed; preserve pose.log'
    target_path = dest / (arm+'.pose.json')
    target = read(target_path)
    assert target['provenance'] == source['provenance'] and target['joint_order'] == source['joint_order']
    assert target['video']['sha256'] == sha(video)
    assert target['extraction'] == protocol['pose_protocol']['extraction']
    assert len(target['frames']) == 158 and [x['frame'] for x in target['frames']] == list(range(158))
    save(receipt_path, {'passed': True, 'pair': pair, 'arm': arm, 'pose': bound(target_path),
        'video': bound(video), 'source_pose': bound(source_path), 'gate': bound(ROOT/'inputs'/pair/'PAIR_RUNTIME_GATE.json'),
        'protocol': bound(ROOT/'PROTOCOL.json'), 'elapsed_seconds': time.monotonic()-started,
        'command': command, 'cuda_initialized': False, 'pose_provenance': target['provenance']})

def evaluate(pair, mode):
    protocol, gate, source_path, source = verify(pair)
    targets = {}
    for arm in ['p0','p1']:
        path = ROOT/'poses'/pair/arm/(arm+'.pose.json')
        receipt = read(path.parent/'COMPLETE.json')
        assert receipt['passed'] and receipt['pose']['sha256'] == sha(path)
        assert receipt['video']['sha256'] == gate['runs'][arm]['video']['sha256']
        assert receipt['protocol']['sha256'] == sha(ROOT/'PROTOCOL.json')
        targets[arm] = path
    output = ROOT/'results'/pair/(mode+'.json.gz')
    if output.exists():
        return
    if mode == 'physical':
        sys.path.insert(0,str(ROOT/'vendor/physical'))
        evaluator = load('frozen_r65_evaluate', ROOT/'vendor/physical/evaluate.py')
        adapter = load('isolated_targets',ROOT/'vendor/adapter.py')
        results = adapter.independent_targets(evaluator.evaluate, source, {k:read(p) for k,p in targets.items()})
        summary = {k: v['lag_summary'] for k,v in results.items()}
    else:
        sys.path.insert(0,str(ROOT/'vendor/visible/scripts'))
        scanner = load('frozen_r59_scan',ROOT/'vendor/visible/scripts/scan_current_pose.py')
        geometry = scanner.Geometry(**protocol['geometry'])
        results = {k: scanner.observe(source_path, path, 0, geometry) for k,path in targets.items()}
        summary = {k: {'rows':len(v['windows']), 'baseline_counts':dict(collections.Counter(r['baseline'] for r in v['windows'])),
                      'status_counts':dict(collections.Counter(r['status'] for r in v['windows']))} for k,v in results.items()}
    output.parent.mkdir(exist_ok=True,parents=True)
    with gzip.open(output,'xt') as f:
        json.dump({'schema':'r72-offline-final-prompt-diagnostic-v1','pair':pair,'mode':mode,
                   'protocol':bound(ROOT/'PROTOCOL.json'),'actual_gate':bound(ROOT/'inputs'/pair/'PAIR_RUNTIME_GATE.json'),
                   'source_pose':bound(source_path),'targets':{k:bound(p) for k,p in targets.items()},
                   'results':results,'summary':summary,'gpu_started':False,
                   'overlapping_views_are_not_independent_samples':True},f,allow_nan=False)
    save(output.with_suffix('').with_suffix('.SUMMARY.json'),summary)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--pair',required=True)
    p.add_argument('--mode',choices=['pose_p0','pose_p1','physical','visible'],required=True)
    args=p.parse_args()
    protocol,*_=verify(args.pair)
    try:
        with lock(protocol):
            if args.mode.startswith('pose_'):pose(args.pair,args.mode.removeprefix('pose_'))
            else:evaluate(args.pair,args.mode)
    except BlockingIOError:
        print(json.dumps({'status':'CPU_BUSY','pair':args.pair,'mode':args.mode}))
        return 75
    print(json.dumps({'status':'complete','pair':args.pair,'mode':args.mode,'gpu_started':False}))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
