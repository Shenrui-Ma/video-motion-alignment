"""Verify the actual R57 archive and materialize small metadata/input dependencies.

Run on the archive-owning server after R57 completed. Existing candidate and
parent files remain immutable. Full condition/noise/endpoint files are hashed
in place; no duplicate tensor archive is made. This is not a GPU admission gate.
"""
import argparse
import copy
import importlib.util
import os
import shutil
import tempfile
from pathlib import Path
from execution_contract import (ROOT, CANDIDATE_SHA, SOURCES, PARENT_PRODUCER,
    require, read, sha, checked_file, safe, file_record, write_new,
    verify_candidate, verify_parent_anchors)


def inherited_intake(root):
    relative = 'operations_snapshot/r55/intake_parent_metadata.py'
    inventory = read(root / 'audit/OPERATION_SOURCE_INVENTORY.json')
    row = inventory[relative]
    require(file_record(root / relative) == {k: row[k] for k in ('bytes', 'sha256')}, 'inherited intake changed')
    spec = importlib.util.spec_from_file_location('r59_frozen_parent_intake', root / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect(archive, expected_manifest_sha, root=ROOT):
    root, archive = Path(root), Path(archive)
    protocol = verify_candidate(root)
    parents = [row for row in protocol['cases'] if row['arm'] == 'native']
    runs = [row['parent_run'] for row in parents]
    gate, runtime, inventory = verify_parent_anchors(archive, expected_manifest_sha, runs)
    bindings = read(root / 'candidate/configs/input_bindings.json')
    inputs = {}
    for name, record in bindings.items():
        path = checked_file(archive, 'inputs/' + name, inventory)
        require(file_record(path) == {k: record[k] for k in ('bytes', 'sha256')}, 'original source bytes differ')
        inputs[name] = file_record(path)
    require(len(inputs) == 20, 'five original source/working/provenance/prompt inputs required')
    inherited = inherited_intake(root)
    rows, tensor_files = [], {}
    for case in parents:
        template = read(root / 'candidate' / case['parent_planned_graph'])
        record = inherited.inspect_case(archive, case, template, inventory)
        require(not record['missing_metadata'], 'actual parent metadata pending: ' + case['source_id'])
        capture = read(record['files']['captures']['path'])
        condition = read(record['files']['conditioning']['path'])
        counts = runtime['runs'][case['parent_run']]
        expected_snapshots = {'audit/x0/' + case['parent_run'] + '/' + row['file'] for row in capture['captures'] + [capture['final_sampler_result']]}
        actual_snapshots = {}
        for row in counts['snapshots']:
            path = Path(row['file'])
            require(path.is_absolute() and path.is_relative_to(PARENT_PRODUCER), 'parent snapshot runtime root differs')
            relative = str(path.relative_to(PARENT_PRODUCER))
            require(relative not in actual_snapshots, 'duplicate actual snapshot')
            actual_snapshots[relative] = {k: row[k] for k in ('bytes', 'sha256')}
        require(set(actual_snapshots) == expected_snapshots and len(actual_snapshots) == 21, 'actual endpoint runtime inventory differs')
        require(all(inventory[name] == value for name, value in actual_snapshots.items()), 'runtime/archived endpoint bytes differ')
        require(len(record['tensor_inventory']) == 28, 'six condition blobs, initial noise and21 endpoints required')
        for name, value in record['tensor_inventory'].items():
            checked_file(archive, name, inventory)
            tensor_files[name] = value
        require(capture['sigmas_video'][-1] == 0.0 and len(capture['sigmas_video']) == 21, 'parent sigma grid differs')
        record.update(packed_layout=condition['packed_layout'], payload_bytes_reverified=True,
                      parent_archive=str(archive.resolve()), raw_tensor_recomputation='inherited R57 RUNTIME_GATE; file bytes reverified here')
        rows.append(record)
    return {'schema': 'r59-actual-parent-intake-v1', 'status': 'ACTUAL_PARENT_BYTES_VERIFIED',
            'candidate_manifest_sha256': CANDIDATE_SHA, 'parent_manifest_sha256': expected_manifest_sha,
            'parent_archive': str(archive.resolve()), 'archive_anchors': {name: sha(archive / name) for name in ('RUN_GATE.json', 'RUNTIME_GATE.json', 'FILE_INVENTORY.json', 'deploy_manifest.json')},
            'inputs': inputs, 'cases': rows, 'tensor_inventory': tensor_files,
            'GPU_launch_authorized': False, 'source_ids': list(SOURCES)}


def materialize(archive, expected_manifest_sha, root=ROOT):
    root, archive = Path(root), Path(archive)
    destination = root / 'prepared_parent'
    require(not destination.exists(), 'refuse to replace existing parent binding')
    result = inspect(archive, expected_manifest_sha, root)
    stage = Path(tempfile.mkdtemp(prefix='.parent-staging-', dir=root))
    try:
        files = {}
        def copy_file(source, relative):
            target = safe(stage, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            with Path(source).open('rb') as before, target.open('xb') as after:
                shutil.copyfileobj(before, after)
            require(file_record(source) == file_record(target), 'copy verification failed')
            files[relative] = file_record(target)
            return relative
        for name in result['archive_anchors']:
            copy_file(archive / name, 'archive/' + name)
        for name in result['inputs']:
            copy_file(archive / 'inputs' / name, 'inputs/' + name)
        mapped = {}
        for row in result['cases']:
            mapped[row['source_id']] = {}
            for key, record in row['files'].items():
                mapped[row['source_id']][key] = copy_file(record['path'], 'parents/' + row['source_id'] + '/' + key + '.json')
        result['materialized_files'] = files
        result['metadata_mapping'] = mapped
        result['tensor_storage'] = 'Original R57 archive remains the only tensor store; references retain absolute archive paths.'
        # Recheck immutable anchors after all copies, before the atomic publication.
        for name, digest in result['archive_anchors'].items():
            require(sha(archive / name) == digest, 'parent archive changed during materialization')
        write_new(stage / 'PARENT_BINDING.json', result)
        os.rename(stage, destination)
        return result
    except BaseException:
        # This directory was created by this call; keep partial evidence for inspection.
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--parent-manifest-sha', required=True)
    parser.add_argument('--materialize', action='store_true')
    args = parser.parse_args()
    result = (materialize if args.materialize else inspect)(args.archive, args.parent_manifest_sha)
    import json
    print(json.dumps({key: result[key] for key in ('status', 'source_ids', 'GPU_launch_authorized', 'parent_manifest_sha256')}, indent=2))
