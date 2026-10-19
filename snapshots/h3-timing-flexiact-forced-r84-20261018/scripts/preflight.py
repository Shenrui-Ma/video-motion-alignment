"""CPU-only static bindings; actual pair equality remains a post-run gate."""
import argparse
import json
from pathlib import Path
from r84_contract import ROOT, read, sha, require, registry, validate_job, ROUTER


def check(root=ROOT, live=False):
    root = Path(root); jobs, order = registry(root)
    s = read(root / 'configs/scientific_contract.json'); runtime = read(root / 'configs/runtime.json')
    require(s['NFE_per_job'] == s['callback_count'] == 20 and not s['online_observer'] and
            s['router'] == ROUTER, 'scientific route/count differs')
    for run in order: validate_job(run, root)
    for p, h in read(root / 'configs/input_hashes.json').items():
        require(sha(root / 'inputs' / p) == h, 'input differs: ' + p)
    for p, v in read(root / 'configs/runtime_kernel_hashes.json').items():
        require(sha(root / p) == v['current_sha256'], 'frozen numeric module changed: ' + p)
    require(runtime['memory_mode'] == 'normal' and runtime['reserve_vram'] == 8, 'memory mode differs')
    if live:
        require(root.resolve() == Path(runtime['remote_root']), 'actual remote root required')
        from execution_gate import atomic, historical_evidence
        from check_storage import check as storage
        atomic(root / 'audit/STORAGE_STARTUP.json', storage(root))
        import service
        service.main_memory_profile()
        require(read(root / 'configs/admission.json')['ready_for_launch'] is True, 'root admission pending')
        for p, v in read(root / 'deploy_manifest.json')['files'].items():
            require(sha(root / p) == v['sha256'], 'sealed file differs: ' + p)
        for p, h in read(root / 'configs/parent_core_hashes.json').items():
            require(sha(Path(runtime['core']) / p) == h, 'actual core differs: ' + p)
        for run in order: historical_evidence(run, root)
    return {'passed': True, 'jobs': order, 'new_forced_jobs': 2, 'historical_native_jobs': 2,
            'same_service_generation': False, 'actual_prefix_equality_required': True, 'GPU_started': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--live', action='store_true')
    print(json.dumps(check(live=p.parse_args().live), indent=2))
