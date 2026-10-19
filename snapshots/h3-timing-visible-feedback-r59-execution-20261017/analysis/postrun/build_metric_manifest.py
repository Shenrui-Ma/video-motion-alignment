"""Assemble four methods over the same five IVEBench sources after all exports."""
import argparse
import copy
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from execution_contract import require, read, sha, write_new, SOURCES
from r59_contract import cases

METHODS = ('native', 'visible_only', 'visible_fallback', 'weak_only')
SELECTION_SHA = '5d4f43a066dffa7227e062c5914734f1d406627d10c2c1c8cdf0388e25ad8fd9'


def bound_file(record):
    require(sha(record['file']) == record['sha256'], 'metric dependency changed: ' + record['file'])
    return {'file': record['file'], 'sha256': record['sha256']}


def build(root=ROOT):
    root = Path(root)
    parent = read(root / 'prepared_parent/PARENT_BINDING.json')
    archive = Path(parent['parent_archive'])
    require(sha(archive / 'deploy_manifest.json') == parent['parent_manifest_sha256'], 'Native R57 producer differs')
    rows = cases(root)
    pairs, receipts = [], []
    for source in SOURCES:
        group = [case for case in rows if case['source_id'] == source]
        reference = group[0]
        native_folder = archive / 'final' / reference['parent_run']
        native_metric = native_folder / 'METRIC_INPUTS.json'
        summary = read(native_folder / 'SUMMARY.json')
        inventory = read(native_folder / 'CASE_FILES.json')
        for relative, digest in inventory.items():
            require(sha(native_folder / relative) == digest, 'Native P1 export changed')
        require(summary['passed'] is True and summary['run_id'] == reference['parent_run'] and summary['source_id'] == source and summary['metric_inputs_sha256'] == sha(native_metric), 'actual Native P1 score inputs missing')
        require(summary['actual_reference_equal_P0'] is True and summary['actual_initial_AV_noise_equal_P0'] is True, 'Native P1 original source/noise pairing missing')
        pair = copy.deepcopy(read(native_metric))
        require(pair['pair_id'] == source and pair['score_frame_indices'] == list(range(reference['valid_frame_count'])) and set(pair['edited']) == {'native'}, 'Native P1 score domain differs')
        bound_file(pair['source_score_video'])
        bound_file(pair['edited']['native']['score_video'])
        for case in group[1:]:
            folder = root / 'analysis/postrun/completed_cases' / case['run_id']
            path = folder / 'METRIC_INPUTS.json'
            ready = read(folder / 'CASE_READY.json')
            metric = read(path)
            require(ready['status'] == 'ready' and ready['run_id'] == case['run_id'] and ready['arm'] == case['arm'] and ready['metric_inputs_sha256'] == sha(path), 'method case export pending/changed')
            require(metric['run_id'] == case['run_id'] and metric['arm'] == case['arm'] and metric['valid_frames'] == reference['valid_frame_count'] and metric['seed'] == reference['seed'], 'method source/seed/time domain differs')
            require(metric['producer_manifest_sha256'] == sha(root / 'deploy_manifest.json'), 'method producer differs')
            require(sha(metric['runtime_gate_file']) == metric['runtime_gate_sha256'] == ready['runtime_gate_sha256'], 'actual method runtime gate changed')
            require(bound_file(metric['files']['source_score.mp4'])['sha256'] == pair['source_score_video']['sha256'], 'methods do not share exact source score input')
            pair['edited'][case['arm']] = {
                'score_video': bound_file(metric['files']['edited_score.mp4']),
                'full_video': bound_file(metric['full_video']),
                'generation_record': bound_file(metric['files']['GENERATION_RECORD.json']),
                'release_record': bound_file(metric['files']['edited_score.mapping.json'])}
            receipts.append({'run_id': case['run_id'], 'metric_inputs_sha256': sha(path), 'runtime_gate_sha256': ready['runtime_gate_sha256']})
        require(list(pair['edited']) == list(METHODS), 'four-method denominator incomplete')
        pairs.append(pair)
    manifest = {'schema': 'h3-ivebench-official-mf-inputs-v1', 'selection_sha256': SELECTION_SHA,
        'methods': list(METHODS), 'pairs': pairs, 'protocol_sha256': sha(root / 'configs/protocol.json'),
        'producer_manifest_sha256': sha(root / 'deploy_manifest.json'),
        'actual_R57_parent_manifest_sha256': parent['parent_manifest_sha256'],
        'R59_case_receipts': receipts, 'metrics_computed': False,
        'scope': 'Fixed five diagnostic/development cases; P1 Native reused, three new paired R59 arms; valid-prefix official MF input interface.'}
    output = root / 'analysis/postrun/METRIC_MANIFEST.json'
    write_new(output, manifest)
    return {'file': str(output), 'sha256': sha(output), 'pairs': 5, 'methods': list(METHODS), 'metrics_computed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(build(args.root), indent=2))
