"""Consume complete, manifest-verified offline x0 decodes serially on CPU."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run-id', required=True)
    p.add_argument('--root', default='/data5/researcher/h3_runs/timing_autoresearch_20261016')
    args = p.parse_args()
    root = Path(args.root)
    decoded = root/'outputs/x0_decoded'/args.run_id
    output = root/'analysis/pose/x0'/args.run_id
    output.mkdir(parents=True, exist_ok=True)
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    os.environ['OPENBLAS_NUM_THREADS'] = '1'
    os.environ['OMP_NUM_THREADS'] = '1'
    results = []
    for name in ('sampler_final', 'x0_step019', 'x0_step005', 'x0_step010', 'x0_step015'):
        deadline = time.monotonic()+3600
        manifest_path = decoded/(name+'.json')
        manifest = None
        while time.monotonic() < deadline:
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text())
                except json.JSONDecodeError:
                    manifest = None
                if manifest and manifest.get('status') in ('complete', 'error', 'failed'):
                    break
            time.sleep(60)
        if not manifest or manifest.get('status') != 'complete':
            result = {'checkpoint': name, 'status': 'decode_not_complete_or_failed', 'manifest': manifest}
        else:
            video = decoded/(name+'.mp4')
            if not video.is_file() or hashlib.sha256(video.read_bytes()).hexdigest() != manifest['output_sha256']:
                raise RuntimeError(f'{name}: complete decode manifest/file hash mismatch')
            if manifest['decoded_shape'] != [141, 736, 1312, 3] or manifest['fps'] != 24:
                raise RuntimeError(f'{name}: unexpected decoded geometry; preserve and investigate')
            (output/(name+'.decode_manifest.json')).write_text(json.dumps(manifest, indent=2)+'\n')
            command = [sys.executable, str(root/'scripts/pose_probe.py'), '--video', str(video),
                       '--output-dir', str(output), '--threads', '4', '--overlay-frame', '55',
                       '--overlay-frame', '63', '--overlay-frame', '86', '--overlay-frame', '105']
            with (output/(name+'.pose_extract.log')).open('w') as log:
                process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
            if process.returncode:
                result = {'checkpoint': name, 'status': 'pose_extraction_failed', 'returncode': process.returncode}
            else:
                command = [sys.executable, str(root/'analysis/pose/evaluate_x0.py'),
                           '--source', str(root/'analysis/pose/old_sam/05_real_megumi_v.pose.json'),
                           '--pose', str(output/(name+'.pose.json')), '--checkpoint', name,
                           '--protocol', str(root/'analysis/pose/x0/INTERMEDIATE_PROTOCOL.txt'),
                           '--output', str(output/(name+'.observability.json'))]
                process = subprocess.run(command, capture_output=True, text=True)
                (output/(name+'.evaluate.log')).write_text(process.stdout+process.stderr)
                if process.returncode:
                    result = {'checkpoint': name, 'status': 'pose_measurement_failed', 'returncode': process.returncode}
                else:
                    data = json.loads((output/(name+'.observability.json')).read_text())
                    result = {'checkpoint': name, 'status': 'complete', 'observability': data['observability'],
                              'detector_statistics': data['detector_statistics']}
        results.append(result)
        (output/'batch_results.json').write_text(json.dumps({'run_id': args.run_id, 'results': results}, indent=2)+'\n')
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
