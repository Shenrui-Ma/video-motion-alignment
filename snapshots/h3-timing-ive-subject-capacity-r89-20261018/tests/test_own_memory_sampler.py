import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'audit'))
from own_memory_sampler import sample_owner, summarize


class OwnMemory(unittest.TestCase):
    def setUp(self):
        self.owner = {'pid': 123, 'gpu_uuid': 'GPU-own', 'identity': {'start_ticks': 77}}
    def sample(self, rows):
        return sample_owner(self.owner, lambda _: self.owner['identity'], lambda: rows)
    def test_foreign_usage_is_excluded(self):
        r = self.sample([{'pid': 2, 'gpu_uuid': 'GPU-own', 'used_memory_mib': '50000'},
                         {'pid': 123, 'gpu_uuid': 'GPU-own', 'used_memory_mib': '9000'}])
        self.assertEqual(r['own_memory_mib'], 9000)
    def test_unknown_probe_does_not_fabricate_zero(self):
        def fail(): raise TimeoutError('read timeout')
        r = sample_owner(self.owner, lambda _: self.owner['identity'], fail)
        self.assertEqual(r['status'], 'unknown')
        self.assertIsNone(summarize(self.owner, [r])['max_observed_own_memory_mib'])
    def test_reused_pid_is_rejected_before_query(self):
        def forbidden(): raise AssertionError('query must not run')
        r = sample_owner(self.owner, lambda _: {'start_ticks': 78}, forbidden)
        self.assertEqual(r['status'], 'identity_changed')
    def test_wrong_gpu_unknown(self):
        r = self.sample([{'pid': 123, 'gpu_uuid': 'GPU-other', 'used_memory_mib': '1'}])
        self.assertEqual(r['status'], 'unknown')
    def test_peak_uses_valid_own_samples_only(self):
        rows = [self.sample([])]
        for value in [100, 75, 80]:
            rows.append(self.sample([{'pid': 123, 'gpu_uuid': 'GPU-own', 'used_memory_mib': value}]))
        s = summarize(self.owner, rows)
        self.assertEqual(s['max_observed_own_memory_mib'], 100)
        self.assertFalse(s['true_allocator_peak_measured'])
    def test_exact_absence_is_terminal(self):
        r = sample_owner(self.owner, lambda _: None, lambda: [])
        self.assertEqual(r['status'], 'process_absent')


if __name__ == '__main__': unittest.main()
