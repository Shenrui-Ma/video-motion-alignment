"""One bounded evaluation pass. Default is CPU-only preflight; --execute starts CUDA."""
import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False))
    temporary.replace(path)


def collect(root, manifest, config):
    rows = []
    by_method = {}
    for job in manifest['jobs']:
        scores = {}
        for metric in config['numeric_metrics'] + ['quantity_accuracy']:
            file = root / 'evaluation/results' / job['id'] / (metric + '.json')
            if file.exists():
                item = json.loads(file.read_text())
                rows.append(item)
                if item.get('status') == 'done':
                    scores[metric] = item['score']
        by_method[job['method']] = scores
    source_mf = by_method['source'].get('motion_fidelity')
    if source_mf is not None:
        for scores in by_method.values():
            if 'motion_fidelity' in scores:
                scores['motion_fidelity_delta_from_reference'] = scores['motion_fidelity'] - source_mf
    done = sum(r['metric'] in config['numeric_metrics'] and r['status'] == 'done' for r in rows)
    failed = sum(r['status'] == 'failed' for r in rows)
    na = sum(r['metric'] == 'quantity_accuracy' and r['status'] == 'not_applicable' for r in rows)
    result = dict(expected_numeric=63, numeric_done=done, failed=failed,
                  qa_not_applicable=na, passed=done == 63 and na == 7 and failed == 0,
                  method_scores=by_method, rows=rows, is_cf_policy=config['is_cf_policy'])
    atomic(root / 'SUMMARY.json', result)
    return result


def main(args):
    config = json.loads((HERE / 'config.json').read_text())
    root = Path(config['remote_root'])
    if HERE != root / 'code' or os.getuid() != config['uid']:
        raise RuntimeError('Run only from the isolated .81 code directory as UID1016')
    lock = (root / 'launch.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    manifest = json.loads((HERE / 'manifest.json').read_text())
    if len(manifest['jobs']) != 7 or set(j['method'] for j in manifest['jobs']) != set(config['methods']):
        raise ValueError('Unexpected manifest methods')
    if manifest.get('expected_numeric') != 63:
        raise ValueError('Unexpected numeric count')
    for job in manifest['jobs']:
        if Path(job['video']).parent != root / 'videos':
            raise ValueError('Video outside isolated root')
        if digest(job['video']) != job['sha256']:
            raise ValueError('Uploaded video SHA mismatch: ' + job['method'])
    fingerprints = json.loads((HERE / 'HOST81_READONLY.json').read_text())['files']
    for name, expected in fingerprints.items():
        if digest(name) != expected:
            raise ValueError('Shared scientific source changed: ' + name)
    for name in ['metric_worker.py', 'durable_metrics.py', 'prepare_frames.py']:
        original = config['shared_root'] + '/code/' + name
        if digest(HERE / name) != fingerprints[original]:
            raise ValueError('Local worker snapshot mismatch: ' + name)
    subprocess.run([sys.executable, str(HERE / 'prepare_frames.py'),
                    '--manifest', str(HERE / 'manifest.json')], check=True)
    for job in manifest['jobs']:
        frames = Path(job['target_frames_parent']) / 'short_0177'
        if len(list(frames.glob('*.png'))) != 60:
            raise ValueError('Expected 60 valid frames per video')
    report = dict(passed=True, time=time.time(), uid=os.getuid(),
                  boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                  manifest_sha256=digest(HERE / 'manifest.json'), jobs=7,
                  numeric_items=63, action='CPU preparation only')
    atomic(root / 'PREFLIGHT.json', report)
    if not args.execute:
        print(json.dumps(report)); return
    if not args.gpu or not args.gpu.startswith('GPU-'):
        raise ValueError('--execute requires an explicit GPU UUID')
    occupied = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid',
                                        '--format=csv,noheader,nounits'], text=True, timeout=15)
    if any(line.split(',')[0].strip() == args.gpu for line in occupied.splitlines()):
        raise RuntimeError('Selected GPU has another compute process; no worker launched')
    free = int(subprocess.check_output(['nvidia-smi', '-i', args.gpu,
               '--query-gpu=memory.free', '--format=csv,noheader,nounits'], text=True, timeout=15).strip())
    if free < args.min_free_mib:
        raise RuntimeError('GPU free memory below admission threshold')
    old = root / 'RUN.json'
    if old.exists() and json.loads(old.read_text())['manifest_sha256'] != report['manifest_sha256']:
        raise RuntimeError('Manifest changed after a prior evaluation; retain evidence and use a new root')
    command = [sys.executable, str(HERE / 'durable_metrics.py'), '--root', str(root / 'evaluation'),
               '--manifest', str(HERE / 'manifest.json'), '--official', config['shared_root'] + '/code/official_source',
               '--model-paths', config['shared_root'] + '/code/model_paths.yml',
               '--metrics', *config['numeric_metrics'], 'quantity_accuracy', '--gpu', args.gpu,
               '--min-free-mib', str(args.min_free_mib), '--retries', '1', '--timeout', '2400', '--once']
    report.update(action='one isolated evaluation pass', gpu=args.gpu, command=command, pid=os.getpid())
    atomic(old, report)
    process = subprocess.Popen(command)
    rc = process.wait()
    result = collect(root, manifest, config)
    atomic(root / 'EXIT.json', dict(time=time.time(), exit_code=rc, summary_passed=result['passed']))
    print(json.dumps({k: v for k, v in result.items() if k not in ['rows', 'method_scores']}))
    if rc or not result['passed']:
        raise SystemExit(rc or 2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--gpu')
    parser.add_argument('--min-free-mib', type=int, default=18000)
    main(parser.parse_args())
