"""Collect one actually verified R76 pair, retaining its real provenance."""
import argparse
import shutil
from common import *

def validate_gate(gate, source):
    expected = entry(source)
    count, total = (expected['input_protocol'][key] for key in ('effective_frame_count', 'h3_frame_count'))
    require(gate.get('schema') == 'r76-paired-runtime-gate-v1' and gate.get('passed') is True and gate.get('source_id') == source and gate.get('prompt_version') == 'P1', 'actual R76 gate differs')
    checks = gate.get('checks', {})
    require(checks and all(value is True for value in checks.values()), 'actual pair gate contains unsuccessful checks')
    for key in ('producer_seal', 'actual_runtime_device', 'actual_clean_conditions_equal', 'actual_initial_AV_noise_equal', 'Native_prefix_0_5_equal'):
        require(checks.get(key) is True, 'pair gate check missing: ' + key)
    require(set(gate['runs']) == set(METHODS), 'both methods required')
    for method, run in gate['runs'].items():
        require(run['run_id'] == f'r76_{source}_seed2026101701_{method}' and run['valid_frames'] == count and run['NFE'] == run['Euler_updates'] == 20 and run['routed_blocks'] == (0 if method == 'native' else 450), 'actual run/validtime/route differs')
        prop = run['video']['properties']
        require(prop['width'] == 1312 and prop['height'] == 736 and int(prop['nb_read_frames']) == total and prop['avg_frame_rate'] == '24/1' and run['evaluation_crop_xywh'] == [16, 8, 1280, 720], 'actual geometry differs')
    return gate

def collect(producer, source):
    producer = Path(producer).resolve()
    receipt = producer / 'analysis/postrun' / source / 'PAIR_RUNTIME_GATE.json'
    gate = validate_gate(read(receipt), source)
    out = ROOT / 'incoming' / source
    require(not out.exists(), 'existing intake must be preserved')
    out.mkdir(parents=True)
    shutil.copy2(receipt, out / 'PAIR_RUNTIME_GATE.json')
    for method in METHODS:
        run = gate['runs'][method]
        video = Path(run['video']['file'])
        require(video.resolve().is_relative_to(producer / 'output') and sha(video) == run['video']['sha256'], 'actual video changed/outside producer')
        shutil.copy2(video, out / (method + '.mp4'))
        for kind, folder, digest_key in [('history', 'logs', 'history_sha256'), ('job', 'logs', 'job_sha256'), ('router', 'audit/router', 'router_file_sha256')]:
            name = run['run_id'] + ('.json' if kind == 'router' else '_' + kind + '.json')
            path = producer / folder / name
            require(sha(path) == run[digest_key], 'actual evidence changed: ' + kind)
            shutil.copy2(path, out / (method + '_' + kind + '.json'))
        shutil.copy2(producer / 'configs/graphs' / (run['run_id'] + '.json'), out / (method + '_graph.json'))
    save(out / 'COLLECTION.json', {'schema': 'r76-portable-actual-pair-v1', 'source': source, 'fixed_denominator': 5, 'producer': str(producer), 'receipt': bound(receipt), 'files': {path.name: sha(path) for path in out.iterdir() if path.is_file()}})
    return out

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--source', choices=PAIRS, required=True); p.add_argument('--producer-root', type=Path, required=True)
    a = p.parse_args(); verify_runtime(); print(collect(a.producer_root, a.source))
