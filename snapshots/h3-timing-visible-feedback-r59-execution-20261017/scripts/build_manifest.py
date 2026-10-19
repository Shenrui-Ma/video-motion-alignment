"""Seal the bound R59 producer after root-reviewed actual P1 GPU gates."""
import argparse
import json
import tarfile
from pathlib import Path
from execution_contract import ROOT, CANDIDATE_SHA, read, sha, file_record, require, write_new
from r59_contract import REMOTE


def build(root=ROOT, bundle=None):
    root = Path(root)
    require(root.resolve() == REMOTE, 'formal producer sealing requires exact remote root')
    require(not (root / 'deploy_manifest.json').exists(), 'producer already sealed')
    from preflight import check
    check(root, metadata_only=True)
    require(read(root / 'configs/runtime.json')['status'] == 'READY', 'actual runtime pending')
    from prelaunch_gates import check as check_gates
    gates = check_gates(root)
    from finalize_gpu_evidence import validate_capacity_record
    parent = read(root / 'prepared_parent/PARENT_BINDING.json')
    validate_capacity_record(read(root / 'audit/resource_admission.json'), sha(root / 'configs/protocol.json'), parent['parent_manifest_sha256'])
    from observer_import import t
    t.bindings(external=True)
    import service
    service.main_memory_profile()
    excluded = {'configs/admission.json', 'configs/queue.json', 'configs/runtime_provenance.json'}
    files = {}
    for folder in ('scripts', 'extensions', 'tests', 'configs', 'inputs', 'prepared_parent', 'candidate', 'operations_snapshot', 'source_snapshot'):
        for path in sorted((root / folder).rglob('*')):
            relative = str(path.relative_to(root))
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc' and relative not in excluded:
                require(not path.is_symlink(), 'sealed source must be ordinary file')
                files[relative] = file_record(path)
    for relative in ('analysis/postrun/export_case.py', 'analysis/postrun/release_prefix.py', 'analysis/postrun/build_metric_manifest.py',
                     'analysis/postrun/SOURCE_SCORE_BINDINGS.json', 'PROTOCOL.json',
                     'audit/OPERATION_SOURCE_INVENTORY.json', 'audit/ACTUAL_PARENT_BOUND.json',
                     'audit/GPU_EVIDENCE_BOUND.json', 'audit/gpu_dynamic_union_gate.json',
                     'audit/known_endpoint_90_gate.json', 'audit/resource_admission.json', 'audit/CPU_PREPARATION.json'):
        files[relative] = file_record(root / relative)
    for relative in ('prepare.py', 'run_probe.py', 'collect_evidence.py', 'capacity_entry.py',
                     'H3MainCapacityProbe/__init__.py', 'H3MainCapacityProbe/contract.py'):
        relative = 'audit/main_capacity_probe/' + relative
        files[relative] = file_record(root / relative)
    manifest = {'schema': 'r59-immutable-five-source-three-new-arm-producer-v1', 'files': files,
        'candidate_manifest_sha256': CANDIDATE_SHA, 'parent_manifest_sha256': parent['parent_manifest_sha256'],
        'protocol_sha256': sha(root / 'configs/protocol.json'), 'GPU_gates': gates,
        'mutable_administrative_files': sorted(excluded), 'new_jobs': 15, 'native_reuse': 'actual R57 P1 five outputs',
        'root_only_launch': True}
    write_new(root / 'deploy_manifest.json', manifest)
    write_new(root / 'ROOT_APPROVED_DEPLOYMENT.json', {'manifest_sha256': sha(root / 'deploy_manifest.json'),
        'candidate_manifest_sha256': CANDIDATE_SHA, 'parent_manifest_sha256': parent['parent_manifest_sha256'],
        'approval_scope': 'root reviewed actual GPU gates; live resource/process admission remains required'})
    if bundle:
        with tarfile.open(bundle, 'x:gz') as archive:
            for relative in files:
                if not relative.startswith(('inputs/', 'prepared_parent/inputs/')):
                    archive.add(root / relative, arcname=relative)
            for relative in ('deploy_manifest.json', 'ROOT_APPROVED_DEPLOYMENT.json', 'configs/admission.json', 'configs/queue.json'):
                archive.add(root / relative, arcname=relative)
    return {'manifest_sha256': sha(root / 'deploy_manifest.json'), 'files': len(files), 'new_jobs': 15}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path)
    args = parser.parse_args()
    print(json.dumps(build(bundle=args.bundle), indent=2))
