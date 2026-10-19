import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('watch', HERE / 'watch_pairs.py')
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)
spec2 = importlib.util.spec_from_file_location('phases', HERE / 'run_cpu_phase.py')
phases = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(phases)


class CPUWatcherTests(unittest.TestCase):
    def test_both_actual_jobs_and_histories_required(self):
        jobs = [{'method': m, 'job': 'success', 'history': {'completed': True, 'status_str': 'success'}} for m in ('native', 'forced')]
        self.assertTrue(watch.jobs_complete(jobs))
        jobs[1]['job'] = 'pending_or_running'
        self.assertFalse(watch.jobs_complete(jobs))
        jobs[1]['job'] = 'success'
        jobs[1]['history'] = {}
        self.assertFalse(watch.jobs_complete(jobs))

    def test_duplicate_or_missing_method_rejected(self):
        row = {'method': 'native', 'job': 'success', 'history': {'completed': True, 'status_str': 'success'}}
        self.assertFalse(watch.jobs_complete([row]))
        self.assertFalse(watch.jobs_complete([row, row]))

    def test_allowed_phases_have_no_gpu_or_service_command(self):
        self.assertEqual(phases.ALLOWED, {'verify_pair', 'collect_pair', 'prepare_pair', 'score_one', 'summarize', 'make_triptych', 'make_checkpoints'})


if __name__ == '__main__':
    unittest.main()
