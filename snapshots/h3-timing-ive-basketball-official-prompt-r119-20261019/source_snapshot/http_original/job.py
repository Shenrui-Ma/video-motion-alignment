"""Submit once and preserve Comfy history for the task-owned service."""
import argparse
import fcntl
import http.client
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


class StatusUnavailable(RuntimeError):
    """The registered job status could not be observed through a read-only HTTP request."""


def request(route, body=None):
    payload = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(URL + route, data=payload, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if body is None and exc.code in (408, 429, 500, 502, 503, 504):
            raise StatusUnavailable('HTTP status observation unavailable: ' + str(exc.code)) from exc
        raise RuntimeError(exc.read().decode()) from exc
    except (TimeoutError, ConnectionError, urllib.error.URLError, http.client.IncompleteRead) as exc:
        if body is None:
            raise StatusUnavailable('HTTP status observation unavailable: ' + repr(exc)) from exc
        raise


def active_service():
    record = json.loads((RUN / 'processes/service.json').read_text())
    service.assert_owned(record)
    return record


def check_host_admission(owner):
    admission = json.loads((RUN / 'configs/admission.json').read_text())
    existing_queue = service.queue_at(admission.get('existing_comfy_port', 8189))
    service.wait_admission_snapshot(admission, existing_queue, exclude_pid=owner['pid'])
    return time.time()


def require_generation(actual,expected):
    if actual['pid']!=expected['pid'] or actual['identity']!=expected['identity']:raise RuntimeError('stale service generation')

def wait_host_admission(owner,timeout=600):
    started=time.monotonic()
    while True:
        require_generation(active_service(),owner)
        try:return check_host_admission(owner)
        except RuntimeError as error:
            # Retry the same strict test; no unregistered process is admitted.
            if not (str(error).startswith('Unexpected host compute PID ') or str(error)=='Selected GPU has active compute; refusing to start'):raise
            with (RUN/'logs/submission_admission_wait.jsonl').open('a') as f:f.write(json.dumps({'unix':time.time(),'owner_pid':owner['pid'],'error':str(error)})+'\n')
            if time.monotonic()-started>=timeout:raise TimeoutError('strict peer admission did not clear') from error
            time.sleep(2)


def require_native_generation(binding, owner):
    if binding['arm'] != 'forced':return
    run = 'r104_' + binding['source_id'] + '_seed2026101701_native'
    native = json.loads((RUN/'logs'/(run+'_job.json')).read_text())
    history = json.loads((RUN/'logs'/(run+'_history.json')).read_text())
    if (native.get('status') != 'success' or native['service_pid'] != owner['pid'] or
        native['service_identity'] != owner['identity'] or
        history['status'].get('completed') is not True or history['status'].get('status_str') != 'success'):
        raise RuntimeError('paired Native success or service generation differs')


def submit(name, expected_owner=None):
    validate_name(name)
    from execution_gate import admitted_job
    if not admitted_job(name,RUN):raise RuntimeError('root Native/first-guided review pending; no submission')
    from r104_contract import validate_job, prepare_loader_inputs
    binding = validate_job(name)
    prepare_loader_inputs(name)
    graph_path = RUN / 'configs/graphs' / (name + '.json')
    record_path = RUN / 'logs' / (name + '_job.json')
    with (RUN / 'processes/jobs.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if record_path.exists():
            raise RuntimeError('Job record already exists; inspect status before retrying')
        owner = active_service()
        if not admitted_job(name,RUN):raise RuntimeError('root Native/first-guided review pending inside submission lock')
        require_native_generation(binding,owner)
        require_generation(active_service(),owner)
        if expected_owner is not None and (owner['pid']!=expected_owner['pid'] or owner['identity']!=expected_owner['identity']):raise RuntimeError('service generation changed before submission')
        data = graph_path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=binding['graph_sha256']:raise ValueError('graph changed between validation and actual submission')
        graph = json.loads(data)
        if not isinstance(graph, dict) or not graph:
            raise ValueError('Graph must be a nonempty API prompt object')
        queue = request('/queue')
        if queue['queue_running'] or queue['queue_pending']:
            raise RuntimeError('Task queue is not empty')
        admitted_unix = wait_host_admission(owner)
        record = {'name': name, 'graph': str(graph_path), 'graph_sha256': hashlib.sha256(data).hexdigest(),
                  'submitted_unix': time.time(), 'status': 'submitting',
                  'service_pid': owner['pid'], 'service_identity': owner['identity'],
                  'queue_before_submit': queue, 'host_admission_checked_unix': admitted_unix, 'case_binding': binding,
                  'queue_sha256': hashlib.sha256((RUN/'configs/queue.json').read_bytes()).hexdigest()}
        with record_path.open('x') as target:
            json.dump(record, target, indent=2)
        try:
            require_generation(active_service(),owner)
            if not admitted_job(name,RUN):raise RuntimeError('approval withdrawn before POST')
            require_native_generation(binding,owner)
            require_generation(active_service(),owner)
            response = request('/prompt', {'prompt': graph, 'client_id': 'h3-timing-ive-native-screen-r104-20261018'})
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
