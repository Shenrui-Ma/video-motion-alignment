"""Actual-input contract for fixed ten generated full158 pose extractions."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def save(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def expected_run(protocol, source, method):
    item = protocol['methods'][method]
    return item['run_prefix'] + '_source_' + source + '_seed2026101701_' + item['run_suffix']


def validate_metadata(protocol, source, method, metric, mapping):
    require(source in protocol['source_order'] and method in protocol['methods'], 'fixed ten cases only')
    item = protocol['pairs'][source]
    require(metric['source_id'] == source and metric['official_pair_id'] == item['pair_id'], 'source/pair identity')
    require(metric['run_id'] == expected_run(protocol, source, method), 'method/run identity')
    require(metric['original_source_sha256'] == item['original_source_sha256'] and metric['target_sha256'] == item['target_sha256'], 'official pair bytes')
    require(metric['source_frames'] == metric['output_frames'] == 49 and metric['source_fps'] == metric['output_fps'] == 8, 'release geometry')
    require(metric['source_size'] == [720, 480] and metric['output_size'] == [1152, 768], 'release size')
    indices = list(range(0, 147, 3))
    times = [i / 8 for i in range(49)]
    require(metric['source_indices'] == list(range(49)) and metric['full_output_indices'] == indices, '49 physical samples')
    require(metric['physical_seconds'] == times and all(math.isfinite(t) for t in metric['physical_seconds']), 'physical seconds')
    require(metric['padding_evaluated'] is False and metric['score_computed'] is False, 'separate score lane')
    require(mapping['input_indices'] == indices and mapping['physical_seconds'] == times, 'mapping samples')
    require(mapping['terminal_padding_excluded'] is True and mapping['decoded_frame_md5_equal'] is True, 'actual release gate')
    require(mapping['source'] == metric['full158_output'] and mapping['source_sha256'] == metric['full158_output_sha256'], 'mapping full158 identity')
    require(mapping['destination'] == metric['edited49'] and mapping['destination_sha256'] == metric['edited49_sha256'], 'mapping release49 identity')


def validate_paths(protocol, method, metric_path, mapping_path, metric):
    root = Path(protocol['methods'][method]['root_remote']).resolve()
    for path in (metric_path, mapping_path, metric['full158_output'], metric['edited49']):
        require(Path(path).is_absolute() and Path(path).resolve().is_relative_to(root), 'generated artifact outside method root')
    require(Path(metric_path).name == 'METRIC_INPUTS.json', 'actual postrun metric record')
    require(Path(mapping_path) == Path(metric['edited49']).with_suffix('.mapping.json'), 'actual release mapping path')


def source_helper(protocol):
    side = 'remote' if HERE == Path(protocol['root_remote']) else 'local'
    path = Path(protocol['source_helper'][side])
    require(sha(path) == protocol['source_helper']['sha256'], 'frozen source helper')
    spec = importlib.util.spec_from_file_location('source_pose_contract', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_pose_provenance(protocol, raw):
    p = raw['provenance']
    external = protocol['frozen_external']
    expected = {
        'script_sha256': next(h for n, h in external.items() if n.endswith('/pose_probe.py')),
        'detector_sha256': next(h for n, h in external.items() if n.endswith('/yolox_l.onnx')),
        'pose_sha256': next(h for n, h in external.items() if n.endswith('/dw-ll_ucoco_384_bs5.torchscript.pt')),
        'detector_code_sha256': next(h for n, h in external.items() if n.endswith('/cv_ox_det.py')),
        'pose_code_sha256': next(h for n, h in external.items() if n.endswith('/jit_pose.py')),
    }
    require(all(p[k] == v for k, v in expected.items()), 'raw probe/model provenance')


def check_freeze(protocol):
    freeze = read(HERE / 'FREEZE.json')
    for rel, digest in freeze['files'].items():
        require(sha(HERE / rel) == digest, 'generated sidecar code changed')
    require(sha(Path(protocol['source_helper']['remote' if HERE == Path(protocol['root_remote']) else 'local'])) == protocol['source_helper']['sha256'], 'source helper changed')
    return freeze
