"""Score each actual target against the fresh same-runtime source cache."""
import argparse
import os
from pathlib import Path
import sys

os.environ['CUDA_VISIBLE_DEVICES'] = ''
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import bound, read, save, verify_runtime, cpu_lock, RUNTIME
sys.path.insert(0, str(RUNTIME / 'metric_runtime'))
from score_cached_tracks import score
from track_source import verify_extension


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--method', choices=['native', 'forced'], required=True)
    parser.add_argument('--source-attempt', type=int, default=1)
    parser.add_argument('--target-attempt', type=int, default=1)
    args = parser.parse_args()
    if min(args.source_attempt, args.target_attempt) < 1:
        raise ValueError('positive attempts required')
    runtime = verify_runtime(); extension = verify_extension()
    source = HERE / 'tracks' / ('attempt' + str(args.source_attempt))
    target = ROOT / 'tracks' / args.method / 'short_0210' / ('attempt' + str(args.target_attempt))
    manifest = bound(ROOT / 'prepared/short_0210/METRIC_INPUTS.json')
    sb = read(source / 'SOURCE_BINDING.json'); tb = read(target / 'R63_BINDING.json')
    if (sb['runtime_freeze_sha256'] != runtime or tb['runtime_freeze_sha256'] != runtime or sb['extension_freeze_sha256'] != extension or
            sb['input_manifest'] != manifest or tb['input_manifest'] != manifest or
            sb['report'] != bound(source / 'REPORT.json') or tb['report'] != bound(target / 'REPORT.json') or
            not sb['new_actual_tracking'] or not tb['new_actual_tracking']):
        raise ValueError('fresh source/target actual tracking binding differs')
    s = read(source / 'REPORT.json'); t = read(target / 'REPORT.json')
    for key in ['torch_version', 'cuda_version', 'checkpoint_sha256', 'tracker', 'official_commit']:
        if s[key] != t[key]:
            raise ValueError('fresh source/target numerical runtime differs: ' + key)
    with cpu_lock():
        result = score(source, target)
        if result['cuda_initialized']:
            raise ValueError('CPU score initialized CUDA')
        result.update(source_policy='fresh .9 source, same Torch/CUDA runtime as both new targets',
                      source_gpu_uuid=s['gpu_uuid'], target_gpu_uuid=t['gpu_uuid'],
                      runtime_freeze_sha256=runtime, extension_freeze_sha256=extension,
                      fixed_denominator=5, source_runtime={'torch':s['torch_version'], 'cuda':s['cuda_version']})
        path = HERE / 'results' / (args.method + '_source' + str(args.source_attempt) + '_target' + str(args.target_attempt) + '.json')
        save(path, result)
        print(result)


if __name__ == '__main__':
    main()
