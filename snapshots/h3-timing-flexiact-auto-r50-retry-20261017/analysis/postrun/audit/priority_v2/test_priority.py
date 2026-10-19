import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from priority import pending, terminal_failure


class Priority(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.step = self.root / 'audit/observations/step000'
        for path in (self.step, self.root / 'logs', self.root / 'processes'):
            path.mkdir(parents=True)
        self.write(self.step / 'request.json', {'run_id': 'case'})
        self.write(self.step / 'native.json', {'complete': True})
        self.write(self.step / 'failure.json', {'error': 'failed', 'request_sha256': hashlib.sha256((self.step / 'request.json').read_bytes()).hexdigest()})
        self.write(self.root / 'logs/controller_state.json', {'status': 'failed', 'current': 'case'})
        self.write(self.root / 'processes/service.json', {'pid': 12, 'identity': {'uid': 1, 'start_ticks': '20'}})

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, p, value):
        p.write_text(json.dumps(value))

    def test_terminal_absent_does_not_block(self):
        self.assertFalse(pending([self.root], lambda p: None))

    def test_same_generation_still_has_priority(self):
        self.assertTrue(pending([self.root], lambda p: {'uid': 1, 'start_ticks': '20'}))

    def test_reused_pid_is_not_old_generation(self):
        self.assertFalse(pending([self.root], lambda p: {'uid': 1, 'start_ticks': '21'}))

    def test_active_request_priority(self):
        (self.step / 'failure.json').unlink()
        self.assertTrue(pending([self.root], lambda p: None))

    def test_ambiguous_controller_has_priority(self):
        self.write(self.root / 'logs/controller_state.json', {'status': 'pending_or_running', 'current': 'case'})
        self.assertTrue(pending([self.root], lambda p: None))

    def test_unreadable_identity_has_priority(self):
        def denied(pid):
            raise PermissionError('proc unavailable')
        self.assertTrue(pending([self.root], denied))

    def test_different_failed_case_has_priority(self):
        self.write(self.root / 'logs/controller_state.json', {'status': 'failed', 'current': 'different'})
        self.assertTrue(pending([self.root], lambda p: None))

    def test_unbound_failure_has_priority(self):
        self.write(self.step / 'failure.json', {'error': 'failed', 'request_sha256': 'wrong'})
        self.assertTrue(pending([self.root], lambda p: None))


if __name__ == '__main__':
    unittest.main()
