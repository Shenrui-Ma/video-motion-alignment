import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import capacity_v1 as cap
import peer_support as batch


class Capacity(unittest.TestCase):
    def sample(self):
        return {'uid': 1016, 'cgroup_version': 1, 'host_available_bytes': 32 * cap.GIB,
                'host_oom_kill': 5, 'ancestors': [{'path': '/user.slice', 'current_bytes': 10 * cap.GIB,
                'max_bytes': 22 * cap.GIB, 'failcnt': 0, 'oom_control': {'under_oom': 0}}]}

    def test_limit(self):
        self.assertIsNone(cap.limit(9223372036854771712))
        self.assertEqual(cap.limit(12 * cap.GIB), 12 * cap.GIB)
        with self.assertRaises(ValueError): cap.limit(-1)

    def test_boundaries(self):
        value = self.sample(); self.assertTrue(cap.assess(value, 12)['passed'])
        value['ancestors'][0]['current_bytes'] += 1
        with self.assertRaises(AssertionError): cap.assess(value, 12)
        value['ancestors'][0]['max_bytes'] = 18 * cap.GIB
        value['ancestors'][0]['current_bytes'] = 10 * cap.GIB
        self.assertTrue(cap.assess(value, 8)['passed'])
        value['ancestors'][0]['current_bytes'] += 1
        with self.assertRaises(AssertionError): cap.assess(value, 8)

    def test_unlimited_still_requires_host(self):
        value = self.sample(); value['ancestors'][0]['max_bytes'] = None
        self.assertTrue(cap.assess(value, 12)['passed'])
        value['host_available_bytes'] -= 1
        with self.assertRaises(AssertionError): cap.assess(value, 12)

    def test_uid_and_active_oom(self):
        value = self.sample(); value['uid'] = 1004
        with self.assertRaises(AssertionError): cap.assess(value, 12)
        value = self.sample(); value['ancestors'][0]['oom_control']['under_oom'] = 1
        with self.assertRaises(AssertionError): cap.assess(value, 12)

    def test_oom_and_failure_detection(self):
        before = self.sample(); after = copy.deepcopy(before)
        self.assertTrue(cap.oom_delta(before, after)['passed'])
        after['host_oom_kill'] += 1
        self.assertFalse(cap.oom_delta(before, after)['passed'])
        after = copy.deepcopy(before); after['ancestors'][0]['failcnt'] += 1
        self.assertFalse(cap.oom_delta(before, after)['passed'])
        after = copy.deepcopy(before); after['host_oom_kill'] -= 1
        with self.assertRaises(AssertionError): cap.oom_delta(before, after)
        after = copy.deepcopy(before); after['ancestors'][0]['max_bytes'] += 1
        with self.assertRaises(AssertionError): cap.oom_delta(before, after)

    def test_actual_v1_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); proc = root / 'proc'; mount = root / 'memory'
            (proc / 'self').mkdir(parents=True)
            (proc / 'self/cgroup').write_text('8:memory:/user.slice\n1:name=systemd:/user.slice/session.scope\n')
            (proc / 'meminfo').write_text('MemAvailable: 40000000 kB\n')
            (proc / 'vmstat').write_text('oom_kill 0\n')
            for folder in (mount, mount / 'user.slice'):
                folder.mkdir(parents=True, exist_ok=True)
                (folder / 'memory.limit_in_bytes').write_text('9223372036854771712')
                (folder / 'memory.usage_in_bytes').write_text(str(100 * cap.GIB))
                (folder / 'memory.failcnt').write_text('0')
                (folder / 'memory.oom_control').write_text('oom_kill_disable 0\nunder_oom 0\n')
                (folder / 'memory.stat').write_text('hierarchical_memory_limit 9223372036854771712\n')
            value = cap.snapshot(proc, mount, uid=1016)
            self.assertEqual([x['path'] for x in value['ancestors']], ['/user.slice', '/'])
            self.assertTrue(cap.assess(value, 12)['passed'])

    def test_old_kernel_oom_counter_is_unknown(self):
        value = self.sample(); value['host_oom_kill'] = None
        result = cap.oom_delta(value, copy.deepcopy(value))
        self.assertTrue(result['passed']); self.assertIsNone(result['host_oom_kill_delta'])
        self.assertFalse(result['cumulative_host_oom_counter_available'])


class OwnedResources(unittest.TestCase):
    def test_foreign_process_allowed(self):
        with patch.object(batch.os, 'getuid', return_value=1016):
            result = batch.owned_check({'processes': [{'uid': 1000, 'pid': 2}]}, [], None, 'GPU-1')
        self.assertEqual(result['owned_devices'], ['GPU-1'])

    def test_unknown_own_process_rejected(self):
        with patch.object(batch.os, 'getuid', return_value=1016), self.assertRaises(AssertionError):
            batch.owned_check({'processes': [{'uid': 1016, 'pid': 2}]}, [], None, 'GPU-1')

    def test_peer_device_reserved(self):
        known = [{'owner': {'pid': 2, 'gpu_uuid': 'GPU-1'}, 'identity': {}}]
        with self.assertRaises(AssertionError): batch.owned_check({'processes': []}, known, None, 'GPU-1')

    def test_max_two_including_reserved(self):
        known = [{'owner': {'pid': i, 'gpu_uuid': 'GPU-' + str(i)}, 'identity': {}} for i in (2, 3)]
        with self.assertRaises(AssertionError): batch.owned_check({'processes': []}, known, None, 'GPU-1')

    def test_module_import_does_not_load_torch(self):
        self.assertNotIn('torch', sys.modules)


if __name__ == '__main__':
    unittest.main()
