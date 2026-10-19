"""Check immutable actual P1 parent closure, including source-only pose domains."""
from pathlib import Path
from execution_contract import ROOT, require, read, sha, file_record
from prepare_parent_binding import inspect


def check(root=ROOT, remote=False):
    root = Path(root)
    from observer_import import t
    from pose_domain import validate_pose
    t.require_parent_closure(root)
    binding = read(root / 'prepared_parent/PARENT_BINDING.json')
    for relative, record in binding['materialized_files'].items():
        require(file_record(root / 'prepared_parent' / relative) == record, 'prepared parent bytes changed')
    cases = read(root / 'configs/protocol.json')['cases']
    rows = []
    for case in [case for case in cases if case['arm'] == 'visible_only']:
        geometry = t.geometry_for(case['run_id'])
        pose = validate_pose(root / case['source_pose_path'], geometry)
        require(sha(root / case['source_pose_path']) == case['source_pose_sha256'] and pose['video']['sha256'] == case['video_sha256'], 'source pose/source video binding differs')
        rows.append({'source_id': case['source_id'], 'parent_run': case['parent_run'], 'valid_frames': case['valid_frame_count'], 'historical_endpoint_count': 21})
    if remote:
        actual = inspect(binding['parent_archive'], binding['parent_manifest_sha256'], root)
        require(actual['archive_anchors'] == binding['archive_anchors'] and actual['tensor_inventory'] == binding['tensor_inventory'], 'live actual parent archive differs')
    return {'passed': True, 'cases': rows, 'actual_archive_payloads_rehashed': remote}
