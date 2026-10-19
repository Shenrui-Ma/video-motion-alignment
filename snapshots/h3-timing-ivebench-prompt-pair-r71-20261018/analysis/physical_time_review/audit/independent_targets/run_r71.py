"""Supplement legacy results from existing poses; no pose/model execution."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time

os.environ['CUDA_VISIBLE_DEVICES'] = ''
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'vendor/physical'))
import evaluate90
from adapter import independent_targets


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    protocol = read(ROOT / 'PROTOCOL.json')
    for item in protocol['bindings']:
        assert sha(ROOT / item['relative']) == item['sha256'], item['relative']
    source = ROOT / 'poses/source.pose.json'
    assert sha(source) == protocol['source_pose']['sha256']
    targets = {}
    for arm in ('p0', 'p1'):
        path = ROOT / 'poses' / arm / (arm + '.pose.json')
        receipt = read(path.parent / 'COMPLETE.json')
        assert receipt['status'] == 'complete'
        assert receipt['pose_sha256'] == sha(path)
        assert receipt['protocol_sha256'] == sha(ROOT / 'PROTOCOL.json')
        targets[arm] = path
    start = time.monotonic()
    result = independent_targets(evaluate90.evaluate, read(source),
                                 {key: read(path) for key, path in targets.items()}, 'short_0210')
    output = {'schema': 'r71-independent-target-physical-supplement-v1',
              'result': result, 'protocol_sha256': sha(ROOT / 'PROTOCOL.json'),
              'source_pose_sha256': sha(source),
              'target_pose_sha256': {key: sha(path) for key, path in targets.items()},
              'legacy_output_sha256': sha(ROOT / 'results/physical_original.json.gz'),
              'adapter_sha256': sha(Path(__file__).with_name('adapter.py')),
              'cpu_seconds': time.monotonic() - start,
              'duplicate_slot_is_not_an_additional_sample': True,
              'paired_common_support': 'Retained only in unchanged legacy output',
              'gpu_started': False}
    target = ROOT / 'results/physical_independent.json.gz'
    with gzip.open(target, 'xt') as stream:
        json.dump(output, stream, allow_nan=False)
    print(json.dumps({'output': str(target), 'cpu_seconds': output['cpu_seconds']}))


if __name__ == '__main__':
    main()
