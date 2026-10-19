import tempfile
import unittest

import torch

from test_feedback_support import execute_toy, make_state


class FixedScheduleControlTests(unittest.TestCase):
    def test_both_fixed_schedules_have_exact_routes_and_ignore_observer(self):
        for mask in (list(range(6, 20)), [6, *range(8, 15)]):
            with self.subTest(mask=mask), tempfile.TemporaryDirectory() as directory:
                outputs = []
                for name, lags in [('delay', [12]), ('aligned', [0]), ('unknown', [None])]:
                    state = make_state(directory, lags, policy='fixed',
                                       fixed=','.join(map(str, mask)), run_id=name)
                    outputs.append(execute_toy(state))
                    self.assertEqual(state.active_indices, mask)
                    self.assertEqual(state.audit['completed_forward_calls'], 20)
                    self.assertEqual(state.audit['completed_calls'], 1000)
                    self.assertEqual(state.audit['calls_by_forward'], [50] * 20)
                    self.assertEqual(state.audit['routed_by_forward'],
                                     [50 if i in mask else 0 for i in range(20)])
                    self.assertEqual(sum(state.audit['routed_by_forward']), len(mask) * 50)
                    self.assertEqual([r['active'] for r in state.latched[:6]], [False] * 6)
                    self.assertEqual([r['forward_index'] for r in state.latched], list(range(20)))
                    records = state.audit['feedback']['observations']
                    for row in records[:-1]:
                        self.assertEqual(row['next_active'], row['next_forward_index'] in mask)
                        self.assertEqual(row['applied_reason'], 'FIXED_MASK')
                    self.assertIsNone(records[-1]['next_active'])
                    self.assertEqual(state.audit['status'], 'complete')
                self.assertTrue(torch.equal(outputs[0], outputs[1]))
                self.assertTrue(torch.equal(outputs[0], outputs[2]))

    def test_empty_fixed_schedule_is_bitwise_off_even_with_delayed_observer(self):
        with tempfile.TemporaryDirectory() as directory:
            fixed = make_state(directory, [12], policy='fixed', fixed='', run_id='fixed')
            off = make_state(directory, [12], policy='off', run_id='off')
            self.assertTrue(torch.equal(execute_toy(fixed), execute_toy(off)))
            self.assertEqual(fixed.active_indices, [])
            self.assertEqual(fixed.audit['routed_by_forward'], [0] * 20)


if __name__ == '__main__':
    unittest.main()
