import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import torch
from test_feedback_support import make_state, execute_toy
from H3X0Readout.core import CAPTURE_STEPS

ROOT = Path(__file__).resolve().parents[1]

class NativeScreenTests(unittest.TestCase):
    def test_off_ignores_every_observation_and_uses20forward(self):
        with tempfile.TemporaryDirectory() as d:
            bad = make_state(d, [13, 7, None, -7, 3, 0, 13, 13, 13, 13, 13, 13, 13, 13, 13],
                             policy='off', run_id='bad')
            aligned = make_state(d, [0], policy='off', run_id='aligned')
            a, b = execute_toy(bad), execute_toy(aligned)
            self.assertTrue(torch.equal(a, b))
            self.assertEqual(bad.active_indices, [])
            self.assertEqual(bad.audit['completed_forward_calls'], 20)
            self.assertEqual(bad.audit['completed_calls'], 1000)
            self.assertEqual(bad.audit['routed_calls'], 0)
            self.assertEqual(bad.audit['feedback']['callback_count'], 20)
            self.assertEqual(len(bad.audit['feedback']['observations']), 15)
            self.assertTrue(all(not row['current_forward_active'] for row in bad.audit['feedback']['observations']))

    def test_no_reserve_job_and_expected_snapshots(self):
        p = json.loads((ROOT / 'configs/protocol.json').read_text())
        queue = json.loads((ROOT / 'configs/queue.json').read_text())
        self.assertEqual(p['seed'], 2026101313)
        self.assertEqual(p['reserve_seed_not_queued'], 2026101314)
        self.assertEqual(queue['jobs'], [p['formal_run']])
        self.assertTrue(queue['sealed'])
        self.assertEqual(CAPTURE_STEPS, (5, 6, 7, 8, 9, 10, 15, 19))
        self.assertTrue(p['recording']['sampler_final'])
        self.assertEqual(p['routing_policy'], 'off')

    def test_every_runtime_extension_identical_to_verified_r11_except_root(self):
        m = json.loads((ROOT / 'configs/runtime_copy_manifest.json').read_text())
        for rel, h in m['parent_runtime_sha256'].items():
            raw = (ROOT / rel).read_bytes().replace(b'timing_native_screen_r14_20261016',
                                                  b'timing_schedule_controls_r11_20261016')
            self.assertEqual(hashlib.sha256(raw).hexdigest(), h, rel)

if __name__ == '__main__': unittest.main()
