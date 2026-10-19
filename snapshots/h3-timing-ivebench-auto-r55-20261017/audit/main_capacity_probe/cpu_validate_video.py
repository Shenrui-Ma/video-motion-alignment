"""Run the actual installed LoadVideo schema/validation with CUDA hidden."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.run_root.resolve()
    config = json.loads((root / 'configs/probe.json').read_text())
    core = Path(config['runtime']['core'])
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    sys.path.insert(0, config['runtime']['dependencies'])
    sys.path.insert(0, str(core))
    # Set CPU before importing the actual node and its Comfy API dependencies.
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    import folder_paths
    folder_paths.set_input_directory(str(root / 'input'))
    from comfy_extras.nodes_video import LoadVideo
    import torch
    graph = json.loads((root / 'configs/graph.json').read_text())
    filename = graph['22']['inputs']['file']
    video = root / 'input' / filename
    if not video.is_file() or video.is_symlink():
        raise ValueError('input must be a byte-checked regular file')
    schema = LoadVideo.define_schema()
    validation = LoadVideo.validate_inputs(filename)
    if validation is not True:
        raise ValueError(str(validation))
    schema_file = next(row for row in schema.inputs if row.id == 'file')
    if filename not in schema_file.options:
        raise ValueError('input absent from actual LoadVideo schema')
    if torch.cuda.is_initialized():
        raise ValueError('CPU validation unexpectedly initialized CUDA')
    report = {
        'status': 'ACTUAL_LOADVIDEO_SCHEMA_AND_VALIDATION_PASS',
        'run_root': str(root), 'file': filename,
        'video_sha256': hashlib.sha256(video.read_bytes()).hexdigest(),
        'validator_source_sha256': hashlib.sha256((core / 'comfy_extras/nodes_video.py').read_bytes()).hexdigest(),
        'folder_paths_source_sha256': hashlib.sha256((core / 'folder_paths.py').read_bytes()).hexdigest(),
        'in_schema': True, 'validation': True,
        'cuda_initialized': False, 'validation_device': 'cpu',
    }
    with (root / 'audit/cpu_node_schema.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
