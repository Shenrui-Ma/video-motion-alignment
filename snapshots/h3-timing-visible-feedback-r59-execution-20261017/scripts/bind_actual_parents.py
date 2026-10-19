"""Publish the actual completed R57 binding before root GPU gates, CPU only."""
import argparse
import copy
import json
import re
import shutil
from pathlib import Path
from execution_contract import ROOT, CANDIDATE_SHA, PARENT_PRODUCER, read, sha, require, file_record, write_new
from prepare_parent_binding import inspect, materialize
from r59_contract import REMOTE


def refresh_observer_bindings(root=ROOT):
    root = Path(root)
    bindings = read(root / 'configs/observer_external_bindings.json')
    excluded = {'configs/observer_bindings.json', 'configs/admission.json', 'configs/queue.json', 'configs/runtime_provenance.json'}
    bindings['local_files'] = {str(path.relative_to(root)): sha(path)
        for folder in ('scripts', 'extensions', 'configs') for path in sorted((root / folder).rglob('*'))
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc' and str(path.relative_to(root)) not in excluded}
    target = root / 'configs/observer_bindings.json'
    if target.exists():
        snapshot = root / 'audit/binding_revisions' / (sha(target) + '.json')
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if not snapshot.exists():
            shutil.copyfile(target, snapshot)
    target.write_text(json.dumps(bindings, indent=2) + '\n')
    return sha(target)


def binding_documents(root, binding):
    root = Path(root)
    protocol = read(root / 'configs/protocol.json')
    require(all(case['parent_status'] == 'PENDING' for case in protocol['cases']), 'already bound or partially bound producer')
    evidence = {row['source_id']: row for row in binding['cases']}
    closure = {'schema': 'r59-actual-R57-closure-v1', 'status': 'READY', 'ready': True,
               'candidate_manifest_sha256': CANDIDATE_SHA, 'cases': {}, 'GPU': 'new root capacity/runtime gates pending'}
    for case in protocol['cases']:
        source = case['source_id']
        mapping = binding['metadata_mapping'][source]
        for field, key in {'parent_graph': 'graph', 'parent_conditioning': 'conditioning', 'parent_noise': 'noise', 'parent_captures': 'captures'}.items():
            case[field] = 'prepared_parent/' + mapping[key]
        case.update(parent_status='READY', parent_root=binding['parent_archive'],
                    parent_graph_sha256=sha(root / case['parent_graph']),
                    parent_file_inventory='prepared_parent/archive/FILE_INVENTORY.json')
        required = ['prepared_parent/' + relative for relative in mapping.values()]
        required += ['prepared_parent/archive/' + name for name in binding['archive_anchors']]
        required.append(case['source_pose_path'])
        closure['cases'][source] = {'ready': True, 'parent_run': case['parent_run'],
            'required_actual_files': required, 'actual_file_sha256': {relative: sha(root / relative) for relative in required},
            'packed_layout': evidence[source]['packed_layout'], 'tensor_inventory': evidence[source]['tensor_inventory'],
            'source_pose_sha256': case['source_pose_sha256']}
    protocol['preparation_status'] = 'ACTUAL_R57_BOUND_ROOT_GPU_GATES_PENDING'
    protocol['prefix']['availability'] = 'Actual five R57 P1 Native histories and all21 endpoint files; current Native through first intervention inclusive.'
    return protocol, closure


def bind(archive, expected_manifest_sha, root=ROOT):
    root, archive = Path(root), Path(archive)
    require(root.resolve() == REMOTE and archive.resolve() == PARENT_PRODUCER / 'analysis/postrun/captured/batch', 'formal parent publication requires exact remote roots')
    require(not (root / 'deploy_manifest.json').exists(), 'cannot change sealed producer')
    prepared = root / 'prepared_parent/PARENT_BINDING.json'
    if not prepared.exists():
        materialize(archive, expected_manifest_sha, root)
    binding = read(prepared)
    actual = inspect(archive, expected_manifest_sha, root)
    require(binding['archive_anchors'] == actual['archive_anchors'] and binding['tensor_inventory'] == actual['tensor_inventory'], 'prepared parent archive changed')
    for relative, record in binding['materialized_files'].items():
        require(file_record(root / 'prepared_parent' / relative) == record, 'materialized parent file changed')
    protocol, closure = binding_documents(root, binding)
    for name in ('protocol.json', 'PARENT_CLOSURE.json', 'scientific_contract.json'):
        write_new(root / 'audit/pre_parent_binding' / name, read(root / 'configs' / name))
    # Preserve original source bytes in ordinary files expected by Comfy/postrun.
    (root / 'inputs').mkdir(exist_ok=False)
    for name, record in binding['inputs'].items():
        source = root / 'prepared_parent/inputs' / name
        destination = root / 'inputs' / name
        shutil.copyfile(source, destination)
        require(file_record(destination) == record, 'producer input copy changed')
    for relative, value in (('configs/protocol.json', protocol), ('configs/PARENT_CLOSURE.json', closure)):
        (root / relative).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    shutil.copyfile(root / 'configs/protocol.json', root / 'PROTOCOL.json')
    science = read(root / 'configs/scientific_contract.json')
    science.update(cases=protocol['cases'], status='ACTUAL_R57_BOUND_GPU_PENDING', paired_parent_status='READY')
    (root / 'configs/scientific_contract.json').write_text(json.dumps(science, indent=2, ensure_ascii=False) + '\n')
    path = root / 'extensions/H3AutomaticWindowRouter/transport.py'
    text, count = re.subn(r"^PROTOCOL_SHA='[0-9a-f]+'$", 'PROTOCOL_SHA=' + repr(sha(root / 'configs/protocol.json')), path.read_text(), flags=re.MULTILINE)
    require(count == 1, 'single protocol seal constant expected')
    path.write_text(text)
    digest = refresh_observer_bindings(root)
    write_new(root / 'audit/ACTUAL_PARENT_BOUND.json', {'status': 'READY', 'candidate_manifest_sha256': CANDIDATE_SHA,
        'parent_binding_sha256': sha(prepared), 'protocol_sha256': sha(root / 'configs/protocol.json'),
        'observer_bindings_sha256': digest, 'GPU_launch_authorized': False})
    return {'parent_sources': 5, 'registered_arms': 4, 'new_jobs': 15, 'GPU_launch_authorized': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--parent-manifest-sha', required=True)
    args = parser.parse_args()
    print(json.dumps(bind(args.archive, args.parent_manifest_sha), indent=2))
