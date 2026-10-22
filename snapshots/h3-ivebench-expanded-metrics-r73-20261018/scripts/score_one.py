"""Score fresh same-host source and target with the frozen official matching function."""
import argparse
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
from common import *
from bindings import configure_score

def check_runtime_pair(source, target):
    for key in ('torch_version', 'cuda_version', 'official_commit', 'tracker', 'checkpoint_sha256', 'selection_sha256', 'source_prepared_sha256', 'source_score_sha256', 'effective_frame_count', 'score_frame_indices'):
        require(source[key] == target[key], 'source/target runtime or input differs: ' + key)
    for key in ('hostname', 'gpu_name'):
        require(source['admission_before_cuda'][key] == target['admission_before_cuda'][key], 'source/target hardware differs: ' + key)

def score(source, method, source_attempt=1, target_attempt=1):
    verify_runtime()
    folders = [ROOT / 'tracks/source' / source / ('attempt' + str(source_attempt)), ROOT / 'tracks' / method / source / ('attempt' + str(target_attempt))]
    reports = []
    for role, folder in zip(('source', method), folders):
        binding = read(folder / 'R73_BINDING.json'); report = read(folder / 'REPORT.json')
        require(binding['actual_tracking'] is True and binding['source'] == source and binding['method'] == role and binding['report'] == bound(folder / 'REPORT.json'), 'actual tracking role/report differs')
        require(binding['consumer_freeze_sha256'] == sha(ROOT / 'CONSUMER_FREEZE.json') and binding['numerical_tracker']['sha256'] == sha(RUNTIME / 'metric_runtime/run_tracks.py'), 'tracking numerical implementation differs')
        require(binding['manifest'] == bound(source_manifest(source) if role == 'source' else ROOT / 'prepared' / source / 'METRIC_INPUTS.json'), 'actual tracking input manifest changed')
        reports.append(report)
    check_runtime_pair(*reports)
    result = configure_score().score(*folders)
    require(result['cuda_initialized'] is False, 'CPU score initialized CUDA')
    result.update(fixed_denominator=5, source_policy='fresh same-host and GPU-model source/targets', scope='five source-selected official general-editing tasks; MF only; not full IVEBench or a timing accuracy metric', consumer_freeze_sha256=sha(ROOT / 'CONSUMER_FREEZE.json'))
    out = ROOT / 'results' / source / f'{method}_source{source_attempt}_target{target_attempt}.json'
    save(out, result)
    return result

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--source', choices=PAIRS, required=True); p.add_argument('--method', choices=METHODS, required=True); p.add_argument('--source-attempt', type=int, default=1); p.add_argument('--target-attempt', type=int, default=1)
    a = p.parse_args()
    with cpu_lock():
        print(json.dumps(score(a.source, a.method, a.source_attempt, a.target_attempt)))
