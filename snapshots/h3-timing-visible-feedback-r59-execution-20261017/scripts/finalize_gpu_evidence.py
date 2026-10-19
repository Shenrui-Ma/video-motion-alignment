"""Bind new R59 P1 capacity evidence after root-controlled GPU checks."""
import argparse
import json
import shutil
from pathlib import Path
from execution_contract import ROOT, CANDIDATE_SHA, require, read, sha, write_new
from r59_contract import REMOTE
from bind_actual_parents import refresh_observer_bindings


def validate_capacity_record(record, protocol_sha, parent_manifest_sha):
    require(record.get('root_approved') is True, 'root capacity review pending')
    require(record.get('candidate_manifest_sha256') == CANDIDATE_SHA and record.get('protocol_sha256') == protocol_sha, 'capacity science binding differs')
    require(record.get('parent_manifest_sha256') == parent_manifest_sha, 'capacity P1 parent differs')
    require(record.get('capacity_scope') == 'R59 P1 Native plus same-state Full global27 all50blocks alpha1', 'P1 full-support capacity scope differs')
    for name in ('actual_native_prefix_equal_R57', 'full_forward_completed_50_blocks', 'input_sigma_condition_rng_equal', 'maximum_P1_sequence_case_measured'):
        require(record.get(name) is True, 'actual R59 capacity/numerical evidence missing: ' + name)
    require(isinstance(record.get('evidence'), list) and len(record['evidence']) >= 2, 'actual capacity evidence files required')
    for evidence in record['evidence']:
        require(sha(evidence['file']) == evidence['sha256'], 'capacity evidence changed')
    return True


def finalize(root=ROOT):
    root = Path(root)
    require(root.resolve() == REMOTE, 'actual GPU evidence belongs on exact remote root')
    require(not (root / 'deploy_manifest.json').exists(), 'producer already sealed')
    from preflight import check
    check(root, metadata_only=True)
    parent = read(root / 'prepared_parent/PARENT_BINDING.json')
    resource_path = root / 'audit/resource_admission.json'
    resource = read(resource_path)
    validate_capacity_record(resource, sha(root / 'configs/protocol.json'), parent['parent_manifest_sha256'])
    decoder_path = root / 'audit/known_endpoint_90_gate.json'
    decoder = read(decoder_path)
    require(decoder.get('passed') is True and decoder.get('protocol_sha256') == sha(root / 'configs/protocol.json'), 'new decoder evidence pending')
    require(decoder['decode']['decoded_shape'] == [90, 736, 1312, 3] and decoder['decode']['fps'] == 24, 'decoder geometry differs')
    for source, relative in ((decoder_path, 'configs/decoder_memory_evidence/full90_gate.json'), (resource_path, 'configs/main_memory_evidence/resource_admission.json')):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        require(not destination.exists(), 'capacity evidence already published')
        shutil.copyfile(source, destination)
    peak = decoder['decode']['max_memory_reserved_bytes']
    decoder_profile = {'schema': 'h3-decoder-memory-profile-v4', 'status': 'MEASURED',
        'geometry': {'fps': 24, 'frames': 90, 'height': 736, 'width': 1312},
        'bootstrap_required_free_bytes': 16 * 1024**3, 'safety_margin_bytes': 2 * 1024**3,
        'evidence_file': 'configs/decoder_memory_evidence/full90_gate.json', 'evidence_sha256': sha(decoder_path),
        'peak_reserved_bytes': peak, 'required_free_bytes': peak + 2 * 1024**3,
        'vae_sha256': decoder['decode']['vae_sha256']}
    main_profile = {'schema': 'h3-main-memory-profile-v4', 'status': 'MEASURED_BOUND',
        'evidence_file': 'configs/main_memory_evidence/resource_admission.json', 'evidence_sha256': sha(resource_path),
        'required_free_bytes': resource['main_estimated_peak_bytes'], 'scope': resource['capacity_scope']}
    for name, value in (('decoder_memory_profile.json', decoder_profile), ('main_memory_profile.json', main_profile)):
        write_new(root / 'audit/pre_measured_profiles' / name, read(root / 'configs' / name))
        (root / 'configs' / name).write_text(json.dumps(value, indent=2) + '\n')
    from prelaunch_gates import check as check_gates
    check_gates(root)
    import service
    service.main_memory_profile()
    runtime = read(root / 'configs/runtime.json')
    runtime['status'] = 'READY'
    (root / 'configs/runtime.json').write_text(json.dumps(runtime, indent=2) + '\n')
    digest = refresh_observer_bindings(root)
    write_new(root / 'audit/GPU_EVIDENCE_BOUND.json', {'status': 'READY', 'resource_sha256': sha(resource_path),
        'decoder_sha256': sha(decoder_path), 'observer_bindings_sha256': digest, 'formal_seal_and_live_admission_pending': True})
    return {'status': 'GPU_EVIDENCE_BOUND', 'formal_seal_and_live_admission_pending': True}


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(finalize(), indent=2))
