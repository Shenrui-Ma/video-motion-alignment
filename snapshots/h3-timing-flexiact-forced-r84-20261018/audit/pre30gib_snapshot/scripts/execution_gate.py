"""Root individually approves each historical-Native continuation on the current service."""
import argparse
import json
import os
import time
from pathlib import Path
from r84_contract import ROOT, read, sha, registry, require


def atomic(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n'); os.replace(tmp, path)


def approval(root=ROOT):
    root = Path(root); a = read(root / 'audit/ROOT_SERVICE_APPROVAL.json'); runtime = read(root / 'configs/runtime.json')
    require(a.get('schema') == 'r84-service-capacity-trial-v1' and a.get('root_approved') is True,
            'root service approval pending')
    require(a['runtime_profile_sha256'] == sha(root / 'configs/runtime.json') and a['main_gpu_uuid'] == runtime['gpu_uuid'],
            'service runtime/device changed')
    require(a['required_free_bytes'] >= 40 * 1024**3 and a['reserve_vram_gib'] == 8, 'headroom differs')
    require(a['capacity_status'] == 'ACTUAL_FULL_TRAJECTORY_PENDING', 'trial capacity claim changed')
    return a


def historical_evidence(run, root=ROOT):
    root = Path(root); jobs, _ = registry(root); require(run in jobs, 'unregistered job')
    c = jobs[run]['case']; old = Path(c['baseline_root']); name = c['baseline_run']
    binding = read(root / 'configs/HISTORICAL_BINDINGS.json')[c['source_id']]
    require(binding['remote_root'] == str(old), 'old root differs')
    for relative, expected in binding['files'].items():
        p = old / relative
        require(not p.is_symlink() and p.is_file() and sha(p) == expected['sha256'] and
                p.stat().st_size == expected['bytes'], 'historical actual evidence changed: ' + relative)
    j = read(old / 'logs' / (name + '_job.json')); h = read(old / 'logs' / (name + '_history.json'))
    graph = read(root / c['parent_graph'])
    require(j['name'] == name and j['status'] == 'success' and j['graph_sha256'] == c['parent_graph_sha256'],
            'historical Native job differs')
    require(h['status']['completed'] is True and h['status']['status_str'] == 'success' and
            h['prompt'][1] == j['prompt_id'] and h['prompt'][2] == graph, 'historical actual graph/history differs')
    old_runtime = read(old / 'configs/runtime.json'); runtime = read(root / 'configs/runtime.json')
    for key in ('host', 'core', 'python', 'dependencies', 'models', 'memory_mode', 'reserve_vram'):
        require(old_runtime[key] == runtime[key], 'same-host numeric profile differs: ' + key)
    original = old / 'audit' / (c['baseline_noise_pair_id'] + '_noise.pt')
    copied = root / 'audit' / original.name
    require(copied.is_file() and not copied.is_symlink() and sha(copied) == sha(original), 'actual old noise cache missing/different')
    return {'baseline_run': name, 'baseline_root': str(old),
        'bindings_sha256': sha(root / 'configs/HISTORICAL_BINDINGS.json'),
        'job_sha256': sha(old / 'logs' / (name + '_job.json')),
        'history_sha256': sha(old / 'logs' / (name + '_history.json')),
        'noise_sha256': sha(original), 'pairing': 'same-host across service generations; post-run tensor equality required'}


def approve_run(run, root=ROOT, native_reviewed=False):
    root = Path(root); a = approval(root); jobs, _ = registry(root)
    require(run in jobs and native_reviewed, 'root review of historical Native required')
    import service
    owner = read(root / 'processes/service.json'); service.assert_owned(owner)
    value = {'schema': 'r84-individual-job-approval-v1', 'root_approved': True, 'run': run,
        'runtime_profile_sha256': a['runtime_profile_sha256'], 'graph_sha256': jobs[run]['graph_sha256'],
        'native_reviewed': True, 'historical_evidence': historical_evidence(run, root),
        'target_service': {'pid': owner['pid'], 'identity': owner['identity']}, 'created_unix': time.time()}
    atomic(root / 'audit/ROOT_JOB_APPROVALS' / (run + '.json'), value)
    return value


def admitted_job(run, root=ROOT):
    root = Path(root); a = approval(root); jobs, _ = registry(root)
    require(run in jobs, 'unregistered job'); p = root / 'audit/ROOT_JOB_APPROVALS' / (run + '.json')
    if not p.exists(): return False
    v = read(p)
    require(v.get('schema') == 'r84-individual-job-approval-v1' and v.get('root_approved') is True and
            v['run'] == run and v.get('native_reviewed') is True, 'individual approval invalid')
    require(v['runtime_profile_sha256'] == a['runtime_profile_sha256'] and
            v['graph_sha256'] == jobs[run]['graph_sha256'], 'approved graph/runtime changed')
    require(v['historical_evidence'] == historical_evidence(run, root), 'historical review evidence changed')
    owner = read(root / 'processes/service.json')
    require(v['target_service'] == {'pid': owner['pid'], 'identity': owner['identity']}, 'approved target service generation changed')
    return True


def seal(root=ROOT):
    root = Path(root)
    require(not (root / 'processes/service.json').exists(), 'service registry exists')
    paths = []
    for folder in ('scripts', 'extensions', 'configs/graphs', 'configs/parent_graphs',
                   'configs/R54_evidence', 'configs/prompts', 'design', 'ancestry',
                   'analysis/postrun', 'tests', 'source_snapshot'):
        paths.extend(p for p in (root / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    paths.extend(root / 'configs' / name for name in ('runtime.json', 'scientific_contract.json',
        'input_hashes.json', 'runtime_kernel_hashes.json', 'parent_core_hashes.json',
        'expected_checkpoint_hashes.json', 'storage_policy.json', 'HISTORICAL_BINDINGS.json'))
    value = {'schema': 'r84-producer-seal-v1', 'files': {str(p.relative_to(root)):
        {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(paths)},
        'mutable_root_owned': ['configs/admission.json', 'audit/ROOT_SERVICE_APPROVAL.json', 'audit/ROOT_JOB_APPROVALS/'],
        'created_unix': time.time()}
    atomic(root / 'deploy_manifest.json', value); return value


def main():
    p = argparse.ArgumentParser(); p.add_argument('action', choices=('seal', 'approve-service', 'approve-run'))
    p.add_argument('run', nargs='?'); p.add_argument('--root-admitted', action='store_true')
    p.add_argument('--native-reviewed', action='store_true'); p.add_argument('--free-mib', type=int, default=40960)
    a = p.parse_args()
    if a.action == 'seal': v = seal()
    else:
        require(a.root_admitted, 'root must admit actual resources')
        require(ROOT == Path(read(ROOT / 'configs/runtime.json')['remote_root']), 'actual remote root required')
        if a.action == 'approve-service':
            require(a.free_mib >= 40960, 'trial requires40GiB free')
            v = {'schema': 'r84-service-capacity-trial-v1', 'root_approved': True,
                'runtime_profile_sha256': sha(ROOT / 'configs/runtime.json'),
                'main_gpu_uuid': read(ROOT / 'configs/runtime.json')['gpu_uuid'],
                'required_free_bytes': a.free_mib * 1024**2, 'reserve_vram_gib': 8,
                'capacity_status': 'ACTUAL_FULL_TRAJECTORY_PENDING', 'created_unix': time.time()}
            atomic(ROOT / 'audit/ROOT_SERVICE_APPROVAL.json', v)
        else: v = approve_run(a.run, native_reviewed=a.native_reviewed)
    print(json.dumps({'action': a.action, 'files': len(v.get('files', {})), 'run': v.get('run')}, indent=2))


if __name__ == '__main__': main()
