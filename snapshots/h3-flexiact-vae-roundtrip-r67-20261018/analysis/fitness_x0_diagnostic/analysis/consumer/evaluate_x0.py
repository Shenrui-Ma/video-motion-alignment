"""CPU pose measurement after the root verified a saved-x0 decoder exit."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
X0 = HERE.parents[1]
R67 = X0.parents[1]
sys.path.insert(0, str(R67 / 'scripts'))
from common import require, sha, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--key', required=True)
    args = parser.parse_args()
    require(args.key in ['native_step002_attempt1', 'native_step005_attempt1',
                         'native_step006_attempt1', 'forced_step006_attempt1'], 'registered key')
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    decoded = X0 / 'outputs' / args.key
    progress = X0 / 'audit/root_batch_attempt1/PROGRESS.json'
    exits = json.loads(progress.read_text())
    exit_rec = next(x for x in exits if x['key'] == args.key)
    d = json.loads((decoded / 'RESULT.json').read_text())
    require(d['status'] == 'complete' and d['fallback_guard']['calls'] == 0, 'successful native decode')
    require(exit_rec['process_absent'] is True and exit_rec['CUDA_allocation_absent'] is True
            and exit_rec['pid'] == d['pid'], 'root verified decoder exit')
    require(d['model_forward_calls'] == 0, 'saved x0 only')
    require(d['code_contract_sha256'] == sha(X0 / 'configs/contract.json'), 'decode contract')
    freeze = json.loads((X0 / 'FREEZE.json').read_text())
    for item in freeze['files']:
        require(sha(X0 / item['path']) == item['sha256'], 'frozen saved-x0 package')
    item = d['products']['x0_158']
    video = decoded / item['file']
    require(sha(video) == item['sha256'] and item['frames'] == 158 and item['fps'] == 24,
            'actual full158 decoded video')
    require(item['selected_full158_indices'] == list(range(158)), 'full decoded timeline')

    previous = R67 / 'analysis/fitness_attempt2/PHYSICAL.json'
    previous_result = json.loads(previous.read_text())
    cached = previous_result['poses']['prepared']
    source_file = R67 / 'analysis/fitness_attempt2/prepared/prepared_158.pose.json'
    require(sha(source_file) == cached['sha256'], 'actual prepared RGB pose cache')
    source = json.loads(source_file.read_text())
    prepared = json.loads((R67 / 'inputs/fitness/PREPARED.json').read_text())
    require(source['video']['sha256'] == prepared['products']['prepared_158']['sha256'],
            'source pose video binding')
    for rel, digest in json.loads((R67 / 'configs/physical_code.json').read_text()).items():
        require(sha(R67 / rel) == digest, 'frozen physical functions')
    protocol = json.loads((R67 / 'configs/pose_protocol.json').read_text())
    for path, digest in protocol['frozen_external'].items():
        require(sha(path) == digest, 'frozen pose dependency')
    pose_script = next(x for x in protocol['frozen_external'] if x.endswith('/pose_probe.py'))
    out = HERE / args.key
    require(not out.exists(), 'new evaluation directory')
    out.mkdir()
    write(out / 'ROOT_EXIT_USED.json', exit_rec)
    cmd = [sys.executable, pose_script, '--video', str(video), '--output-dir', str(out),
           '--threads', '4', '--stride', '1']
    started = time.monotonic()
    with (out / 'pose.log').open('x') as log:
        run = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=240,
                             env=dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='4',
                                      MKL_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4', NUMEXPR_NUM_THREADS='4'))
    require(run.returncode == 0, 'pose extraction failed, retained log')
    target_file = out / 'x0_158.pose.json'
    target = json.loads(target_file.read_text())
    require(target['video']['sha256'] == item['sha256'] and len(target['frames']) == 158,
            'target pose binding and frame count')
    require(target['provenance'] == source['provenance'], 'source and target pose runtime')
    sys.path.insert(0, str(R67 / 'runtime/physical'))
    import evaluate
    result = {'status': 'complete', 'scope': 'saved predicted clean x0; exploratory pose timing',
              'input': d['input'], 'source_pose_sha256': sha(source_file),
              'target_pose_sha256': sha(target_file), 'video_sha256': sha(video),
              'decode_receipt_sha256': sha(decoded / 'RESULT.json'), 'root_exit': exit_rec,
              'pose_seconds': time.monotonic() - started, 'pose_command': cmd,
              'physical_time_step_ms': 125, 'confidence_results': {}}
    for confidence in (.3, .5):
        try:
            reference = evaluate.original_time_view(source, confidence)
            endpoint = evaluate.original_time_view(target, confidence)
        except ValueError as exc:
            if str(exc) != 'Insufficient reliable torso anchors for scale normalization':
                raise
            result['confidence_results'][str(confidence)] = {'status': 'unknown_visibility', 'rows': []}
            continue
        result['confidence_results'][str(confidence)] = {'status': 'measured', 'rows': [
            evaluate.diagnostic(reference, endpoint, window, feature)
            for window in evaluate.PROTOCOL['windows_inclusive'] for feature in evaluate.FEATURES]}
    write(out / 'PHYSICAL.json', evaluate.metrics.clean(result))
    print(out / 'PHYSICAL.json')


if __name__ == '__main__':
    main()
