"""CPU-only valid-prefix export after a full actual R59 runtime case gate.

This module neither launches scoring GPUs nor controls the producer service.
It emits exact source/edited score inputs and preserves all three method arms.
"""
import argparse
import fcntl
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from execution_contract import require, read, sha, file_record, safe, write_new
from r59_contract import registry
import release_prefix


def observed_pending(root):
    state = root / 'logs/controller_state.json'
    if not state.exists():
        return False
    current = read(state).get('current')
    if not current:
        return False
    for path in (root / 'audit/observations').glob('*/request.json'):
        if read(path).get('run_id') == current and not (path.parent / 'response.json').exists() and not (path.parent / 'failure.json').exists():
            return True
    return False


def verify_gate(root, run, gate_path):
    jobs, _ = registry(root)
    require(run in jobs, 'unknown fixed executable run')
    gate = read(gate_path)
    require(gate.get('status') == 'pass' and gate.get('producer_manifest_sha256') == sha(root / 'deploy_manifest.json') and gate.get('protocol_sha256') == sha(root / 'configs/protocol.json'), 'actual runtime gate not bound to producer')
    require(gate.get('planned_denominator') == 15 and gate.get('registered_arms') == 4, 'runtime gate used an incomplete registry')
    rows = [row for row in gate['cases'] if row['run'] == run]
    require(len(rows) == 1 and rows[0]['arm'] == jobs[run]['arm'] and rows[0]['updates'] == 20, 'actual case runtime result missing')
    require(gate.get('candidate_science_preserved') is True and gate.get('runtime_integrity_only') is True, 'actual science/runtime verification scope missing')
    proof = rows[0].get('independent_parent_inputs', {})
    require(proof.get('actual_clean_inputs_equal') is True and proof.get('initial_video_audio_noise_equal') is True and bool(rows[0].get('independent_native_prefix')), 'independent actual parent payload comparisons missing')
    owner = read(root / 'processes/service.json')
    require(gate['service_record'] == owner, 'runtime gate service generation changed')
    job = read(root / 'logs' / (run + '_job.json'))
    history = read(root / 'logs' / (run + '_history.json'))
    require(job['service_pid'] == owner['pid'] and job['service_identity'] == owner['identity'], 'job service generation differs')
    require(job['status'] == 'success' and job['graph_sha256'] == jobs[run]['graph_sha256'] and history['prompt'][1] == job['prompt_id'] and history['prompt'][2] == read(root / 'configs/graphs' / (run + '.json')), 'actual job/history binding differs')
    require(history['status']['status_str'] == 'success' and history['status']['completed'] is True, 'actual Comfy history incomplete')
    outputs = history['outputs']['14']['images']
    require(len(outputs) == 1 and outputs[0]['type'] == 'output' and not outputs[0].get('subfolder'), 'expected one task output')
    require(re.fullmatch(re.escape(run) + r'_\d+_\.mp4', outputs[0]['filename']), 'output run differs')
    return jobs[run]['case'], safe(root / 'output', outputs[0]['filename']), rows[0]


def export(root, run, gate_path):
    root, gate_path = Path(root), Path(gate_path)
    case, output, runtime = verify_gate(root, run, gate_path)
    for relative, record in read(root / 'deploy_manifest.json')['files'].items():
        require(file_record(root / relative) == record, 'sealed producer file changed: ' + relative)
    destination = root / 'analysis/postrun/completed_cases' / run
    require(not destination.exists(), 'existing/partial case export requires explicit recovery')
    lock_path = Path(read(root / 'configs/protocol.json')['resources']['CPU_lock'])
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if observed_pending(root):
            raise BlockingIOError('online observer has priority')
        destination.mkdir(parents=True)
        binding = read(ROOT / 'analysis/postrun/SOURCE_SCORE_BINDINGS.json')[case['source_id']]
        require(binding['valid_frames'] == case['valid_frame_count'] and binding['prepared_video_sha256'] == case['video_sha256'] and binding['provenance_sha256'] == case['provenance_sha256'], 'published score source/task differs')
        for row in binding['files'].values():
            require(file_record(row['remote_file']) == {key: row[key] for key in ('bytes', 'sha256')}, 'published source score artifact changed')
        source = release_prefix.reuse_source(root / 'inputs' / case['video'], root / 'inputs' / case['original_source'], root / 'inputs' / case['provenance'], Path(binding['files']['source_score.mp4']['remote_file']), destination / 'source_score.mp4')
        edited = release_prefix.edited_view(output, case['valid_frame_count'], destination / 'edited_score.mp4')
        generation = {'schema': 'r59-P1-generation-record-v1', 'run_id': run, 'source_id': case['source_id'],
            'method': case['arm'], 'prompt_version': 'P1', 'prompt': case['prompt'], 'seed': case['seed'],
            'geometry': case['geometry'], 'parent_run': case['parent_run'],
            'parent_binding_sha256': sha(root / 'prepared_parent/PARENT_BINDING.json'),
            'runtime_gate': {'file': str(gate_path.resolve()), 'sha256': sha(gate_path)},
            'runtime': runtime, 'producer_manifest_sha256': sha(root / 'deploy_manifest.json'),
            'full_video': {'file': str(output), 'sha256': sha(output)},
            'graph': {'file': str(root / 'configs/graphs' / (run + '.json')), 'sha256': sha(root / 'configs/graphs' / (run + '.json'))},
            'score_geometry': {'frames': case['valid_frame_count'], 'fps': 24, 'crop_xywh': [16, 8, 1280, 720]}}
        write_new(destination / 'GENERATION_RECORD.json', generation)
        result = {'schema': 'r59-valid-prefix-score-input-v1', 'source_id': case['source_id'], 'run_id': run,
            'arm': case['arm'], 'seed': case['seed'], 'parent_run': case['parent_run'],
            'valid_frames': case['valid_frame_count'], 'fps': 24, 'crop_xywh': [16, 8, 1280, 720],
            'padding_evaluated': False, 'runtime_gate_file': str(gate_path.resolve()), 'runtime_gate_sha256': sha(gate_path),
            'producer_manifest_sha256': sha(root / 'deploy_manifest.json'),
            'full_video': {'file': str(output), **file_record(output)}, 'runtime': runtime,
            'files': {name: {'file': str(destination / name), **file_record(destination / name)} for name in ('source_score.mp4', 'edited_score.mp4', 'source_score.mapping.json', 'edited_score.mapping.json', 'GENERATION_RECORD.json')},
            'source_export': source, 'edited_export': edited,
            'score_status': 'INPUTS_READY_NOT_SCORED', 'quality_conclusion': None}
        write_new(destination / 'METRIC_INPUTS.json', result)
        write_new(destination / 'CASE_READY.json', {'status': 'ready', 'run_id': run, 'arm': case['arm'],
            'metric_inputs_sha256': sha(destination / 'METRIC_INPUTS.json'), 'runtime_gate_sha256': sha(gate_path)})
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--run', required=True)
    parser.add_argument('--runtime-gate', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = export(args.root, args.run, args.runtime_gate)
    except BlockingIOError as error:
        print(json.dumps({'status': 'WAIT_CPU_PRIORITY', 'reason': str(error)}))
        raise SystemExit(75)
    print(json.dumps({'status': result['score_status'], 'run_id': args.run, 'arm': result['arm']}))
