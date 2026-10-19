"""CPU preparation checks and strict actual-parent/runtime launch checks."""
import argparse
import json
from pathlib import Path
from execution_contract import ROOT, read, sha, require, verify_candidate
from r59_contract import registry, validate_job, REMOTE


def prepared(root=ROOT):
    root = Path(root)
    verify_candidate(root)
    from science_preservation import check as check_science
    science = check_science(root)
    jobs, order = registry(root)
    for name in order:
        validate_job(name, root, inputs=False)
    require(read(root / 'configs/scientific_contract.json')['continuous'] == {
        'retain_service_between_jobs': True, 'cache_none': False, 'idle_hold_seconds': 1800,
        'max_service_seconds': 43200, 'job_timeout_seconds': 14400,
        'root_final_close_releases': True, 'failure_releases_exact_owned': True}, 'continuous execution bounds differ')
    return {'status': 'CPU_PREPARATION_PASS', 'science_preservation': science, 'jobs': len(order), 'sources': 5, 'registered_arms': 4,
            'new_jobs_per_arm': {arm: sum(row['arm'] == arm for row in jobs.values()) for arm in ('visible_only', 'visible_fallback', 'weak_only')},
            'actual_parent_ready': read(root / 'configs/PARENT_CLOSURE.json')['ready'], 'GPU_launch_authorized': False}


def check(root=ROOT, metadata_only=False, live=False):
    root = Path(root)
    prepared(root)
    from observer_import import t
    t.require_parent_closure(root)
    t.bindings()
    t.admission_document(approved=not metadata_only or live)
    from parent_binding import check as check_parent
    parent = check_parent(root, remote=not metadata_only)
    jobs, order = registry(root)
    rows = [validate_job(name, root, inputs=not metadata_only) for name in order]
    gates = None
    if not metadata_only:
        require(root.resolve() == REMOTE and read(root / 'configs/runtime.json')['status'] == 'READY', 'formal remote runtime pending')
        from prelaunch_gates import check as check_gates
        gates = check_gates(root)
        binding = t.bindings(external=True)
        for relative, digest in read(root / 'configs/parent_core_hashes.json').items():
            require(sha(Path(binding['comfy']) / relative) == digest, 'actual H3 core differs')
        manifest = read(root / 'deploy_manifest.json')
        require(read(root / 'ROOT_APPROVED_DEPLOYMENT.json')['manifest_sha256'] == sha(root / 'deploy_manifest.json'), 'root deployment seal differs')
        for relative, record in manifest['files'].items():
            require(sha(root / relative) == record['sha256'], 'sealed producer changed: ' + relative)
    return {'passed': True, 'cases': rows, 'parent_binding': parent, 'GPU_gates': gates,
            'updates_per_case': 20, 'weak_only_NFE': 29, 'visible_NFE_range': [20, 39]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--preparation', action='store_true')
    parser.add_argument('--metadata-only', action='store_true')
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    result = prepared(args.root) if args.preparation else check(args.root, args.metadata_only, args.live)
    print(json.dumps(result, indent=2))
