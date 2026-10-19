"""R66 administrative adapter to the unchanged R65 CPU pose/evaluation functions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

os.environ['CUDA_VISIBLE_DEVICES'] = ''
ROOT = Path(__file__).resolve().parents[2]
ADMIN = Path(__file__).resolve().parent
PROTOCOL = json.loads((ADMIN / 'PROTOCOL.json').read_text())
for name, expected in PROTOCOL['local_static_pins'].items():
    if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
        raise ValueError('administrative dependency changed: ' + name)
sys.path.insert(0, str(ROOT / 'scripts'))
from common import bound, cpu_lock, frozen, load, pair_info, read, require, save, sha, verify_gate, PAIR_KEYS
from priority import pending


def relabel(value):
    if isinstance(value, dict):
        return {('forced' if k == 'automatic' else k): relabel(v) for k, v in value.items()}
    if isinstance(value, list):
        return [relabel(v) for v in value]
    return value


def prerequisites(pair):
    require(str(ROOT).startswith('/data5/'), 'use original .9 CPU environment')
    old = Path(PROTOCOL['frozen_r65_remote'])
    for name, digest in PROTOCOL['frozen_r65_files'].items():
        require(sha(old / name) == digest, 'R65 frozen dependency changed: ' + name)
    old_contract = read(old / 'configs/contract.json')
    frozen(old / 'runtime/physical', 'FREEZE.json', old_contract['physical_freeze_sha256'])
    protocol = old_contract['pose_protocol']
    for path, digest in protocol['frozen_external'].items():
        require(sha(path) == digest, 'DWPose code/model changed: ' + path)
    gate = verify_gate(read(ROOT / 'incoming' / pair / 'PAIR_RUNTIME_GATE.json'), pair)
    action = pair_info(pair)['motion_source_id']
    source = PROTOCOL['source_bindings'][action]
    require(sha(source['pose_path']) == source['pose_sha256'], 'source pose changed')
    original = read(source['pose_path'])
    validator = load('r66_original_pose_validator', old / 'runtime/source_pose/remote_one.py')
    validator.validate_pose(original, source['video_sha256'], protocol)
    for method in ('native', 'forced'):
        require(sha(ROOT / 'incoming' / pair / (method + '.mp4')) == gate['runs'][method]['video']['sha256'], 'target video differs from actual gate')
    return old, old_contract, protocol, gate, original, validator, source


def pose(pair, method):
    old, old_contract, protocol, gate, original, validator, source = prerequisites(pair)
    video = ROOT / 'incoming' / pair / (method + '.mp4')
    dest = ROOT / 'poses' / pair / method
    require(not dest.exists(), 'pose attempt already exists; preserve and inspect')
    dest.mkdir(parents=True)
    probe = next(p for p in protocol['frozen_external'] if p.endswith('/pose_probe.py'))
    command = [sys.executable, probe, '--video', str(video), '--output-dir', str(dest), '--threads', '4', '--stride', '1']
    start = time.monotonic()
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='4', MKL_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4', NUMEXPR_NUM_THREADS='4', PYTHONDONTWRITEBYTECODE='1')
    with (dest / 'pose.log').open('x') as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, env=env, timeout=240)
    require(result.returncode == 0, 'DWPose failed; preserve actual log')
    path = dest / (method + '.pose.json')
    raw = validator.validate_pose(read(path), sha(video), protocol)
    require(raw['provenance'] == original['provenance'] and raw['joint_order'] == original['joint_order'], 'source/target DWPose runtime differs')
    save(dest / 'COMPLETE.json', {'passed': True, 'pair': pair, 'method': method, 'video': bound(video), 'pose': bound(path), 'producer_gate': bound(ROOT / 'incoming' / pair / 'PAIR_RUNTIME_GATE.json'), 'source_pose': bound(source['pose_path']), 'pose_provenance': raw['provenance'], 'command': command, 'elapsed_seconds': time.monotonic() - start, 'adapter_protocol': bound(ADMIN / 'PROTOCOL.json'), 'retained_frames': 158, 'scored_frame_indices': list(range(0, 147, 3))})
    return dest


def evaluate(pair):
    old, old_contract, protocol, gate, original, validator, source = prerequisites(pair)
    poses, receipts = {}, {}
    for method in ('native', 'forced'):
        dest = ROOT / 'poses' / pair / method
        receipt = read(dest / 'COMPLETE.json')
        path = dest / (method + '.pose.json')
        require(receipt['passed'] is True and receipt['pair'] == pair and receipt['method'] == method and receipt['video']['sha256'] == gate['runs'][method]['video']['sha256'] and sha(path) == receipt['pose']['sha256'], 'target pose binding differs')
        require(receipt['producer_gate']['sha256'] == sha(ROOT / 'incoming' / pair / 'PAIR_RUNTIME_GATE.json'), 'pose gate binding differs')
        poses[method] = validator.validate_pose(read(path), receipt['video']['sha256'], protocol)
        require(poses[method]['provenance'] == original['provenance'] and poses[method]['joint_order'] == original['joint_order'], 'pose runtimes differ')
        receipts[method] = bound(dest / 'COMPLETE.json')
    sys.path.insert(0, str(old / 'runtime/physical'))
    evaluator = load('r66_unchanged_r65_evaluator', old / 'runtime/physical/evaluate.py')
    start = time.monotonic()
    result = evaluator.evaluate(original, poses['native'], poses['forced'])
    report = {'schema': 'r66-frozen-physical-pair-v1', 'pair': pair, 'motion_source_id': pair_info(pair)['motion_source_id'], 'numeric_freeze_sha256': old_contract['physical_freeze_sha256'], 'source_pose': bound(source['pose_path']), 'generated_pose_receipts': receipts, 'producer_gate': bound(ROOT / 'incoming' / pair / 'PAIR_RUNTIME_GATE.json'), 'adapter_protocol': bound(ADMIN / 'PROTOCOL.json'), 'numeric_function': 'unchanged R65 evaluate(reference,native,automatic); automatic argument contains forced', 'method_label_map': {'native': 'native', 'automatic': 'forced'}, 'result': relabel(result), 'elapsed_seconds': time.monotonic() - start, 'scope': PROTOCOL['scope'], 'all_fixed_windows_and_UNKNOWN_retained': True}
    output = ROOT / 'scores/physical' / (pair + '.json')
    save(output, report)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', choices=PAIR_KEYS, required=True)
    parser.add_argument('--phase', choices=['check', 'pose-native', 'pose-forced', 'evaluate'], required=True)
    args = parser.parse_args()
    if pending(PROTOCOL['online_priority_roots']):
        raise BlockingIOError('online observer priority')
    with cpu_lock():
        if pending(PROTOCOL['online_priority_roots']):
            raise BlockingIOError('online observer priority')
        if args.phase == 'check':
            prerequisites(args.pair)
            print('R66_PHYSICAL_PREREQUISITES_PASS')
        elif args.phase == 'evaluate':
            print(evaluate(args.pair))
        else:
            print(pose(args.pair, args.phase.split('-', 1)[1]))


if __name__ == '__main__':
    try:
        main()
    except BlockingIOError:
        print('SHARED_CPU_LOCK_BUSY_OR_ONLINE_PRIORITY')
        raise SystemExit(75)
