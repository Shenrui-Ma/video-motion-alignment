"""CPU-only, read-only input audit for possible reuse of archived Sam05 x3.

Writes only beside this file. Never calls SSH, CUDA, ComfyUI, or a model.
Run again after the new full native output and its audit/history arrive.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import time

OLD = Path('/Users/researcher/DevProjects/h3-sam-real-dance-batch-20261015')
NEW = Path('/Users/researcher/DevProjects/h3-timing-autoresearch-20261016')
OUT = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256')
    return digest.hexdigest()


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def strip_blob_paths(value):
    if isinstance(value, dict):
        return {key: strip_blob_paths(item) for key, item in value.items() if key != 'tensor_file'}
    if isinstance(value, list):
        return [strip_blob_paths(item) for item in value]
    return value


def condition_signature(value):
    fields = ['prompt', 'input_video', 'native_vae_calls', 'qwen_presentation',
              'tokenization_before_vision_expansion', 'conditioning_embedding',
              'token_tags', 'target_latent_shapes', 'packed_layout']
    result = {key: strip_blob_paths(value[key]) for key in fields}
    snapshot = value['pair_snapshot']
    if snapshot.get('verified') is not True:
        raise ValueError('Per-run actual conditioning snapshot was not verified')
    result['actual_snapshot'] = snapshot['actual']
    return result


def graph_signature(value, normalize_native=False):
    result = copy.deepcopy(value)
    admin = {'5': ['audit_dir', 'run_id'], '6': ['audit_dir', 'run_id', 'pair_id'],
             '14': ['filename_prefix'], '50': ['audit_dir', 'run_id'],
             '51': ['source_audit_dir', 'source_run_id', 'run_id']}
    for node, keys in admin.items():
        for key in keys:
            result[node]['inputs'].pop(key, None)
    if normalize_native:
        patch = result['50']
        native = (patch['class_type'] == 'H3EventEmphasis' and patch['inputs'].get('factor') == 1)
        native |= (patch['class_type'] == 'H3TemporalRouter' and patch['inputs'].get('mode') == 'native')
        if not native:
            raise ValueError('Expected an explicitly inactive/native intervention')
        result['50'] = {'class_type': 'REVIEW_ONLY_NATIVE_EQUIVALENCE', 'inputs': {
            key: patch['inputs'][key] for key in ('model', 'positive')}}
    return result


def video_fingerprint(path, label):
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(path),
               '-map', '0:v:0', '-an', '-pix_fmt', 'rgb24', '-fps_mode', 'passthrough',
               '-f', 'framemd5', '-']
    text = subprocess.check_output(command, text=True, timeout=60)
    (OUT / (label + '.framemd5')).write_text(text)
    records = [row.strip() for row in text.splitlines() if row and not row.startswith('#')]
    metadata = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
        'stream=width,height,pix_fmt,avg_frame_rate,nb_frames,duration,color_space,color_range',
        '-of', 'json', str(path)], text=True, timeout=30))['streams'][0]
    return {'path': str(path), 'file_sha256': sha(path), 'ffprobe': metadata,
            'decoded_rgb24_frame_count': len(records), 'decoded_rgb24_records': records,
            'frame_record_sha256': canonical_hash(records), 'framemd5_path': str(OUT / (label + '.framemd5'))}


def raw_tensor_checks(condition, noise):
    import torch
    checks = []
    cache = OLD / 'audit' / Path(noise['cache_file']).name
    saved = torch.load(cache, map_location='cpu', weights_only=True)
    actual = []
    for tensor in saved['tensors']:
        tensor = tensor.detach().cpu().contiguous()
        actual.append({'shape': list(tensor.shape), 'dtype': str(tensor.dtype),
                       'sha256': hashlib.sha256(tensor.view(torch.uint8).numpy().data).hexdigest()})
    checks.append({'kind': 'noise_cache', 'path': str(cache), 'file_sha256': sha(cache),
                   'signature_matches': saved['signature'] == noise['signature'],
                   'runtime_hashes_recomputed': actual == noise['actual_noise_streams'], 'actual': actual})
    for call_index, call in enumerate(condition['native_vae_calls']):
        info = call['latent']
        path = OLD / 'audit' / info['tensor_file']
        row = {'kind': 'reference_clean_latent', 'call_index': call_index, 'path': str(path),
               'available_locally': path.exists(), 'expected': strip_blob_paths(info)}
        if path.exists():
            tensor = torch.load(path, map_location='cpu', weights_only=True).contiguous()
            actual = {'shape': list(tensor.shape), 'dtype': str(tensor.dtype),
                      'sha256': hashlib.sha256(tensor.view(torch.uint8).numpy().data).hexdigest()}
            row.update(actual=actual, runtime_hash_recomputed=actual == strip_blob_paths(info))
        checks.append(row)
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--new-run', default='s05_full_seed1_native')
    args = parser.parse_args()
    evidence = {'schema': 'h3-archived-pair-reuse-v1', 'checked_unix': time.time(),
                'new_run': args.new_run, 'scope': 'Local CPU/file audit; no new inference', 'old': {}}
    old_conditions, old_noises, old_graphs = {}, {}, {}
    for arm in ('baseline', 'weight3'):
        run = '05_sam_s1_' + arm
        graph_path = OLD / ('remote_configs/' + run + '.json')
        graph = load(graph_path)
        job = load(OLD / ('logs/' + run + '_job.json'))
        history = load(OLD / ('logs/' + run + '_history.json'))
        condition = load(OLD / ('audit/' + run + '_conditioning.json'))
        noise = load(OLD / ('audit/' + run + '_noise.json'))
        emphasis = load(OLD / ('audit/emphasis/' + run + '.json'))
        old_conditions[arm], old_noises[arm], old_graphs[arm] = condition, noise, graph
        evidence['old'][arm] = {
            'graph_path': str(graph_path), 'graph_sha256': sha(graph_path),
            'graph_hash_matches_execution_job': sha(graph_path) == job['graph_sha256'],
            'graph_equals_executed_history': graph == history['prompt'][2],
            'history_completed_successfully': history['status']['completed'] and history['status']['status_str'] == 'success',
            'cached_nodes': [node for event, payload in history['status']['messages'] if event == 'execution_cached'
                             for node in payload['nodes']],
            'condition_signature_sha256': canonical_hash(condition_signature(condition)),
            'actual_condition_snapshot': condition['pair_snapshot']['actual'],
            'noise_signature': noise['signature'], 'actual_noise_streams': noise['actual_noise_streams'],
            'completed_calls': emphasis['completed_calls'], 'completed_forwards': emphasis['completed_forward_calls'],
            'factor': emphasis['factor'], 'layout': emphasis['validated_layout'],
            'sample_sigmas': emphasis['sample_sigmas'],
            'video': video_fingerprint(OLD / ('outputs/' + run + '_00001_.mp4'), 'old_' + arm)}
    evidence['old_pair_same_condition'] = condition_signature(old_conditions['baseline']) == condition_signature(old_conditions['weight3'])
    evidence['old_pair_same_noise'] = all(old_noises['baseline'][key] == old_noises['weight3'][key]
                                        for key in ('signature', 'actual_noise_streams'))
    evidence['raw_tensor_checks'] = raw_tensor_checks(old_conditions['baseline'], old_noises['baseline'])
    evidence['stored_noise_and_available_latent_hashes_reverified'] = all(
        (row['signature_matches'] and row['runtime_hashes_recomputed']) if row['kind'] == 'noise_cache'
        else row.get('runtime_hash_recomputed', not row['available_locally'])
        for row in evidence['raw_tensor_checks'])
    evidence['inputs'] = []
    for name in ('05_real_megumi_v.mp4', 'sam_altman_village_global_20221117_original.jpg'):
        a, b = OLD / 'inputs' / name, NEW / 'inputs' / name
        evidence['inputs'].append({'name': name, 'old_sha256': sha(a), 'new_sha256': sha(b), 'equal': sha(a) == sha(b)})
    evidence['code_comparison'] = []
    for name in ('H3EventEmphasis/core.py', 'H3EventEmphasis/__init__.py', 'H3PairAudit/__init__.py', 'H3EventAudit/__init__.py'):
        a, b = OLD / 'remote_extensions' / name, NEW / 'extensions' / name
        normalized_equal = a.read_text().replace('sam_real_dance_batch_20261015', 'timing_autoresearch_20261016') == b.read_text()
        evidence['code_comparison'].append({'name': name, 'old_sha256': sha(a), 'new_sha256': sha(b),
                                             'exact_equal': sha(a) == sha(b), 'equal_after_task_directory_literal_normalization': normalized_equal})
    for name in ('compatibility_bootstrap.py', 'int8_row_chunking.py'):
        a, b = OLD / 'scripts' / name, NEW / 'scripts' / name
        evidence['code_comparison'].append({'name': 'scripts/' + name, 'old_sha256': sha(a), 'new_sha256': sha(b), 'exact_equal': sha(a) == sha(b)})
    evidence['core_manifest_equal'] = load(OLD / 'configs/parent_core_hashes.json') == load(NEW / 'configs/parent_core_hashes.json')
    evidence['model_manifest_equal'] = load(OLD / 'configs/model_hashes_host9.json') == load(NEW / 'configs/model_hashes_host9.json')
    old_runtime = load(OLD / 'remote_configs/runtime_provenance.json')
    evidence['old_runtime_provenance_path'] = str(OLD / 'remote_configs/runtime_provenance.json')
    evidence['old_code_matches_recorded_execution_provenance'] = all(
        row['old_sha256'] == old_runtime['code'][row['name'] if row['name'].startswith('scripts/')
                                                    else 'extensions/' + row['name']]
        for row in evidence['code_comparison'])
    evidence['old_recorded_core_matches_all_true'] = all(old_runtime['core_matches'].values())
    new_graph = load(NEW / ('configs/' + args.new_run + '.json'))
    new_x3_graph = load(NEW / 'configs/s05_full_seed1_weight3.json')
    evidence['new_native_scientific_graph_equal_after_inactive_patch_normalization'] = graph_signature(old_graphs['baseline'], True) == graph_signature(new_graph, True)
    evidence['new_x3_scientific_graph_equal'] = graph_signature(old_graphs['weight3']) == graph_signature(new_x3_graph)
    evidence['graph_normalization_note'] = 'Only audit/run/output/cache IDs removed; native factor1 and router mode=native normalized as inactive. ImageScale or any changed scientific field remains a mismatch.'
    evidence['pending_new_paths'] = []
    paths = {kind: NEW / path for kind, path in {
        'video': 'outputs/' + args.new_run + '_00001_.mp4',
        'condition': 'audit/' + args.new_run + '_conditioning.json',
        'noise': 'audit/' + args.new_run + '_noise.json',
        'history': 'logs/' + args.new_run + '_history.json'}.items()}
    for kind, path in paths.items():
        if not path.exists():
            evidence['pending_new_paths'].append(str(path))
    evidence['reuse_status'] = 'pending_new_native_replication'
    evidence['eligible_as_reused_paired_control'] = False
    if not evidence['pending_new_paths']:
        condition, noise, history = load(paths['condition']), load(paths['noise']), load(paths['history'])
        video = video_fingerprint(paths['video'], 'new_full_native')
        evidence['new_replication'] = {
            'condition_signature_equal': condition_signature(condition) == condition_signature(old_conditions['baseline']),
            'actual_noise_equal': all(noise[key] == old_noises['baseline'][key] for key in ('signature', 'actual_noise_streams')),
            'history_graph_equals_reviewed_graph': history['prompt'][2] == new_graph,
            'completed_successfully': history['status']['completed'] and history['status']['status_str'] == 'success',
            'decoded_video_equal': video['decoded_rgb24_records'] == evidence['old']['baseline']['video']['decoded_rgb24_records'],
            'video': video}
        old_ok = all(value['graph_hash_matches_execution_job'] and value['graph_equals_executed_history']
                     and value['history_completed_successfully'] and value['completed_calls'] == 1000
                     and value['completed_forwards'] == 20 for value in evidence['old'].values())
        old_ok &= evidence['old_pair_same_condition'] and evidence['old_pair_same_noise']
        checks = evidence['new_replication']
        new_ok = all(checks[key] for key in ('condition_signature_equal', 'actual_noise_equal',
                     'history_graph_equals_reviewed_graph', 'completed_successfully', 'decoded_video_equal'))
        static_ok = all(evidence[key] for key in ('core_manifest_equal', 'model_manifest_equal',
                         'new_native_scientific_graph_equal_after_inactive_patch_normalization', 'new_x3_scientific_graph_equal',
                         'stored_noise_and_available_latent_hashes_reverified',
                         'old_code_matches_recorded_execution_provenance', 'old_recorded_core_matches_all_true'))
        static_ok &= all(row['equal'] for row in evidence['inputs'])
        static_ok &= all(row.get('equal_after_task_directory_literal_normalization', row['exact_equal']) for row in evidence['code_comparison'])
        evidence['eligible_as_reused_paired_control'] = bool(old_ok and new_ok and static_ok)
        evidence['reuse_status'] = ('eligible_with_explicit_archive_provenance' if evidence['eligible_as_reused_paired_control']
                                    else 'not_eligible_replication_mismatch')
    evidence['qualifications'] = [
        'Even if eligible, this is reused archived x3, not a newly executed arm, independent seed, or fresh speed measurement.',
        'Decoded MP4 equality verifies identical displayed frames but does not prove identical uncompressed latent trajectories.',
        'Conditioning/noise hashes and original successful execution evidence must pass together; visual similarity or same seed alone is insufficient.',
        'Model file identities use prior full hashes plus archived size/mtime evidence, not a new full checkpoint hash sweep.',
        'Current core/model manifests are inherited records, not a new remote hash sweep. Root must retain its current runtime preflight evidence and recheck if shared files/packages changed.',
        'Old per-run snapshot records clean references, not every noisy reference tensor. Same seed/native model source implies deterministic augmentation; do not claim every internal tensor was independently rehashed.',
        'Native routing has observational readouts absent from the archived baseline; timing overhead is not comparable.',
        'Full87592-token default-backend profiler was not rerun in this CPU-only review;1024-shape backend test alone is not that proof.',
        'If any gate differs, retain archived results only as historical evidence and rerun x3 for a strict new paired comparison.'
    ]
    path = OUT / 'archived_pair_reuse_audit.json'
    path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'path': str(path), 'reuse_status': evidence['reuse_status'],
                      'old_pair_same_condition': evidence['old_pair_same_condition'],
                      'old_pair_same_noise': evidence['old_pair_same_noise'],
                      'new_native_graph_equal': evidence['new_native_scientific_graph_equal_after_inactive_patch_normalization'],
                      'new_x3_graph_equal': evidence['new_x3_scientific_graph_equal'],
                      'pending_new_paths': evidence['pending_new_paths']}))


if __name__ == '__main__':
    main()
