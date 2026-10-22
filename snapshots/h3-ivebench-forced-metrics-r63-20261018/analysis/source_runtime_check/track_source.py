"""Fresh .9 source tracking through the frozen IVEBench tracker."""
import argparse
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import bound, read, save, sha, verify_runtime, RUNTIME, SELECTION
from launch_tracker import identity
from track_one import resource_check
import run_tracks


def verify_extension():
    for rel, digest in read(HERE / 'FREEZE.json')['files'].items():
        if sha(HERE / rel) != digest:
            raise ValueError('source runtime extension differs: ' + rel)
    return sha(HERE / 'FREEZE.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpu-uuid', required=True)
    parser.add_argument('--attempt', type=int, default=1)
    parser.add_argument('--control', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if args.attempt < 1:
        raise ValueError('positive attempt required')
    extension = verify_extension(); runtime = verify_runtime()
    manifest = ROOT / 'prepared/short_0210/METRIC_INPUTS.json'
    row = read(manifest)
    old = read(ROOT / 'tracks/source/short_0210/REPORT.json')
    if (row['pair_id'] != 'short_0210' or
            row['source_score_video']['sha256'] != old['source_score_sha256'] or
            row['source_prepared_video']['sha256'] != old['source_prepared_sha256']):
        raise ValueError('fresh source differs from the original frozen source')
    if not args.check_only:
        if args.control is None or os.environ.get('CUDA_VISIBLE_DEVICES') != args.gpu_uuid:
            raise ValueError('root control directory and exact visible UUID required')
        args.control.mkdir(parents=True, exist_ok=False)
        ready = {'schema': 'r63-fresh-source-root-preCUDA-v1', 'identity': identity(),
                 'gpu_uuid': args.gpu_uuid, 'attempt': args.attempt, 'CUDA_started': False,
                 'runtime_freeze_sha256': runtime, 'extension_freeze_sha256': extension,
                 'input_manifest': bound(manifest), 'required_free_bytes': 16 * 1024**3}
        save(args.control / 'ready.json', ready)
        print({'ready': str(args.control / 'ready.json'), 'identity': ready['identity']}, flush=True)
        start = time.monotonic()
        while not (args.control / 'go.json').exists():
            if time.monotonic() - start > 600:
                raise TimeoutError('root source-tracker registration timed out')
            time.sleep(.2)
        if (read(args.control / 'go.json') != ready or identity() != ready['identity'] or
                verify_runtime() != runtime or verify_extension() != extension or
                bound(manifest) != ready['input_manifest']):
            raise ValueError('root approval or source binding changed')
    output = HERE / ('preflight' if args.check_only else 'tracks') / ('attempt' + str(args.attempt))
    original_args = argparse.Namespace(input_manifest=str(manifest), selection=str(SELECTION),
        pair='short_0210', method='source', gpu_uuid=args.gpu_uuid, check_only=args.check_only,
        output=str(output), ffmpeg='/usr/bin/ffmpeg', ffprobe='/usr/bin/ffprobe')
    run_tracks.check_gpu = resource_check
    run_tracks.main(original_args)
    save(output / 'SOURCE_BINDING.json', {'runtime_freeze_sha256': runtime,
         'extension_freeze_sha256': extension, 'input_manifest': bound(manifest),
         'report': bound(output / ('PREFLIGHT.json' if args.check_only else 'REPORT.json')),
         'frozen_tracker': bound(RUNTIME / 'metric_runtime/run_tracks.py'),
         'original_source_report': bound(ROOT / 'tracks/source/short_0210/REPORT.json'),
         'new_actual_tracking': not args.check_only})


if __name__ == '__main__':
    main()
