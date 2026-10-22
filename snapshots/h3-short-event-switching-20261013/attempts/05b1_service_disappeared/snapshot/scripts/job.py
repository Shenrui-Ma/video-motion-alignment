"""Submit once and preserve Comfy history for the task-owned service."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

import service

RUN = service.RUN
URL = f'http://127.0.0.1:{service.PORT}'


def validate_name(name):
    if re.fullmatch(r'[a-z0-9_]+', name) is None:
        raise ValueError('Job name must contain only lowercase letters, digits and underscores')
    return name


def request(route, body=None):
    payload = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(URL + route, data=payload, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode()) from exc


def active_service():
    record = json.loads((RUN / 'processes/service.json').read_text())
    service.assert_owned(record)
    return record


def check_host_admission(owner):
    admission = json.loads((RUN / 'configs/admission.json').read_text())
    other_processes = [row for row in service.compute_processes() if row['pid'] != owner['pid']]
    existing_queue = service.queue_at(admission.get('existing_comfy_port', 8189))
    service.check_admission(admission, other_processes, existing_queue)
    return time.time()


def submit(name):
    validate_name(name)
    graph_path = RUN / 'configs' / (name + '.json')
    record_path = RUN / 'logs' / (name + '_job.json')
    with (RUN / 'processes/jobs.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if record_path.exists():
            raise RuntimeError('Job record already exists; inspect status before retrying')
        owner = active_service()
        data = graph_path.read_bytes()
        graph = json.loads(data)
        if not isinstance(graph, dict) or not graph:
            raise ValueError('Graph must be a nonempty API prompt object')
        queue = request('/queue')
        if queue['queue_running'] or queue['queue_pending']:
            raise RuntimeError('Task queue is not empty')
        admitted_unix = check_host_admission(owner)
        record = {'name': name, 'graph': str(graph_path), 'graph_sha256': hashlib.sha256(data).hexdigest(),
                  'submitted_unix': time.time(), 'status': 'submitting',
                  'service_pid': owner['pid'], 'service_identity': owner['identity'],
                  'queue_before_submit': queue, 'host_admission_checked_unix': admitted_unix}
        with record_path.open('x') as target:
            json.dump(record, target, indent=2)
        try:
            response = request('/prompt', {'prompt': graph, 'client_id': 'h3-short-event-switching-20261013'})
            record.update(status='queued', response=response, prompt_id=response['prompt_id'])
        except Exception as exc:
            record.update(status='submission_uncertain', error=str(exc), observed_unix=time.time())
            service.write_json(record_path, record)
            raise
        service.write_json(record_path, record)
    print(json.dumps(record))
    return record


def status(name):
    validate_name(name)
    path = RUN / 'logs' / (name + '_job.json')
    record = json.loads(path.read_text())
    history_path = RUN / 'logs' / (name + '_history.json')
    # Persisted history remains authoritative after the task service is stopped/restarted.
    if record['status'] in ('success', 'error') and history_path.exists():
        result = json.loads(history_path.read_text())
        answer = {'name': name, 'status': result['status'], 'outputs': result.get('outputs', {}),
                  'archived': True, 'observed_unix': record.get('observed_unix')}
        print(json.dumps(answer))
        return answer
    if 'prompt_id' not in record:
        answer = {'name': name, 'status': record['status'], 'error': record.get('error'),
                  'note': 'No saved prompt ID; do not auto-resubmit'}
        print(json.dumps(answer))
        return answer
    owner = active_service()
    if owner['pid'] != record['service_pid'] or owner['identity'] != record['service_identity']:
        raise RuntimeError('Job belongs to another service instance; inspect saved artifacts')
    prompt_id = record['prompt_id']
    result = request('/history/' + prompt_id).get(prompt_id)
    queue = None
    present = False
    if not result:
        queue = request('/queue')
        present = any(row[1] == prompt_id for row in queue['queue_running'] + queue['queue_pending'])
        if not present:
            # Completion can race the first history read and subsequent queue read.
            result = request('/history/' + prompt_id).get(prompt_id)
    if result:
        service.write_json(history_path, result)
        status_value = result['status']['status_str']
        answer = {'name': name, 'status': result['status'], 'outputs': result.get('outputs', {})}
    else:
        status_value = 'pending_or_running' if present else 'unknown_missing'
        answer = {'name': name, 'status': status_value,
                  'running_ids': [row[1] for row in queue['queue_running']],
                  'pending_ids': [row[1] for row in queue['queue_pending']]}
    record.update(status=status_value, observed_unix=time.time())
    service.write_json(path, record)
    answer['elapsed_seconds'] = record['observed_unix'] - record['submitted_unix']
    print(json.dumps(answer))
    return answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['submit', 'status'])
    parser.add_argument('name', type=validate_name)
    args = parser.parse_args()
    submit(args.name) if args.action == 'submit' else status(args.name)
