"""Independent CPU replay of actual clean inputs/noise and causal Native prefixes."""
from pathlib import Path
from execution_contract import PARENT_PRODUCER, require, read, sha, safe, file_record


def tensor_records(value, prefix=()):
    if isinstance(value, dict):
        if 'tensor_file' in value:
            yield prefix, value
        else:
            for key, child in value.items():
                yield from tensor_records(child, prefix + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from tensor_records(child, prefix + (index,))


def signature(tensor):
    from H3X0Readout.core import tensor_signature
    return {key: value for key, value in tensor_signature(tensor).items() if key != 'bytes'}


def checked_parent(case, inventory, relative):
    path = safe(Path(case['parent_root']), relative)
    require(relative in inventory and file_record(path) == inventory[relative], 'actual parent payload changed: ' + relative)
    return path


def compare_clean_inputs(root, case):
    import torch
    from H3AutomaticWindowRouter.pair_gate import condition_audit_matches
    root = Path(root)
    old = read(root / case['parent_conditioning'])
    current = read(root / 'audit' / (case['run_id'] + '_conditioning.json'))
    condition_audit_matches(current, old)
    inventory = read(root / case['parent_file_inventory'])
    left, right = dict(tensor_records(current)), dict(tensor_records(old))
    require(len(left) == len(right) == 6 and set(left) == set(right), 'six actual clean input tensors required')
    pairs = []
    for key in left:
        current_record, parent_record = left[key], right[key]
        current_file = safe(root / 'audit', current_record['tensor_file'])
        relative = 'audit/' + parent_record['tensor_file']
        parent_file = checked_parent(case, inventory, relative)
        current_tensor = torch.load(current_file, map_location='cpu', weights_only=True)
        parent_tensor = torch.load(parent_file, map_location='cpu', weights_only=True)
        expected = {k: parent_record[k] for k in ('shape', 'dtype', 'sha256')}
        require(isinstance(current_tensor, torch.Tensor) and isinstance(parent_tensor, torch.Tensor), 'clean tensor payload schema')
        require(signature(current_tensor) == signature(parent_tensor) == expected, 'actual clean tensor signature differs: ' + str(key))
        require(torch.equal(current_tensor, parent_tensor), 'actual clean tensor values differ: ' + str(key))
        pairs.append({'field': '/'.join(map(str, key)), 'current': str(current_file), 'parent': str(parent_file),
                      'current_file_sha256': sha(current_file), 'parent_file_sha256': inventory[relative]['sha256'],
                      'tensor_equal': True})
        del current_tensor, parent_tensor
    current_noise = read(root / 'audit' / (case['run_id'] + '_noise.json'))
    parent_noise = read(root / case['parent_noise'])
    require(current_noise['signature'] == parent_noise['signature'] and current_noise['signature']['seed'] == case['seed'], 'actual noise metadata differs')
    current_noise_path = Path(current_noise['cache_file'])
    require(current_noise_path == root / 'audit' / 'r73_short_0252_seed2026101701_noise.pt', 'current noise cache identity differs')
    parent_original = Path(parent_noise['cache_file'])
    require(parent_original.is_relative_to(PARENT_PRODUCER), 'parent noise original root differs')
    relative = str(parent_original.relative_to(PARENT_PRODUCER))
    parent_noise_path = checked_parent(case, inventory, relative)
    current_payload = torch.load(current_noise_path, map_location='cpu', weights_only=True)
    parent_payload = torch.load(parent_noise_path, map_location='cpu', weights_only=True)
    require(current_payload['signature'] == parent_payload['signature'] == current_noise['signature'], 'noise archive signature differs')
    require(len(current_payload['tensors']) == len(parent_payload['tensors']) == 2, 'video/audio noise pair required')
    for index, (current_tensor, parent_tensor) in enumerate(zip(current_payload['tensors'], parent_payload['tensors'])):
        expected = parent_noise['actual_noise_streams'][index]
        require(signature(current_tensor) == signature(parent_tensor) == expected == current_noise['actual_noise_streams'][index], 'initial noise stream signature differs')
        require(current_payload['hashes'][index] == parent_payload['hashes'][index] == expected and torch.equal(current_tensor, parent_tensor), 'actual initial noise tensor differs')
    return {'clean_tensor_pairs': pairs, 'actual_clean_inputs_equal': True, 'initial_video_audio_noise_equal': True,
            'initial_noise_files': {'current': str(current_noise_path), 'parent': str(parent_noise_path),
                'current_sha256': sha(current_noise_path), 'parent_sha256': inventory[relative]['sha256']}}


def compare_prefix(case, inventory, parent_capture, index, current):
    """Caller invokes only for Native n <= first actual Full (inclusive)."""
    import torch
    from H3X0Readout.core import tensor_signature
    require(parent_capture['step_zero_based'] == index, 'parent endpoint step differs')
    relative = 'audit/x0/' + case['parent_run'] + '/' + parent_capture['file']
    parent_file = checked_parent(case, inventory, relative)
    parent = torch.load(parent_file, map_location='cpu', weights_only=True)
    for key in ('video', 'audio'):
        require(tensor_signature(parent[key]) == parent_capture[key], 'historical endpoint tensor signature changed')
        require(torch.equal(parent[key], current[key]), 'independent actual Native prefix differs')
    return {'physical_index': index, 'parent_file': str(parent_file),
            'parent_file_sha256': inventory[relative]['sha256'], 'actual_video_audio_tensor_equal': True}
