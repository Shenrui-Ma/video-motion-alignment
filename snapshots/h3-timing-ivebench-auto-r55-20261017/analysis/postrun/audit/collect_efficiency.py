"""Read existing completed-case timers and resource records without new inference."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

root, run = Path(sys.argv[1]), sys.argv[2]
read = lambda path: json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


audit_path = root / 'audit/counterfactual' / (run + '.json')
audit = read(audit_path)
counter = audit['counterfactual']
assert audit['status'] == 'complete'
assert len(counter['steps']) == len(counter['measurements']) == 20
job_path = root / 'logs' / (run + '_job.json')
job = read(job_path)
assert job['status'] == 'success'
branches = []
for row in counter['branches']:
    branches.append({key: row[key] for key in ('physical_index', 'branch', 'nfe_index',
                    'model_seconds_synchronized', 'archive_and_readout_seconds', 'condition_copy_hash_seconds')})
responses = []
for row in counter['measurements']:
    path = Path(row['response_file'])
    response = read(path)
    assert response['status'] == 'complete'
    decode_path = Path(response['decode']['file'])
    assert sha(decode_path) == response['decode']['sha256']
    decode = read(decode_path)
    responses.append({'denoising_index': row['physical_index'], 'file': str(path), 'sha256': sha(path),
                      'observer_wall_seconds': response['wall_seconds'],
                      'decoder_stage_seconds': response['decoder_stage_seconds'],
                      'decoder_process_wall_seconds': response['decoder']['wall_seconds'],
                      'pose_process_wall_seconds': response['pose_process']['wall_seconds'],
                      'outer_admission_wait_seconds': response.get('outer_admission_wait_seconds', 0),
                      'decoder_attempts': len(response.get('decoder_attempts', [])),
                      'decoder_peak_allocated_bytes': decode['max_memory_allocated_bytes'],
                      'decoder_peak_reserved_bytes': decode['max_memory_reserved_bytes']})
assert [row['denoising_index'] for row in responses] == list(range(20))
resource_path = root / 'logs/resources.jsonl'
samples = []
if resource_path.exists():
    for line in resource_path.read_text().splitlines():
        record = json.loads(line)
        if record['job'] == run:
            uuid, used, utilization, temperature = [x.strip() for x in record['sample'].split(',')]
            samples.append({'unix': record['unix'], 'gpu_uuid': uuid, 'total_device_used_MiB': int(used),
                            'utilization_percent': int(utilization), 'temperature_C': int(temperature)})
summary = {'schema': 'h3-completed-case-efficiency-v1', 'run_id': run,
           'job_wall_seconds': job['observed_unix'] - job['submitted_unix'],
           'branches': {name: {'count': sum(r['branch'] == name for r in branches),
                              'model_seconds_synchronized': sum(r['model_seconds_synchronized'] for r in branches if r['branch'] == name)}
                        for name in ('native', 'full')},
           'observer_count': len(responses),
           'observer_totals': {key: sum(r[key] for r in responses) for key in ('observer_wall_seconds',
                              'decoder_stage_seconds', 'decoder_process_wall_seconds',
                              'pose_process_wall_seconds', 'outer_admission_wait_seconds')},
           'decoder_retries': sum(max(0, r['decoder_attempts'] - 1) for r in responses),
           'decoder_peak_reserved_bytes': max(r['decoder_peak_reserved_bytes'] for r in responses),
           'decoder_peak_allocated_bytes': max(r['decoder_peak_allocated_bytes'] for r in responses),
           'main_task_allocator_peak_bytes': None,
           'main_GPU_sampled_total_peak_MiB': max((r['total_device_used_MiB'] for r in samples), default=None),
           'main_GPU_sampled_peak_scope': 'Entire device usage including other users; not an isolated task allocator peak.',
           'branch_records': branches, 'observer_records': responses, 'resource_samples': samples,
           'evidence': {'audit': {'file': str(audit_path), 'sha256': sha(audit_path)},
                        'job': {'file': str(job_path), 'sha256': sha(job_path)}},
           'scope': 'Existing timers only. Nested stage times overlap and must not be added to wall time.'}
print(json.dumps(summary, allow_nan=False))
