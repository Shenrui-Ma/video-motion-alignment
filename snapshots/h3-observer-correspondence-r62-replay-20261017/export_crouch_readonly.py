"""Executed on the remote host via stdin; reads JSON only and streams a tar."""
from pathlib import Path
import hashlib
import io
import json
import sys
import tarfile
import time

root = Path('/data5/researcher/h3_runs/timing_flexiact_auto_r50_retry_20261017')
read = lambda path: json.loads(path.read_text())
sha = lambda data: hashlib.sha256(data).hexdigest()
case = next(c for c in read(root / 'configs/protocol.json')['cases'] if c['source_id'] == 'crouch')
run = case['run_id']
source = root / case['source_pose_path']
source_raw = source.read_bytes()
assert sha(source_raw) == case['source_pose_sha256']
counterfactual = root / 'audit/counterfactual' / (run + '.json')
counterfactual_raw = counterfactual.read_bytes()
decisions = {x['physical_index']: x['decision'] for x in json.loads(counterfactual_raw)['counterfactual']['steps']}
files = {'source.pose.json': source_raw, 'counterfactual_snapshot.json': counterfactual_raw}
rows, failures = [], []
for request_path in sorted((root / 'audit/observations').glob('step*/request.json')):
    request_raw = request_path.read_bytes()
    request = json.loads(request_raw)
    if request['run_id'] != run:
        continue
    step = request['physical_index']
    response_path = request_path.with_name('response.json')
    prefix = f'steps/{step:03d}/'
    if not response_path.exists():
        assert step == 14 and request['request_id'] == 'step014_ae6dbbe585864e15bee2c48d8f6cc2c7'
        failure_path = request_path.with_name('failure.json')
        failure_raw = failure_path.read_bytes()
        failure = json.loads(failure_raw)
        assert failure['status'] == 'failed' and failure['request_sha256'] == sha(request_raw)
        files[prefix + 'request.json'], files[prefix + 'failure.json'] = request_raw, failure_raw
        failures.append({'denoising_index': step, 'state': 'technical_failure',
                         'response_exists': False, 'pose_usable': False,
                         'request_file': prefix + 'request.json', 'failure_file': prefix + 'failure.json',
                         'failure_remote_file': str(failure_path), 'error': failure['error']})
        continue
    response_raw = response_path.read_bytes()
    response = json.loads(response_raw)
    assert response['status'] == 'complete' and response['request_sha256'] == sha(request_raw)
    assert response['physical_index'] == step
    pose = Path(response['pose']['file'])
    assert pose.is_relative_to(root) and pose.suffix == '.json'
    pose_raw = pose.read_bytes()
    assert sha(pose_raw) == response['pose']['sha256']
    for name, data in [('request.json', request_raw), ('response.json', response_raw), ('target.pose.json', pose_raw)]:
        files[prefix + name] = data
    decision = decisions.get(step)
    assert decision is not None and decision['response_sha256'] == sha(response_raw)
    rows.append({'denoising_index': step, 'run_id': run, 'original_decision_committed': True,
        'original_decision': decision,
        'request': {'remote_file': str(request_path), 'relative_file': prefix + 'request.json', 'sha256': sha(request_raw)},
        'response': {'remote_file': str(response_path), 'relative_file': prefix + 'response.json', 'sha256': sha(response_raw)},
        'target_pose': {'remote_file': str(pose), 'relative_file': prefix + 'target.pose.json', 'sha256': sha(pose_raw)},
        'observer': response['observer'], 'endpoint_file_sha256': response['endpoint_file_sha256']})
rows.sort(key=lambda r: r['denoising_index'])
assert [r['denoising_index'] for r in rows] == list(range(14))
assert len(failures) == 1
index = {'schema': 'existing-observer-pose-export-v1', 'observed_unix': time.time(),
    'root_remote': str(root), 'run_id': run, 'case': case,
    'source_pose': {'remote_file': str(source), 'relative_file': 'source.pose.json', 'sha256': sha(source_raw)},
    'rows': rows, 'technical_failures': failures, 'missing_after_failure': list(range(15, 20)),
    'counterfactual_snapshot': {'remote_file': str(counterfactual), 'relative_file': 'counterfactual_snapshot.json',
                                'sha256': sha(counterfactual_raw), 'snapshot_only': True},
    'scope': 'Existing JSON only. step014 technical failure is excluded from observation/policy updates. No remote writes, no GPU or new pose.',
    'files': {name: {'sha256': sha(data), 'bytes': len(data)} for name, data in files.items()}}
files['INDEX.json'] = (json.dumps(index, indent=2, allow_nan=False) + '\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|gz') as archive:
    for name, data in files.items():
        assert name.endswith('.json')
        info = tarfile.TarInfo(name)
        info.size, info.mode = len(data), 0o644
        archive.addfile(info, io.BytesIO(data))
