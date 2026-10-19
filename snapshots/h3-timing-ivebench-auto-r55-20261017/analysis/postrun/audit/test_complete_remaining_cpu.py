import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).with_name('complete_remaining_cpu.py')
spec = importlib.util.spec_from_file_location('remaining', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CompletionTests(unittest.TestCase):
    def test_pending_files_do_not_imply_failure(self):
        self.assertEqual(module.readiness({}, {}), 'pending')
        self.assertEqual(module.readiness({}, {'status': 'pending_or_running'}), 'pending')

    def test_both_success_records_required(self):
        h = {'status': {'completed': True, 'status_str': 'success'}}
        self.assertEqual(module.readiness(h, {'status': 'pending_or_running'}), 'pending')
        self.assertEqual(module.readiness(h, {'status': 'success'}), 'ready')

    def test_actual_failure_is_retained(self):
        self.assertEqual(module.readiness({'status': {'status_str': 'error'}}, {}), 'failed')
        self.assertEqual(module.readiness({}, {'status': 'submission_uncertain'}), 'failed')

    def test_reuse_requires_both_real_identity_proofs(self):
        s = {'proofs': {'full_video': {'exact': True}, 'score_video': {'exact': True}}}
        self.assertTrue(module.exact_for_reuse(s))
        s['proofs']['full_video']['exact'] = False
        self.assertFalse(module.exact_for_reuse(s))
        s['proofs']['full_video']['exact'] = True
        s['proofs']['score_video']['exact'] = False
        self.assertFalse(module.exact_for_reuse(s))


if __name__ == '__main__':
    unittest.main()
