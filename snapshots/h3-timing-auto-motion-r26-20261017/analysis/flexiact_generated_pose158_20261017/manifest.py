"""Fixed denominator ten; explicit pending records until actual products exist."""
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location('generated_pose158_receipt_contract', Path(__file__).with_name('contract.py'))
_contract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_contract)
HERE = _contract.HERE
sha, read, require, save = _contract.sha, _contract.read, _contract.require, _contract.save
validate_metadata, validate_paths = _contract.validate_metadata, _contract.validate_paths
source_helper, validate_pose_provenance = _contract.source_helper, _contract.validate_pose_provenance
check_freeze = _contract.check_freeze

PATH_FIELDS = ('pose_path', 'pose_sha256', 'full158_path', 'full158_sha256', 'metric_inputs_path', 'metric_inputs_sha256', 'release49_mapping_path', 'release49_mapping_sha256', 'extraction_complete_path', 'extraction_complete_sha256', 'provenance_path', 'provenance_sha256')


def verify_complete_identity(complete, source, method, pair, freeze_sha):
    require(complete['status'] == 'complete' and complete['source_id'] == source and complete['method'] == method and complete['pair_id'] == pair and complete['code_freeze_sha256'] == freeze_sha, 'completion identity')


def verified_record(protocol, source, method):
    base = {'source_id': source, 'pair_id': protocol['pairs'][source]['pair_id'], 'method': method, 'status': 'pending', **{key: None for key in PATH_FIELDS}, 'local_paths': {}, 'valid_observation_frames': [0, 146], 'padding_frames': [147, 157], 'original_sample_indices': list(range(0, 147, 3))}
    folder = HERE / 'records' / (method + '_' + source)
    if not folder.exists():
        return base
    if not (folder / 'COMPLETE.json').exists():
        base.update(status='technical_incomplete', reason='partial extraction; requires review')
        return base
    complete = read(folder / 'COMPLETE.json')
    verify_complete_identity(complete, source, method, base['pair_id'], sha(HERE / 'FREEZE.json'))
    require({p.name for p in folder.iterdir()} == set(complete['files']) | {'COMPLETE.json'}, 'exact extraction inventory')
    for name, digest in complete['files'].items():
        require(sha(folder / name) == digest, 'extraction byte identity')
    binding, provenance = read(folder / 'INPUT_BINDING.json'), read(folder / 'PROVENANCE.json')
    for row in (binding, provenance):
        require((row['pair_id'], row['source_id'], row['method']) == (base['pair_id'], source, method), 'record identity')
        require(row['code_freeze_sha256'] == sha(HERE / 'FREEZE.json'), 'record code identity')
    require(provenance['protocol_sha256'] == sha(HERE / 'PROTOCOL.json'), 'record protocol identity')
    metric, mapping = read(folder / 'METRIC_INPUTS.json'), read(folder / 'release49.mapping.json')
    validate_metadata(protocol, source, method, metric, mapping)
    validate_paths(protocol, method, binding['metric_inputs_path'], binding['release49_mapping_path'], metric)
    require(binding['run_id'] == metric['run_id'], 'bound run identity')
    require(binding['full158_path'] == metric['full158_output'] and binding['full158_sha256'] == metric['full158_output_sha256'], 'bound full158')
    expected_inputs = {binding['metric_inputs_path']: sha(folder / 'METRIC_INPUTS.json'), binding['release49_mapping_path']: sha(folder / 'release49.mapping.json'), str(Path(binding['metric_inputs_path']).parent / 'CASE_FILES.json'): sha(folder / 'PARENT_CASE_FILES.json'), metric['full158_output']: metric['full158_output_sha256'], metric['edited49']: metric['edited49_sha256'], metric['original_source']: metric['original_source_sha256'], metric['target_image']: metric['target_sha256']}
    require(binding['actual_inputs'] == expected_inputs, 'complete actual parent inventory identity')
    parent_files = read(folder / 'PARENT_CASE_FILES.json')
    for path, copied in ((binding['metric_inputs_path'], 'METRIC_INPUTS.json'), (binding['release49_mapping_path'], 'release49.mapping.json')):
        require(parent_files[str(Path(path).relative_to(Path(binding['metric_inputs_path']).parent))] == sha(folder / copied), 'parent case completion identity')
    require(provenance['input_binding_sha256'] == sha(folder / 'INPUT_BINDING.json'), 'provenance binding')
    remote_folder = Path(protocol['root_remote']) / 'records' / (method + '_' + source)
    pose = folder / Path(provenance['pose_path']).name
    require(provenance['pose_path'] == str(remote_folder / pose.name) and provenance['pose_sha256'] == sha(pose), 'pose identity')
    raw = source_helper(protocol).validate_pose(read(pose), metric['full158_output_sha256'], protocol)
    validate_pose_provenance(protocol, raw)
    require(provenance['raw_provenance'] == raw['provenance'] and provenance['statistics'] == raw['statistics'], 'raw pose provenance/statistics identity')
    base.update(status='complete', pose_path=provenance['pose_path'], pose_sha256=sha(pose), full158_path=binding['full158_path'], full158_sha256=binding['full158_sha256'], metric_inputs_path=binding['metric_inputs_path'], metric_inputs_sha256=sha(folder / 'METRIC_INPUTS.json'), release49_mapping_path=binding['release49_mapping_path'], release49_mapping_sha256=sha(folder / 'release49.mapping.json'), extraction_complete_path=str(remote_folder / 'COMPLETE.json'), extraction_complete_sha256=sha(folder / 'COMPLETE.json'), provenance_path=str(remote_folder / 'PROVENANCE.json'), provenance_sha256=sha(folder / 'PROVENANCE.json'), extraction=protocol['extraction'], geometry=protocol['geometry'], probe_and_models=raw['provenance'], elapsed_seconds=provenance['elapsed_seconds'], local_paths={'pose': str(pose), 'provenance': str(folder / 'PROVENANCE.json'), 'extraction_complete': str(folder / 'COMPLETE.json'), 'metric_inputs': str(folder / 'METRIC_INPUTS.json'), 'release49_mapping': str(folder / 'release49.mapping.json'), 'input_binding': str(folder / 'INPUT_BINDING.json')})
    return base


def compare_supplied_record(record, actual):
    require(record.get('status') == actual.get('status') == 'complete', 'complete generated pose required')
    # Download locations vary by host. All scoring identity and scientific fields
    # remain identical to the receipt re-derived from actual remote products.
    require({k: v for k, v in record.items() if k != 'local_paths'} == {k: v for k, v in actual.items() if k != 'local_paths'}, 'manifest differs from verified actual receipt')
    return actual


def verify_supplied_record(record):
    """Pure stdlib intake: actual files and seal; returns verified remote record."""
    protocol = read(HERE / 'PROTOCOL.json')
    check_freeze(protocol)
    require(record['source_id'] in protocol['source_order'] and record['method'] in protocol['methods'], 'fixed ten identity')
    actual = verified_record(protocol, record['source_id'], record['method'])
    return compare_supplied_record(record, actual)


def assemble():
    protocol = read(HERE / 'PROTOCOL.json')
    check_freeze(protocol)
    records = [verified_record(protocol, source, method) for source in protocol['source_order'] for method in protocol['methods']]
    done = sum(row['status'] == 'complete' for row in records)
    result = {'schema': protocol['schema'], 'status': 'complete' if done == 10 else 'pending', 'expected_count': 10, 'completed_count': done, 'records': records, 'protocol_sha256': sha(HERE / 'PROTOCOL.json'), 'code_freeze_sha256': sha(HERE / 'FREEZE.json'), 'scope': protocol['scope'], 'scores_computed': False}
    save(HERE / 'MANIFEST.json', result)
    print(json.dumps({'status': result['status'], 'complete': done, 'expected': 10, 'manifest_sha256': sha(HERE / 'MANIFEST.json')}))


if __name__ == '__main__': assemble()
