"""Describe two frozen Attention probes after both endpoint gates pass.

CPU only. No threshold fitting, head selection, or statistical inference.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

HEADS = [0, 14, 28, 42]
METRICS = [
    'same_bin_mass', 'same_or_adjacent_bin_mass', 'entropy_nats',
    'expected_reference_center_minus_query_center_frames',
    'expected_interval_distance_frames',
]
NORM_KEYS = ['mass_weighted_readout_difference_l2',
             'mass_weighted_readout_difference_rms']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def as_array(tensor, shape):
    require(isinstance(tensor, torch.Tensor), 'expected saved tensor')
    value = tensor.detach().cpu().float().numpy()
    require(value.shape == shape and np.isfinite(value).all(), 'shape or finite check')
    return value


def frame_weights(intervals, region):
    a, b = region
    return np.asarray([max(0, min(v, b) - max(u, a) + 1)
                       for u, v in intervals], dtype=np.float64)


def weighted_mean(values, weights):
    require(values.shape[-1] == len(weights) and weights.sum() > 0,
            'invalid weighting')
    return (values * weights).sum(-1) / weights.sum()


def js_divergence(p, q):
    """Natural-log JS, retaining each fixed row; zero terms contribute zero."""
    mid = (p + q) / 2
    out = np.zeros(p.shape[:-1], dtype=np.float64)
    for x in (p, q):
        positive = x > 0
        term = np.zeros_like(x, dtype=np.float64)
        term[positive] = x[positive] * np.log(x[positive] / mid[positive])
        out += term.sum(-1) / 2
    return out


def bind_report(root, label, source, report, record, protocol_sha, source_sha):
    require(report['label'] == label and record['state'] == label,
            'state label mismatch')
    require(report['source_run'] == source['source_run'] and report['seed'] == source['seed']
            and report['raw_input_signature'] == source['raw_input']['packed_signature']
            and report['condition_sha256'] == source['condition']['sha256'],
            'source state mismatch')
    require(report['protocol_sha256'] == protocol_sha and
            report['source_binding_sha256'] == source_sha,
            'source/protocol seal mismatch')
    require(record['historical_endpoint_independently_exact'] is True and
            record['DiT_NFE'] == 1 and record['Euler_updates'] == 0,
            'independent endpoint gate incomplete')
    folder = root / 'audit' / 'probe' / label
    for filename, key in [('report.json', 'report_sha256'),
                          ('attention.pt', 'attention_sha256'),
                          ('endpoint_raw.pt', 'endpoint_sha256')]:
        path = folder / filename
        require(path.is_file() and not path.is_symlink() and digest(path) == record[key],
                'independent gate file binding failed: ' + filename)
    require(report['endpoint_sha256'] == record['endpoint_sha256'] and
            report['probe']['file_sha256'] == record['attention_sha256'],
            'report file bindings differ from independent gate')


def load_state(root, label, source, gate_record, protocol_sha, source_sha):
    folder = root / 'audit' / 'probe' / label
    report_file, pt = folder / 'report.json', folder / 'attention.pt'
    report = json.loads(report_file.read_text())
    bind_report(root, label, source, report, gate_record, protocol_sha, source_sha)
    require(report['status'] == 'complete' and report['DiT_NFE'] == 1,
            'complete single prediction required')
    require(report['Native_AV_bitwise_equal'] is True and
            report['input_sigma_grid_condition_RNG_unchanged'] is True,
            'restoration/endpoint gate failed')
    require(report['probe']['quality']['status'] == 'PASS', 'numerical gate failed')
    require(report['probe']['file_sha256'] == digest(pt), 'probe hash mismatch')
    for k in ['Euler_updates', 'ordinary_callbacks', 'VAE_calls', 'Qwen_calls', 'routed_calls']:
        require(report[k] == 0, k + ' must be zero')
    payload = torch.load(pt, map_location='cpu', weights_only=True)
    mapping = payload['mapping']
    require(mapping['heads'] == HEADS, 'head selection changed')
    require(len(mapping['queries']) == 1050, 'query count changed')
    queries = mapping['queries']
    expected_order = [(t, r, c) for t in range(42)
                      for r in [2, 6, 11, 16, 20] for c in [4, 12, 20, 28, 36]]
    require([(x['bin'], x['row'], x['col']) for x in queries] == expected_order,
            'query ordering changed')
    dist, desc = payload['distribution'], payload['descriptors']
    probability = as_array(dist['probabilities'], (1, 4, 1050, 42))[0].astype(np.float64)
    require((probability >= 0).all() and
            np.max(np.abs(probability.sum(-1) - 1)) <= 2e-5,
            'raw probability validation failed')
    fields = {k: as_array(desc[k], (1, 4, 1050))[0].reshape(4, 42, 25)
              for k in METRICS}
    for k in ['reference_mass'] + NORM_KEYS:
        fields[k] = as_array(dist[k], (1, 4, 1050))[0].reshape(4, 42, 25)
    record = {'report_path': str(report_file), 'report_sha256': digest(report_file),
              'attention_sha256': digest(pt), 'source_run': report['source_run'],
              'seed': report['seed'], 'protocol_sha256': report['protocol_sha256'],
              'DiT_NFE': 1, 'model_and_probe_seconds': report['model_and_probe_seconds_synchronized'],
              'probe_seconds': report['probe']['statistic_seconds_synchronized']}
    return mapping, fields, probability, record


def summarize(root, gate_file):
    gate = json.loads(gate_file.read_text())
    require(gate['passed'] is True and gate['total_DiT_NFE'] == 2 and
            gate['Euler_updates'] == gate['VAE_Qwen_calls'] == 0,
            'two-state independent gate required')
    require([x['state'] for x in gate['states']] == ['bad', 'normal'],
            'independent gate state inventory differs')
    protocol_file, source_file = root / 'configs/SCIENCE_PROTOCOL.json', root / 'configs/sources.json'
    protocol_sha, source_sha = digest(protocol_file), digest(source_file)
    frozen = json.loads(Path(__file__).with_name('PRE_SPEC_revision2.json').read_text())
    require(protocol_sha == frozen['producer_protocol_sha256'] and
            source_sha == frozen['producer_sources_sha256'], 'frozen producer identity differs')
    sources = json.loads(source_file.read_text())
    states = {label: load_state(root, label, sources[label], record, protocol_sha, source_sha)
              for label, record in zip(['bad', 'normal'], gate['states'])}
    mapping = states['bad'][0]
    require(states['normal'][0] == mapping, 'paired spatial/time mappings differ')
    require(states['normal'][3]['protocol_sha256'] == states['bad'][3]['protocol_sha256'],
            'protocol mismatch')
    intervals = mapping['frame_intervals']
    require(intervals[0][0] == 0 and intervals[-1][1] == 140 and
            all(b + 1 == c for (_, b), (c, _) in zip(intervals, intervals[1:])),
            'physical intervals differ')
    full = frame_weights(intervals, [0, 140])
    known = frame_weights(intervals, [44, 59])
    regions = {'full_0_140': full, 'previously_inspected_44_59': known,
               'remaining_physical_frames': full - known}
    result = {'schema': 'r46-descriptive-readout-v1',
              'scope': 'two correlated development states; fixed sampled spatial points; no calibrated motion lag',
              'heads': HEADS, 'frame_intervals': intervals, 'inputs': {}, 'states': {},
              'weighting': '25 fixed spatial points per bin; regional means weight nominal physical frame overlap',
              'interpretation': 'positive attention-center offset means future reference readout, not measured output delay; all heads retained'}
    result['independent_gate'] = {'path': str(gate_file), 'sha256': digest(gate_file),
                                  'resident': gate['resident']}
    for label, (_, fields, _, record) in states.items():
        result['inputs'][label] = record
        output = {'per_head_per_time_bin': {}, 'per_head_regions': {}}
        for name, values in fields.items():
            spatial_mean = values.mean(-1, dtype=np.float64)
            output['per_head_per_time_bin'][name] = spatial_mean.tolist()
            output['per_head_regions'][name] = {
                region: weighted_mean(spatial_mean, weights).tolist()
                for region, weights in regions.items()}
        result['states'][label] = output
    js = js_divergence(states['bad'][2], states['normal'][2]).reshape(4, 42, 25).mean(-1)
    result['paired_JS_nats'] = {'per_head_per_time_bin': js.tolist(),
        'per_head_regions': {name: weighted_mean(js, w).tolist() for name, w in regions.items()},
        'interpretation': 'same query grid across seeds; appearance/content changes can also cause differences'}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('capture_root', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--gate', type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'refuse to overwrite a previous interpretation')
    result = summarize(args.capture_root, args.gate or args.capture_root / 'analysis/READOUT_GATE.json')
    result['script_sha256'] = digest(Path(__file__))
    with args.output.open('x') as out:
        json.dump(result, out, ensure_ascii=False, indent=2, allow_nan=False)
        out.write('\n')
    print(json.dumps({'status': 'PASS', 'output': str(args.output),
                      'sha256': digest(args.output)}, ensure_ascii=False))
