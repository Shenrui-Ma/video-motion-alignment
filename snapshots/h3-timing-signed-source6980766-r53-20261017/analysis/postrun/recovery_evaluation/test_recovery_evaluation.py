import json
from pathlib import Path
import tempfile
import unittest
import evaluate_recovered as e


class RecoveryBindingTests(unittest.TestCase):
    def fixture(self, root):
        (root / 'recovered_final.mp4').write_bytes(b'video fixture')
        self.write(root / 'FINAL_EULER.json', {'original_run_completed': False, 'step14_exact': True, 'final_CPU_GPU_exact': True})
        final = {'status': 'cross_host_recovered_final_video', 'original_run_completed': False,
                 'final_euler_sha256': e.sha(root / 'FINAL_EULER.json'),
                 'outputs': {'recovered_final': {'file_sha256': e.sha(root / 'recovered_final.mp4'), 'status': 'complete'}}}
        self.write(root / 'RECOVERY_FINAL.json', final)
        identity = {'pid': 123, 'uid': 1004, 'start_ticks': 100}
        self.write(root / 'RELEASED.json', {'status': 'released', 'RECOVERY_FINAL_sha256': e.sha(root / 'RECOVERY_FINAL.json'),
                                         'child': {'returncode': 0, 'process': identity},
                                         'release': {'schema': 'h3-own-decoder-release-v1', 'child_identity': identity,
                                                     'original_generation_absent': True, 'nvml_pid_absent': True,
                                                     'pid_reused': False, 'other_compute_pids': []}})
        return final

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value))

    def test_explicit_recovery_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.fixture(root)
            self.assertEqual(e.verify_recovery(root)[0], root / 'recovered_final.mp4')

    def test_same_host_recovery_requires_own_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            final = self.fixture(root)
            final.update(status='same_host_recovered_final_video', same_host_comparison={})
            final['outputs']['recovered_final']['cross_host'] = False
            arithmetic = e.read(root / 'FINAL_EULER.json')
            arithmetic['cross_host'] = False
            self.write(root / 'FINAL_EULER.json', arithmetic)
            final['final_euler_sha256'] = e.sha(root / 'FINAL_EULER.json')
            self.write(root / 'RECOVERY_FINAL.json', final)
            release = e.read(root / 'RELEASED.json')
            release['RECOVERY_FINAL_sha256'] = e.sha(root / 'RECOVERY_FINAL.json')
            self.write(root / 'RELEASED.json', release)
            self.assertEqual(e.verify_recovery(root)[0], root / 'recovered_final.mp4')
            final['outputs']['recovered_final']['cross_host'] = True
            self.write(root / 'RECOVERY_FINAL.json', final)
            with self.assertRaisesRegex(ValueError, 'same-host'):
                e.verify_recovery(root)

    def test_changed_video_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.fixture(root)
            (root / 'recovered_final.mp4').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'video changed'):
                e.verify_recovery(root)

    def test_original_success_fabrication_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            final = self.fixture(root)
            final['original_run_completed'] = True
            self.write(root / 'RECOVERY_FINAL.json', final)
            with self.assertRaisesRegex(ValueError, 'explicit recovered'):
                e.verify_recovery(root)

    def test_unreleased_child_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.fixture(root)
            release = e.read(root / 'RELEASED.json')
            release['release']['original_generation_absent'] = False
            self.write(root / 'RELEASED.json', release)
            with self.assertRaisesRegex(ValueError, 'child release'):
                e.verify_recovery(root)

    def test_unrelated_process_does_not_block_own_release(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.fixture(root)
            release = e.read(root / 'RELEASED.json')
            release['release']['other_compute_pids'] = [456]
            self.write(root / 'RELEASED.json', release)
            self.assertEqual(e.verify_recovery(root)[0], root / 'recovered_final.mp4')

    def test_online_priority_uses_pending_sampler_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            preflight = root / 'audit/observations/known_endpoint_158_split_v2'
            preflight.mkdir(parents=True)
            for name in ('request.json', 'native.json'):
                self.write(preflight / name, {})
            self.assertIsNone(e.pending_online([root]))
            live = preflight.parent / 'step006_actual'
            live.mkdir()
            for name in ('request.json', 'native.json'):
                self.write(live / name, {})
            self.assertEqual(e.pending_online([root]), str(live))
            self.write(live / 'failure.json', {})
            self.assertIsNone(e.pending_online([root]))

    def test_table_keeps_unknown_and_all_windows(self):
        windows = [[0, 31], [32, 63], [64, 95], [96, 127], [125, 140], [0, 140]]
        fixed = {name: {str(c): {'status': 'unknown_visibility', 'diagnostics': []} for c in [.3, .5]}
                 for name in ['native', 'recovered_signed_auto']}
        rows = e.table_rows(fixed, {str(c): {'rows': []} for c in [.3, .5]}, windows, [.3, .5])
        self.assertEqual(len(rows), 36)
        self.assertEqual({(r['window_start'], r['window_end']) for r in rows}, {tuple(w) for w in windows})
        self.assertTrue(all(r['native_lag_frames'] == r['recovered_signed_auto_lag_frames'] == 'UNKNOWN' for r in rows))


if __name__ == '__main__':
    unittest.main()
