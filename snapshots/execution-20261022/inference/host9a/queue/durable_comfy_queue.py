#!/usr/bin/env python3
"""Sequential durable ComfyUI runner. Standard library only; ffprobe validates videos."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    with temp.open('w') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


@contextlib.contextmanager
def process_lock(path):
    with open(path, 'a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another runner holds this state directory lock')
        lock.seek(0)
        lock.truncate()
        lock.write(str(os.getpid()))
        lock.flush()
        yield


class API:
    def __init__(self, base, timeout=30):
        self.base = base.rstrip('/')
        self.timeout = timeout

    def call(self, path, body=None):
        request = urllib.request.Request(self.base + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type': 'application/json'})
        # No environment HTTP_PROXY route for localhost traffic.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=self.timeout) as response:
            return json.load(response)


def prompt_extra(record):
    if isinstance(record, dict):
        record = record.get('prompt', [])
    return record[3] if isinstance(record, list) and len(record) > 3 and isinstance(record[3], dict) else {}


def recover_prompt(api, job_id, attempt_token):
    """Both requests must succeed; inability to inspect is not evidence of absence."""
    queue = api.call('/queue')
    history = api.call('/history')
    found = set()
    for record in queue.get('queue_running', []) + queue.get('queue_pending', []):
        extra = prompt_extra(record)
        if extra.get('durable_job_id') == job_id and extra.get('durable_attempt_token') == attempt_token:
            found.add(record[1])
    for prompt_id, record in history.items():
        extra = prompt_extra(record)
        if extra.get('durable_job_id') == job_id and extra.get('durable_attempt_token') == attempt_token:
            found.add(prompt_id)
    if len(found) > 1:
        raise RuntimeError(f'Multiple prompts found for {job_id}; inspect manually: {sorted(found)}')
    return next(iter(found), None)


def extract_files(history):
    for output in history.get('outputs', {}).values():
        for kind in ('gifs', 'videos', 'images'):
            for entry in output.get(kind, []):
                if isinstance(entry, dict) and entry.get('filename'):
                    yield entry


def validate_outputs(history, job, output_root, ffprobe):
    prefix = job['expected_output_prefix'].replace('\\', '/')
    files = []
    for entry in extract_files(history):
        if entry.get('type', 'output') != 'output':
            continue
        rel = Path(entry.get('subfolder', '')) / entry['filename']
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError(f'Unsafe output path: {rel}')
        if not rel.as_posix().startswith(prefix) or rel.suffix.lower() not in ('.mp4', '.webm', '.mov', '.mkv', '.avi'):
            continue
        path = output_root / rel
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f'Output missing or empty: {path}')
        proc = subprocess.run([ffprobe, '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name,width,height,nb_frames,duration:format=duration',
            '-of', 'json', str(path)], capture_output=True, text=True, timeout=120)
        if proc.returncode:
            raise ValueError(f'ffprobe failed: {path}: {proc.stderr[-1000:]}')
        probe = json.loads(proc.stdout)
        stream = next(iter(probe.get('streams', [])), {})
        duration = stream.get('duration') or probe.get('format', {}).get('duration')
        if stream.get('width', 0) <= 0 or stream.get('height', 0) <= 0 or duration is None or float(duration) <= 0:
            raise ValueError(f'Invalid video stream: {path}: {probe}')
        digest = hashlib.sha256()
        with path.open('rb') as data:
            for chunk in iter(lambda: data.read(1024 * 1024), b''):
                digest.update(chunk)
        files.append({'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest(), 'probe': probe})
    if not files:
        raise ValueError(f'No completed video output matches prefix {prefix!r}')
    return files


def timing(history, job, prompt_id):
    """Do not estimate sampling time by dividing end-to-end execution duration."""
    times = {}
    for item in history.get('status', {}).get('messages', []):
        if isinstance(item, list) and len(item) >= 2 and isinstance(item[1], dict):
            timestamp = item[1].get('timestamp')
            if isinstance(timestamp, (int, float)):
                times[item[0]] = timestamp / 1000
    start, end = times.get('execution_start'), times.get('execution_success')
    result = {'execution_seconds': end - start if start is not None and end is not None else None,
              'sampling_seconds': None, 'sampling_step_seconds': [], 'mean_sampling_step_seconds': None,
              'sampling_source': None}
    timing_file = job.get('metadata', {}).get('timing_file')
    if timing_file and Path(timing_file).is_file():
        try:
            audit = json.loads(Path(timing_file).read_text())
            if not isinstance(audit, dict):
                raise ValueError('Timing audit must be a JSON object')
        except (OSError, ValueError) as error:
            result['sampling_error'] = str(error)
            return result
        seconds = audit.get('sampler_wall_seconds')
        steps = audit.get('per_step_seconds', [])
        if isinstance(seconds, (int, float)) and math.isfinite(seconds) and seconds >= 0:
            result['sampling_seconds'] = seconds
        if isinstance(steps, list) and steps and all(isinstance(x, (int, float)) and math.isfinite(x) and x >= 0 for x in steps):
            result['sampling_step_seconds'] = steps
            result['mean_sampling_step_seconds'] = sum(steps) / len(steps)
        result['sampling_source'] = str(timing_file)
        return result
    events_path = job.get('sampling_events_path')
    if events_path and Path(events_path).is_file():
        events = []
        for line in Path(events_path).read_text().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get('prompt_id') == prompt_id:
                events.append(event)
        starts = [e['timestamp'] for e in events if e.get('event') == 'sampling_start']
        ends = [e['timestamp'] for e in events if e.get('event') == 'sampling_end']
        steps = [e['duration_seconds'] for e in events if e.get('event') == 'sampling_step' and isinstance(e.get('duration_seconds'), (int, float))]
        if len(starts) == len(ends) == 1 and ends[0] >= starts[0]:
            result['sampling_seconds'] = ends[0] - starts[0]
        if steps:
            result['sampling_step_seconds'] = steps
            result['mean_sampling_step_seconds'] = sum(steps) / len(steps)
        if result['sampling_seconds'] is not None or steps:
            result['sampling_source'] = str(events_path)
    return result


def attempt_values(value, attempt_id):
    """Expand attempt placeholders; audit run_id fields always identify this attempt."""
    if isinstance(value, dict):
        return {key: attempt_id if key == 'run_id' else attempt_values(item, attempt_id) for key, item in value.items()}
    if isinstance(value, list):
        return [attempt_values(item, attempt_id) for item in value]
    if isinstance(value, str):
        return value.replace('{attempt_id}', attempt_id).replace('{run_id}', attempt_id)
    return value


class Runner:
    def __init__(self, args):
        self.args = args
        self.api = API(args.comfy_url, args.request_timeout)
        self.root = Path(args.state_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / 'state.json'
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {'jobs': {}}

    def save(self):
        atomic_json(self.state_path, self.state)

    def log(self, event, **fields):
        record = {'time': time.time(), 'event': event, **fields}
        with (self.root / 'events.jsonl').open('a') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
        print(json.dumps(record, ensure_ascii=False), flush=True)

    def restart_service(self, job_id, prompt_id):
        """The supplied command owns stopping/starting ONLY the caller's service."""
        if not self.args.restart_command or self.state.get('service_restarts', 0) >= self.args.max_service_restarts:
            return False
        argv = json.loads(self.args.restart_command)
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
            raise ValueError('--restart-command must be a nonempty JSON array of arguments')
        self.state['service_restarts'] = self.state.get('service_restarts', 0) + 1
        self.save()
        self.log('service_restart', job_id=job_id, prompt_id=prompt_id)
        try:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=self.args.restart_timeout)
            self.log('service_restart_result', returncode=result.returncode,
                     stdout=result.stdout[-2000:], stderr=result.stderr[-2000:])
            if result.returncode:
                return False
            # The command must wait until its new ComfyUI endpoint is healthy.
            self.api.call('/queue')
            return True
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            self.log('service_restart_failed', error=str(error))
            return False

    def wait_service(self, job, state):
        """Health check before creating a submission intent or consuming an attempt."""
        started = last_restart = time.monotonic()
        while True:
            try:
                self.api.call('/queue')
                return True
            except (OSError, ValueError, urllib.error.URLError) as error:
                self.log('preflight_connection_error', job_id=job['id'], error=str(error))
                now = time.monotonic()
                if now - last_restart >= self.args.restart_after_seconds:
                    last_restart = now
                    if self.restart_service(job['id'], None):
                        return True
                if now - started >= self.args.stall_timeout:
                    state.update(status='waiting_connection', error=str(error))
                    self.save()
                    return False
                time.sleep(self.args.poll_seconds)

    @staticmethod
    def interrupted_record(prompt_id, reason):
        return {'prompt': [0, prompt_id, {}, {}, []], 'outputs': {},
                'status': {'completed': True, 'status_str': 'error',
                           'messages': [['managed_service_restart', {'reason': reason}]]}}

    def poll(self, job, state):
        prompt_id = state['prompt_id']
        last_progress = time.monotonic()
        previous_signal = None
        connection_failed_at = None
        missing_since = None
        while True:
            try:
                history = self.api.call('/history/' + prompt_id)
                record = history.get(prompt_id)
                if record:
                    status = record.get('status', {})
                    if status.get('status_str') == 'error':
                        return 'failed', record
                    if status.get('completed'):
                        return 'completed', record
                queue = self.api.call('/queue')
                connection_failed_at = None
                active = {r[1] for r in queue.get('queue_running', [])}
                pending = {r[1] for r in queue.get('queue_pending', [])}
                if not record and prompt_id not in active | pending and not active | pending:
                    if missing_since is None:
                        missing_since = time.monotonic()
                    elif time.monotonic() - missing_since >= self.args.missing_prompt_grace:
                        # Fast service restarts can happen entirely between polls.
                        # Confirm a managed restart before treating absent history
                        # as an interrupted attempt eligible for a fresh submission.
                        if self.restart_service(job['id'], prompt_id):
                            queue_after = self.api.call('/queue')
                            history_after = self.api.call('/history/' + prompt_id)
                            queued_after = {r[1] for r in queue_after.get('queue_running', []) + queue_after.get('queue_pending', [])}
                            if prompt_id not in queued_after and prompt_id not in history_after:
                                return 'failed', self.interrupted_record(prompt_id, 'Missing prompt after confirmed managed restart')
                        missing_since = time.monotonic()
                else:
                    missing_since = None
                signal = ('running' if prompt_id in active else 'pending' if prompt_id in pending else 'absent', json.dumps(record, sort_keys=True))
                progress_file = job.get('progress_file')
                if progress_file and Path(progress_file).exists():
                    signal += (Path(progress_file).stat().st_mtime_ns,)
                if signal != previous_signal:
                    last_progress = time.monotonic()
                    previous_signal = signal
                    self.log('progress', job_id=job['id'], prompt_id=prompt_id, status=signal[0])
                if time.monotonic() - last_progress > self.args.stall_timeout:
                    # Preserve ownership and prompt ID; external supervisor can inspect/resume.
                    state['status'] = 'waiting_stalled'
                    state['error'] = 'No new history, queue transition, or progress-file update before stall timeout'
                    self.save()
                    self.log('stalled', job_id=job['id'], prompt_id=prompt_id)
                    return 'stalled', record
            except (OSError, ValueError, urllib.error.URLError) as error:
                self.log('poll_connection_error', job_id=job['id'], error=str(error))
                if connection_failed_at is None:
                    connection_failed_at = time.monotonic()
                if time.monotonic() - connection_failed_at >= self.args.restart_after_seconds and self.restart_service(job['id'], prompt_id):
                    # Successful managed restart may preserve history or find an old
                    # live service. Resume that ID whenever it can still be found.
                    try:
                        queue = self.api.call('/queue')
                        history = self.api.call('/history/' + prompt_id)
                        ids = {r[1] for r in queue.get('queue_running', []) + queue.get('queue_pending', [])}
                        if prompt_id not in ids and prompt_id not in history:
                            return 'failed', self.interrupted_record(prompt_id, 'Disconnected execution disappeared after managed restart')
                        connection_failed_at = None
                        last_progress = time.monotonic()
                    except (OSError, ValueError, urllib.error.URLError) as recovery_error:
                        self.log('restart_recovery_error', error=str(recovery_error))
                if time.monotonic() - last_progress > self.args.stall_timeout:
                    state['status'] = 'waiting_connection'
                    state['error'] = str(error)
                    self.save()
                    return 'stalled', None
            time.sleep(self.args.poll_seconds)

    def run_job(self, job, manifest_dir):
        job_id = job['id']
        graph_path = Path(job['graph'])
        if not graph_path.is_absolute():
            graph_path = manifest_dir / graph_path
        graph_doc = json.loads(graph_path.read_text())
        if not isinstance(graph_doc, dict):
            raise ValueError('Graph must be an API graph JSON object')
        graph = graph_doc.get('prompt', graph_doc)
        if not isinstance(graph, dict):
            raise ValueError('prompt must be an API graph JSON object')
        digest = hashlib.sha256(json.dumps(graph, sort_keys=True).encode()).hexdigest()
        state = self.state['jobs'].setdefault(job_id, {'attempts': 0, 'status': 'pending', 'graph_sha256': digest})
        if state.get('graph_sha256') != digest:
            raise ValueError(f'Graph changed for existing job {job_id}; use a new job ID')
        if state['status'] == 'completed':
            return True
        while state['attempts'] < self.args.max_attempts or state.get('prompt_id') or state.get('status') in ('submitting', 'submission_unknown'):
            if state['status'] in ('submitting', 'submission_unknown'):
                deadline = time.monotonic() + self.args.recovery_seconds
                while True:
                    try:
                        found = recover_prompt(self.api, job_id, state['attempt_token'])
                    except (OSError, ValueError, urllib.error.URLError) as error:
                        self.log('recovery_connection_error', job_id=job_id, error=str(error))
                        found = None
                    if found:
                        state.update(prompt_id=found, status='submitted')
                        self.save()
                        self.log('recovered_prompt', job_id=job_id, prompt_id=found)
                        break
                    if time.monotonic() >= deadline:
                        state['status'] = 'submission_unknown'
                        self.save()
                        self.log('submission_unresolved', job_id=job_id, detail='Retained for recovery; no resubmission')
                        return True
                    time.sleep(self.args.poll_seconds)
            if not state.get('prompt_id'):
                if not self.wait_service(job, state):
                    return False
                state.update(status='submitting', attempt_token=str(uuid.uuid4()), attempts=state['attempts'] + 1,
                             submitted_at=time.time(), metadata=job.get('metadata', {}))
                state['attempt_id'] = job_id + '__a' + str(state['attempts'])
                self.save()  # Submission intent is durable BEFORE HTTP request.
                attempt_job = attempt_values(job, state['attempt_id'])
                payload = {'prompt': attempt_values(graph, state['attempt_id']), 'client_id': 'durable-queue-' + state['attempt_token'],
                           'extra_data': {'durable_job_id': job_id, 'durable_attempt_token': state['attempt_token'],
                                          'durable_attempt_id': state['attempt_id'],
                                          'durable_metadata': attempt_job.get('metadata', {})}}
                try:
                    reply = self.api.call('/prompt', payload)
                    if not reply.get('prompt_id'):
                        raise ValueError('Submission returned no prompt_id')
                    state.update(status='submitted', prompt_id=reply['prompt_id'])
                    self.save()
                    self.log('submitted', job_id=job_id, prompt_id=state['prompt_id'], attempt=state['attempts'])
                except urllib.error.HTTPError as error:
                    # 4xx is a definite rejection; 5xx can follow partial acceptance.
                    if 400 <= error.code < 500:
                        state.update(status='failed_attempt', error=error.read(8192).decode(errors='replace'))
                        self.save()
                        self.log('submission_rejected', job_id=job_id, error=state['error'])
                        continue
                    state.update(status='submission_unknown', error=str(error))
                    self.save()
                    continue
                except (OSError, ValueError, urllib.error.URLError) as error:
                    state.update(status='submission_unknown', error=str(error))
                    self.save()
                    continue
            attempt_id = state.get('attempt_id', job_id + '__a' + str(state['attempts']))
            attempt_job = attempt_values(job, attempt_id)
            outcome, history = self.poll(attempt_job, state)
            if outcome == 'stalled':
                return False
            prompt_id = state['prompt_id']
            atomic_json(self.root / 'history' / (prompt_id + '.json'), history)
            if outcome == 'completed':
                try:
                    files = validate_outputs(history, attempt_job, Path(self.args.output_root), self.args.ffprobe)
                    result = {'job_id': job_id, 'prompt_id': prompt_id, 'graph_sha256': digest,
                              'attempt_id': attempt_id, 'metadata': attempt_job.get('metadata', {}),
                              'files': files, 'timing': timing(history, attempt_job, prompt_id),
                              'submit_to_validation_seconds': time.time() - state['submitted_at']}
                    atomic_json(self.root / 'results' / (job_id + '.json'), result)
                    state.update(status='completed', completed_at=time.time(), result=str(self.root / 'results' / (job_id + '.json')))
                    self.save()
                    self.log('completed', job_id=job_id, prompt_id=prompt_id)
                    return True
                except (ValueError, OSError, subprocess.SubprocessError) as error:
                    state['error'] = str(error)
                    self.log('output_validation_failed', job_id=job_id, error=str(error))
            else:
                state['error'] = history.get('status', {})
                self.log('execution_failed', job_id=job_id, prompt_id=prompt_id)
            state.setdefault('previous_attempts', []).append({'prompt_id': prompt_id, 'error': state.get('error')})
            state.pop('prompt_id', None)
            state['status'] = 'failed_attempt'
            self.save()
        state['status'] = 'failed'
        self.save()
        self.log('attempts_exhausted', job_id=job_id)
        return True

    def run(self):
        manifest_path = Path(self.args.manifest).resolve()
        visited = set()
        with process_lock(self.root / 'runner.lock'):
            while True:
                # Replace manifests atomically. New jobs are picked up after each
                # completed/failed item; an empty remaining queue exits immediately.
                jobs = json.loads(manifest_path.read_text())['jobs']
                ids = [job['id'] for job in jobs]
                if len(ids) != len(set(ids)):
                    raise ValueError('Duplicate job IDs in manifest')
                if any(not isinstance(x, str) or not x or '/' in x or '\\' in x or x in ('.', '..') for x in ids):
                    raise ValueError('Job IDs must be safe filename components')
                remaining = [job for job in jobs if job['id'] not in visited]
                if not remaining:
                    break
                job = remaining[0]
                visited.add(job['id'])
                try:
                    if not self.run_job(job, manifest_path.parent):
                        return 2
                except (ValueError, OSError, KeyError) as error:
                    state = self.state['jobs'].setdefault(job.get('id', 'invalid'), {})
                    state.update(status='invalid', error=str(error))
                    self.save()
                    self.log('job_invalid', job_id=job.get('id'), error=str(error))
            self.log('queue_finished', statuses={job_id: state.get('status') for job_id, state in self.state['jobs'].items()})
        return 0 if all(self.state['jobs'].get(i, {}).get('status') == 'completed' for i in ids) else 1


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', required=True)
    p.add_argument('--state-dir', required=True)
    p.add_argument('--comfy-url', default='http://127.0.0.1:8188')
    p.add_argument('--output-root', required=True)
    p.add_argument('--ffprobe', default='ffprobe')
    p.add_argument('--max-attempts', type=int, default=2)
    p.add_argument('--poll-seconds', type=float, default=5)
    p.add_argument('--request-timeout', type=float, default=30)
    p.add_argument('--recovery-seconds', type=float, default=60)
    p.add_argument('--stall-timeout', type=float, default=14400)
    p.add_argument('--restart-command', help='JSON argv for owned-service stop/start; success must mean healthy endpoint')
    p.add_argument('--restart-after-seconds', type=float, default=120)
    p.add_argument('--max-service-restarts', type=int, default=2)
    p.add_argument('--restart-timeout', type=float, default=600)
    p.add_argument('--missing-prompt-grace', type=float, default=120)
    return p


if __name__ == '__main__':
    try:
        sys.exit(Runner(parser().parse_args()).run())
    except (RuntimeError, ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
