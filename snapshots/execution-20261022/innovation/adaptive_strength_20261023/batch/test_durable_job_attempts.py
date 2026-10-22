"""Per-job retry limits; inherits the existing queue's complete regression suite."""
import json

import test_durable_comfy_queue_base as base


class JobAttemptLimitTests(base.QueueTests):
    def limits(self, runner, overrides, global_limit=3):
        runner.args.max_attempts = global_limit
        path = base.Path(runner.args.manifest)
        manifest = json.loads(path.read_text())
        for job in manifest['jobs']:
            if job['id'] in overrides:
                job['max_attempts'] = overrides[job['id']]
        base.q.atomic_json(path, manifest)

    def pending_state(self, runner, job_id, status='submitting', attempts=1, prompt_id=None):
        digest = base.q.hashlib.sha256(json.dumps(json.loads(self.graph.read_text()), sort_keys=True).encode()).hexdigest()
        state = {'status': status, 'attempts': attempts, 'attempt_token': 'token-limit',
                 'submitted_at': base.q.time.time(), 'graph_sha256': digest}
        if prompt_id is not None:
            state['prompt_id'] = prompt_id
        runner.state['jobs'][job_id] = state
        runner.save()

    def test_job_limit_one_and_default_global_limit_continue_queue(self):
        self.server.always_fail.update(['limited', 'default'])
        runner = self.runner(['limited', 'default', 'good'])
        self.limits(runner, {'limited': 1}, global_limit=3)
        self.assertEqual(self.run_silently(runner), 1)
        self.assertEqual(self.server.count, {'limited': 1, 'default': 3, 'good': 1})
        self.assertEqual(runner.state['jobs']['limited']['attempts'], 1)
        self.assertEqual(runner.state['jobs']['limited']['status'], 'failed')

    def test_lower_job_limit_allows_exactly_requested_attempts(self):
        self.server.always_fail.add('limited')
        runner = self.runner(['limited'])
        self.limits(runner, {'limited': 2}, global_limit=3)
        self.assertEqual(self.run_silently(runner), 1)
        self.assertEqual(self.server.count, {'limited': 2})

    def test_invalid_job_limits_do_not_submit_and_continue(self):
        invalid = [0, -1, True, False, 1.0, '1', None, 4, [], {}]
        ids = ['invalid_' + str(i) for i in range(len(invalid))]
        runner = self.runner(ids + ['good'])
        self.limits(runner, dict(zip(ids, invalid)), global_limit=3)
        self.assertEqual(self.run_silently(runner), 1)
        self.assertEqual(self.server.count, {'good': 1})
        for job_id in ids:
            self.assertEqual(runner.state['jobs'][job_id]['status'], 'invalid')
            self.assertIn('max_attempts', runner.state['jobs'][job_id]['error'])

    def test_limit_one_accepted_connection_drop_recovers_once(self):
        self.server.disconnect_once = True
        runner = self.runner(['recover'])
        self.limits(runner, {'recover': 1})
        self.assertEqual(self.run_silently(runner), 0)
        self.assertEqual(self.server.count, {'recover': 1})
        self.assertEqual(runner.state['jobs']['recover']['attempts'], 1)

    def test_limit_one_restart_unknown_recovers_existing_without_post(self):
        runner = self.runner(['restart'])
        self.limits(runner, {'restart': 1})
        self.pending_state(runner, 'restart')
        self.server.history['existing'] = self.server.record('restart', 'existing',
            {'durable_job_id': 'restart', 'durable_attempt_token': 'token-limit'})
        resumed = base.q.Runner(runner.args)
        self.assertEqual(self.run_silently(resumed), 0)
        self.assertEqual(self.server.count, {})
        self.assertEqual(resumed.state['jobs']['restart']['prompt_id'], 'existing')

    def test_limit_one_unresolved_restart_never_resubmits(self):
        runner = self.runner(['unknown', 'later'])
        self.limits(runner, {'unknown': 1})
        self.pending_state(runner, 'unknown', status='submission_unknown')
        self.assertEqual(self.run_silently(runner), 1)
        resumed = base.q.Runner(runner.args)
        self.assertEqual(self.run_silently(resumed), 1)
        self.assertEqual(self.server.count, {'later': 1})
        self.assertEqual(resumed.state['jobs']['unknown']['status'], 'submission_unknown')
        self.assertEqual(resumed.state['jobs']['unknown']['attempts'], 1)

    def test_known_prompt_polled_even_if_persisted_attempts_exceed_new_limit(self):
        runner = self.runner(['existing'])
        self.limits(runner, {'existing': 1})
        self.pending_state(runner, 'existing', status='submitted', attempts=3, prompt_id='old-live')
        self.server.history['old-live'] = self.server.record('existing', 'old-live', {})
        self.assertEqual(self.run_silently(runner), 0)
        self.assertEqual(self.server.count, {})
        self.assertEqual(runner.state['jobs']['existing']['status'], 'completed')

    def test_recovered_failed_prompt_consumes_existing_single_attempt(self):
        runner = self.runner(['recover', 'later'])
        self.limits(runner, {'recover': 1})
        self.pending_state(runner, 'recover', status='submission_unknown')
        self.server.history['failed-existing'] = self.server.record('recover', 'failed-existing',
            {'durable_job_id': 'recover', 'durable_attempt_token': 'token-limit'}, fail=True)
        self.assertEqual(self.run_silently(runner), 1)
        self.assertEqual(self.server.count, {'later': 1})
        self.assertEqual(runner.state['jobs']['recover']['status'], 'failed')
        self.assertEqual(runner.state['jobs']['recover']['attempts'], 1)

    def test_exhausted_job_does_not_resubmit_after_restart(self):
        runner = self.runner(['failed', 'later'])
        self.limits(runner, {'failed': 1})
        self.pending_state(runner, 'failed', status='failed_attempt')
        resumed = base.q.Runner(runner.args)
        self.assertEqual(self.run_silently(resumed), 1)
        self.assertEqual(self.server.count, {'later': 1})
        self.assertEqual(resumed.state['jobs']['failed']['status'], 'failed')
