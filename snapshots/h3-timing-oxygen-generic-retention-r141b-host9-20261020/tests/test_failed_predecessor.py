"""Failed batches require pinned root release evidence and fresh PID absence."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import predecessor


class FailedPredecessor(unittest.TestCase):
    def fixture(self):
        old = Path('/old')
        owner = {
            'pid': 2, 'identity': {'uid': 1016, 'cmdline': '/old/scripts/service_entry.py'},
            'gpu_uuid': 'gpu', 'port': 8612,
        }
        release = {
            'passed': True, 'pid': 2, 'identity': owner['identity'],
            'owned_pids': [1, 2, 3], 'owned_pids_absent': True, 'owned_CUDA_pids_absent': True,
            'cleanup_sha256': 's', 'sampling_started': False,
            'errors': [{'node_id': '51', 'node_type': 'H3PairConditionSnapshot'}],
        }
        values = {
            Path('/new/configs/predecessor.json'): {'required': [{
                'key': 'R141', 'kind': 'failed_screen_release', 'remote_root': '/old',
                'producer_seal_sha256': 's', 'runtime_sha256': 's',
                'required_attempt': 'failed', 'release_file': 'audit/ROOT_FAILED_ATTEMPT_RELEASE.json',
                'release_sha256': 's',
            }]},
            old / 'configs/runtime.json': {'remote_root': '/old', 'uid': 1016, 'gpu_uuid': 'gpu', 'port': 8612},
            old / 'audit/failed/STARTED.json': {'owner': owner, 'controller': {'pid': 3}},
            old / 'processes/service.json': owner,
            old / 'processes/cleanup.json': {'pid': 2, 'service_record': owner, 'process_absent': True, 'own_compute_absent': True},
            old / 'audit/ROOT_FAILED_ATTEMPT_RELEASE.json': release,
            old / 'audit/ROOT_DISPATCH.json': {'root': '/old', 'uid': 1016, 'pid': 1, 'argv': ['--attempt', 'failed']},
        }
        return values

    def check(self, values, identity=lambda _: None, processes=()):
        with patch.object(predecessor, 'read', side_effect=lambda p: copy.deepcopy(values[Path(p)])), \
                patch.object(predecessor, 'sha', return_value='s'):
            return predecessor.check(
                Path('/new'), ['R141=failed'], current_identity=identity,
                compute_processes=lambda: list(processes),
            )

    def test_exact_failed_release_admitted(self):
        self.assertTrue(self.check(self.fixture())['passed'])

    def test_live_wrapper_rejected(self):
        with self.assertRaisesRegex(ValueError, 'process or CUDA remains'):
            self.check(self.fixture(), identity=lambda pid: {'uid': 1016} if pid == 1 else None)

    def test_lingering_cuda_rejected(self):
        with self.assertRaisesRegex(ValueError, 'process or CUDA remains'):
            self.check(self.fixture(), processes=[{'pid': 2}])

    def test_missing_release_or_failed_cleanup_rejected(self):
        values = self.fixture()
        values[Path('/old/processes/cleanup.json')]['own_compute_absent'] = False
        with self.assertRaisesRegex(ValueError, 'cleanup differs'):
            self.check(values)
        values = self.fixture()
        del values[Path('/old/audit/ROOT_FAILED_ATTEMPT_RELEASE.json')]
        with self.assertRaises(KeyError):
            self.check(values)

    def test_wrong_root_generation_rejected(self):
        values = self.fixture()
        values[Path('/old/audit/ROOT_FAILED_ATTEMPT_RELEASE.json')]['identity'] = {'uid': 1016, 'cmdline': 'other'}
        with self.assertRaisesRegex(ValueError, 'root owner differs'):
            self.check(values)


if __name__ == '__main__':
    unittest.main()
