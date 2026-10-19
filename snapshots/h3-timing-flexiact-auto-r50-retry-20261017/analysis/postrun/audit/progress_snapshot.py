"""Read-only progress extraction; final scientific checks remain in postrun."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

root = Path(sys.argv[1])
read = lambda path: json.loads(path.read_text())
protocol = read(root / 'analysis/postrun/PROTOCOL.json')
assert str(root) == protocol['root_remote']
responses = {}
for path in (root / 'audit/observations').glob('step*/response.json'):
    request = read(path.parent / 'request.json')
    responses.setdefault(request['run_id'], []).append((path, read(path)))
cases = []
for case in protocol['cases']:
    run = case['run_id']
    path = root / 'audit/counterfactual' / (run + '.json')
    row = {'run_id': run, 'status': 'pending', 'completed_steps': [], 'ON_indices': [],
           'observation_unknown_reasons': {}, 'responses': [], 'decoder_retries': 0,
           'decoder_stage_seconds': 0., 'observer_wall_seconds': 0.}
    if path.exists():
        audit = read(path)
        current = audit.get('counterfactual', {})
        steps = current.get('steps', [])
        reasons = Counter()
        observation_status = Counter()
        window_baselines = Counter()
        unknown_window_causes = Counter()
        for measurement in current.get('measurements', []):
            observation = measurement.get('observer', {})
            observation_status[observation.get('status', measurement.get('status', 'pending'))] += 1
            for reason in observation.get('reasons', []):
                reasons[json.dumps(reason, sort_keys=True)] += 1
            for window in observation.get('windows', []):
                window_baselines[window['baseline']] += 1
                if window['baseline'] == 'unknown':
                    for confidence, diagnostic in window['measurements'].items():
                        unknown_window_causes[confidence + ':' + diagnostic['status']] += 1
                        for flag in diagnostic.get('flags', []):
                            unknown_window_causes[confidence + ':' + flag] += 1
        row.update(status=audit.get('status'), error=audit.get('error'),
                   completed_steps=[s['physical_index'] for s in steps],
                   ON_indices=[s['physical_index'] for s in steps if s['decision']['chosen_full']],
                   observation_status=dict(observation_status), observation_unknown_reasons=dict(reasons),
                   decision_reasons=dict(Counter(s['decision']['reason'] for s in steps)),
                   window_baselines=dict(window_baselines), unknown_window_causes=dict(unknown_window_causes),
                   counterfactual_evidence={'file': str(path), 'bytes': path.stat().st_size,
                                            'mtime_ns': path.stat().st_mtime_ns})
    for path, response in sorted(responses.get(run, []), key=lambda item: item[1]['physical_index']):
        release = response.get('after_decoder_release', {})
        row['responses'].append({'index': response['physical_index'], 'status': response['status'],
                                 'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                 'own_decoder_released': release.get('original_generation_absent') is True
                                                         and release.get('nvml_pid_absent') is True})
        row['decoder_retries'] += max(0, len(response.get('decoder_attempts', [])) - 1)
        row['decoder_stage_seconds'] += response.get('decoder_stage_seconds', 0.)
        row['observer_wall_seconds'] += response.get('wall_seconds', 0.)
    cases.append(row)
controller = root / 'logs/controller_state.json'
result = {'observed_unix': time.time(), 'fixed_case_denominator': 5,
          'controller': read(controller) if controller.exists() else {},
          'cases': cases,
          'failed_requests': [str(p) for p in (root / 'audit/observations').glob('step*/failure.json')],
          'scope': 'Current committed decisions and completed responses; final validation pending.'}
print(json.dumps(result))
