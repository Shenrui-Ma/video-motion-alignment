"""Submit and inspect an isolated pilot graph without changing the shared server."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

RUN = Path('/data5/researcher/h3_runs/background_leakage_pilot_20261007')
URL = 'http://127.0.0.1:8387'


def request(route, body=None):
    payload = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(URL + route, data=payload,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode()) from exc


def submit(name):
    graph_path = RUN / 'configs' / (name + '.json')
    record_path = RUN / 'logs' / (name + '_job.json')
    if record_path.exists():
        raise RuntimeError('Job record already exists; inspect status before retrying')
    graph = json.loads(graph_path.read_text())
    queue = request('/queue')
    if queue['queue_running'] or queue['queue_pending']:
        raise RuntimeError('Pilot queue is not empty')
    record = {'name': name, 'graph': str(graph_path),
              'graph_sha256': hashlib.sha256(graph_path.read_bytes()).hexdigest(),
              'submitted_unix': time.time(), 'status': 'submitting'}
    record_path.write_text(json.dumps(record, indent=2))
    response = request('/prompt', {'prompt': graph, 'client_id': 'h3-bg-pilot-20261007'})
    record.update(status='queued', response=response, prompt_id=response['prompt_id'])
    record_path.write_text(json.dumps(record, indent=2))
    print(json.dumps(record))


def status(name):
    record_path = RUN / 'logs' / (name + '_job.json')
    record = json.loads(record_path.read_text())
    prompt_id = record['prompt_id']
    history = request('/history/' + prompt_id)
    result = history.get(prompt_id)
    queue = None
    present = False
    if not result:
        queue = request('/queue')
        present = any(x[1] == prompt_id for x in queue['queue_running'] + queue['queue_pending'])
        if not present:
            # Completion can race the first history read and the queue read.
            result = request('/history/' + prompt_id).get(prompt_id)
    if result:
        (RUN / 'logs' / (name + '_history.json')).write_text(json.dumps(result, indent=2))
        record.update(status=result['status']['status_str'], observed_unix=time.time())
        record_path.write_text(json.dumps(record, indent=2))
        print(json.dumps({'name': name, 'status': result['status'],
                          'outputs': result.get('outputs', {}),
                          'elapsed_seconds': time.time() - record['submitted_unix']}))
    else:
        status_name = 'pending_or_running' if present else 'unknown_missing'
        if not present:
            record.update(status=status_name, observed_unix=time.time())
            record_path.write_text(json.dumps(record, indent=2))
        print(json.dumps({'name': name, 'status': status_name,
                          'running_ids': [x[1] for x in queue['queue_running']],
                          'pending_ids': [x[1] for x in queue['queue_pending']],
                          'elapsed_seconds': time.time() - record['submitted_unix']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['submit', 'status'])
    parser.add_argument('name')
    args = parser.parse_args()
    submit(args.name) if args.action == 'submit' else status(args.name)
