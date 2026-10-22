import contextlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import durable_comfy_queue as q


class Server:
    def __init__(self):
        self.history = {}
        self.pending = []
        self.count = {}
        self.payloads = []
        self.disconnect_once = False
        self.always_fail = set()
        self.fail_once = set()
        self.output_root = None
        outer = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def reply(self, body):
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            def do_GET(self):
                if self.path == '/queue':
                    self.reply({'queue_running': [], 'queue_pending': outer.pending})
                elif self.path == '/history':
                    self.reply(outer.history)
                elif self.path.startswith('/history/'):
                    pid = self.path.rsplit('/', 1)[1]
                    self.reply({pid: outer.history[pid]} if pid in outer.history else {})
                else:
                    self.send_error(404)
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                outer.payloads.append(body)
                job_id = body['extra_data']['durable_job_id']
                outer.count[job_id] = outer.count.get(job_id, 0) + 1
                count = outer.count[job_id]
                prompt_id = job_id + '-' + str(count)
                fail = job_id in outer.always_fail or (job_id in outer.fail_once and count == 1)
                outer.history[prompt_id] = outer.record(job_id, prompt_id, body['extra_data'], fail)
                if outer.disconnect_once:
                    outer.disconnect_once = False
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return
                self.reply({'prompt_id': prompt_id})
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_address[1])

    def record(self, job_id, prompt_id, extra, fail=False):
        if not fail:
            (self.output_root / (job_id + '_00001.mp4')).write_bytes(b'validated-by-mock-ffprobe')
        return {'prompt': [0, prompt_id, {}, extra, []],
                'status': {'completed': True, 'status_str': 'error' if fail else 'success',
                           'messages': [['execution_start', {'timestamp': 100000}],
                                        ['execution_success', {'timestamp': 104000}]]},
                'outputs': {} if fail else {'save': {'gifs': [{'filename': job_id + '_00001.mp4', 'type': 'output'}]}}}

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.output = self.root / 'output'
        self.output.mkdir()
        self.graph = self.root / 'graph.json'
        self.graph.write_text('{"1":{"class_type":"Mock","inputs":{}}}')
        self.probe = self.root / 'ffprobe'
        self.probe.write_text('#!' + sys.executable + '\nprint(\'{"streams":[{"width":64,"height":64,"duration":"1.0"}]}\')\n')
        self.probe.chmod(0o755)
        self.server = Server()
        self.server.output_root = self.output

    def tearDown(self):
        self.server.close()
        self.temp.cleanup()

    def runner(self, ids):
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps({'jobs': [{'id': i, 'graph': str(self.graph), 'expected_output_prefix': i} for i in ids]}))
        args = q.parser().parse_args(['--manifest', str(manifest), '--state-dir', str(self.root / 'state'),
                '--comfy-url', self.server.url, '--output-root', str(self.output), '--ffprobe', str(self.probe),
                '--poll-seconds', '0.01', '--recovery-seconds', '0.03', '--stall-timeout', '0.05'])
        return q.Runner(args)

    def run_silently(self, runner):
        with contextlib.redirect_stdout(io.StringIO()):
            return runner.run()

    def test_failed_job_retries_then_next_job_finishes(self):
        self.server.always_fail.add('bad')
        runner = self.runner(['bad', 'good'])
        self.assertEqual(self.run_silently(runner), 1)
        self.assertEqual(self.server.count, {'bad': 2, 'good': 1})
        self.assertEqual(runner.state['jobs']['bad']['status'], 'failed')
        self.assertEqual(runner.state['jobs']['good']['status'], 'completed')

    def test_transient_failure_succeeds_and_restart_does_not_resubmit(self):
        self.server.fail_once.add('first')
        runner = self.runner(['first', 'second'])
        self.assertEqual(self.run_silently(runner), 0)
        self.assertEqual(self.run_silently(self.runner(['first', 'second'])), 0)
        self.assertEqual(self.server.count, {'first': 2, 'second': 1})
        result = json.loads((self.root / 'state/results/first.json').read_text())
        self.assertEqual(result['timing']['execution_seconds'], 4.0)
        self.assertIsNone(result['timing']['sampling_seconds'])
        self.assertIsNone(result['timing']['mean_sampling_step_seconds'])

    def test_accepted_submission_connection_drop_recovers_no_duplicate(self):
        self.server.disconnect_once = True
        runner = self.runner(['recover'])
        self.assertEqual(self.run_silently(runner), 0)
        self.assertEqual(self.server.count, {'recover': 1})
        self.assertEqual(runner.state['jobs']['recover']['prompt_id'], 'recover-1')

    def test_restart_after_submit_before_prompt_id_persisted(self):
        runner = self.runner(['restart'])
        digest = q.hashlib.sha256(json.dumps(json.loads(self.graph.read_text()), sort_keys=True).encode()).hexdigest()
        runner.state['jobs']['restart'] = {'status': 'submitting', 'attempts': 1,
                    'attempt_token': 'token123', 'submitted_at': q.time.time(), 'graph_sha256': digest}
        runner.save()
        self.server.history['remote-existing'] = self.server.record('restart', 'remote-existing',
                {'durable_job_id': 'restart', 'durable_attempt_token': 'token123'})
        resumed = self.runner(['restart'])
        self.assertEqual(self.run_silently(resumed), 0)
        self.assertEqual(self.server.count, {})
        self.assertEqual(resumed.state['jobs']['restart']['prompt_id'], 'remote-existing')

    def test_unresolved_submission_never_blindly_retries(self):
        runner = self.runner(['unknown', 'later'])
        digest = q.hashlib.sha256(json.dumps(json.loads(self.graph.read_text()), sort_keys=True).encode()).hexdigest()
        runner.state['jobs']['unknown'] = {'status': 'submitting', 'attempts': 1,
                    'attempt_token': 'lost-token', 'submitted_at': q.time.time(), 'graph_sha256': digest}
        runner.save()
        self.assertEqual(self.run_silently(runner), 1)
        self.assertEqual(self.server.count, {'later': 1})
        self.assertEqual(runner.state['jobs']['unknown']['status'], 'submission_unknown')

    def test_duplicate_runner_lock(self):
        runner = self.runner(['job'])
        lock_path = self.root / 'state/runner.lock'
        with q.process_lock(lock_path):
            proc = subprocess.run([sys.executable, '-c',
                    'import durable_comfy_queue as q;\nwith q.process_lock(' + repr(str(lock_path)) + '): pass'],
                    cwd=Path(q.__file__).parent, capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('Another runner holds', proc.stderr)
        self.assertEqual(self.server.count, {})

    def test_progress_stall_preserves_prompt_for_resume(self):
        runner = self.runner(['stalled', 'later'])
        digest = q.hashlib.sha256(json.dumps(json.loads(self.graph.read_text()), sort_keys=True).encode()).hexdigest()
        runner.state['jobs']['stalled'] = {'status': 'submitted', 'prompt_id': 'still-running', 'attempts': 1,
                   'attempt_token': 'token', 'submitted_at': q.time.time(), 'graph_sha256': digest}
        self.assertEqual(self.run_silently(runner), 2)
        self.assertEqual(runner.state['jobs']['stalled']['prompt_id'], 'still-running')
        self.assertEqual(self.server.count, {})

    def test_sampling_events_only_match_current_prompt(self):
        events = self.root / 'sampling.jsonl'
        events.write_text('\n'.join(json.dumps(row) for row in [
            {'prompt_id': 'old', 'event': 'sampling_step', 'duration_seconds': 999},
            {'prompt_id': 'new', 'event': 'sampling_start', 'timestamp': 10},
            {'prompt_id': 'new', 'event': 'sampling_step', 'duration_seconds': 2},
            {'prompt_id': 'new', 'event': 'sampling_step', 'duration_seconds': 3},
            {'prompt_id': 'new', 'event': 'sampling_end', 'timestamp': 15}]))
        timing = q.timing({}, {'sampling_events_path': str(events)}, 'new')
        self.assertEqual(timing['sampling_seconds'], 5)
        self.assertEqual(timing['mean_sampling_step_seconds'], 2.5)

    def test_manifest_append_is_loaded_after_current_job(self):
        runner = self.runner(['first'])
        original_log = runner.log
        def append_on_complete(event, **fields):
            original_log(event, **fields)
            if event == 'completed' and fields['job_id'] == 'first':
                manifest_path = Path(runner.args.manifest)
                manifest = json.loads(manifest_path.read_text())
                manifest['jobs'].append({'id': 'added', 'graph': str(self.graph), 'expected_output_prefix': 'added'})
                q.atomic_json(manifest_path, manifest)
        runner.log = append_on_complete
        self.assertEqual(self.run_silently(runner), 0)
        self.assertEqual(self.server.count, {'first': 1, 'added': 1})

    def test_attempt_run_id_replacement_and_timing_file(self):
        self.graph.write_text(json.dumps({'1': {'class_type': 'Mock', 'inputs': {
            'run_id': 'old-run-id', 'path': 'audit/{attempt_id}/{run_id}.json', 'seed': 123}}}))
        runner = self.runner(['first'])
        manifest_path = Path(runner.args.manifest)
        manifest = json.loads(manifest_path.read_text())
        manifest['jobs'][0]['metadata'] = {'timing_file': str(self.root / '{attempt_id}.json')}
        q.atomic_json(manifest_path, manifest)
        (self.root / 'first__a2.json').write_text(json.dumps({'sampler_wall_seconds': 13, 'per_step_seconds': [5, 6]}))
        self.server.fail_once.add('first')
        self.assertEqual(self.run_silently(runner), 0)
        first, second = self.server.payloads
        self.assertEqual(first['prompt']['1']['inputs']['run_id'], 'first__a1')
        self.assertEqual(second['prompt']['1']['inputs']['run_id'], 'first__a2')
        self.assertEqual(second['prompt']['1']['inputs']['path'], 'audit/first__a2/first__a2.json')
        self.assertEqual(second['prompt']['1']['inputs']['seed'], 123)
        result = json.loads((self.root / 'state/results/first.json').read_text())
        self.assertEqual(result['timing']['sampling_seconds'], 13)
        self.assertEqual(result['timing']['mean_sampling_step_seconds'], 5.5)

    def test_owned_service_restart_marks_lost_execution_failed(self):
        runner = self.runner(['first'])
        marker = self.root / 'restarted'
        runner.args.restart_after_seconds = 0
        runner.args.restart_command = json.dumps([sys.executable, '-c',
                'from pathlib import Path; Path(' + repr(str(marker)) + ').write_text("ready")'])
        class DownUntilRestart:
            def call(self, path):
                if not marker.exists():
                    raise OSError('owned service exited')
                return {'queue_running': [], 'queue_pending': []} if path == '/queue' else {}
        runner.api = DownUntilRestart()
        with contextlib.redirect_stdout(io.StringIO()):
            outcome, record = runner.poll({'id': 'first'}, {'prompt_id': 'lost'})
        self.assertEqual(outcome, 'failed')
        self.assertTrue(marker.exists())
        self.assertEqual(record['status']['messages'][0][0], 'managed_service_restart')

    def test_invalid_graph_continues_to_next_job(self):
        runner = self.runner(['broken', 'next'])
        manifest_path = Path(runner.args.manifest)
        manifest = json.loads(manifest_path.read_text())
        manifest['jobs'][0]['graph'] = str(self.root / 'missing.json')
        q.atomic_json(manifest_path, manifest)
        self.assertEqual(self.run_silently(runner), 1)
        self.assertEqual(self.server.count, {'next': 1})


if __name__ == '__main__':
    unittest.main()
