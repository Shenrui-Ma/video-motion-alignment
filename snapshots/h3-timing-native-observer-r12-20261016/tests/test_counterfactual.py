from pathlib import Path
import hashlib
import tempfile
import unittest
from unittest.mock import patch
import torch

from counterfactual_support import make_state, execute, run_blocks, cpu_attention, observation
from H3NativeObserverRouter.core import Config, INPUT_STEPS, selection_decision, condition_signature, readout, router

torch.set_num_threads(1)
LAGS = [12, 3, 4, 3, 0, None, -3, 4, 3, 2, 4, -4, None, 4, 4]
EXPECTED = [7, 8, 12, 13, 15, 18, 19]


def single_forward(state, calls, chosen, mask, directory, name='baseline'):
    baseline = router.RouterState({'refs': []}, 'mass_preserve', 1.0, 0, 0, 50, 65, 0, 50, 6, 20, name, str(directory))
    baseline.plan_for = state.plan_for
    baseline.selected = lambda block: baseline.forward_index in mask and 0 <= block < 50
    patches = {('double_block', i): router.EventBlockPatch(baseline, i) for i in range(50)}
    x = calls[0][2].clone(); grid = torch.linspace(1, 0, 21)
    with cpu_attention():
        for n in range(20):
            value = run_blocks(baseline, patches, sigmas=grid)
            y = x * .25 + value.mean() * .001
            assert torch.equal(y, chosen[n]), ('chosen mismatch', n)
            x = x + (x-y) / grid[n] * (grid[n+1]-grid[n])
    return x


class NativeObserverTests(unittest.TestCase):
    def test_dynamic_nfe_same_input_archives_and_single_euler_trajectory(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(Path(tmp), lags=LAGS)
            rng = torch.random.get_rng_state().clone()
            result, calls, chosen = execute(state, nested_callback=True)
            self.assertTrue(torch.equal(rng, torch.random.get_rng_state()))
            self.assertEqual(state.callback_count, 20)
            self.assertEqual(state.audit['completed_calls'], 50 * (20 + len(EXPECTED)))
            self.assertEqual(state.audit['routed_calls'], 50 * len(EXPECTED))
            self.assertEqual(state.full_indices, EXPECTED)
            self.assertEqual(len(calls), 27); self.assertEqual(len(chosen), 20)
            for i in EXPECTED:
                pair = [call for call in calls if call[0] == i]
                self.assertEqual([p[1] for p in pair], ['native', 'full'])
                self.assertTrue(torch.equal(pair[0][2], pair[1][2]))
                self.assertTrue(torch.equal(pair[0][3], pair[1][3]))
            self.assertTrue(torch.equal(single_forward(state,calls,chosen,EXPECTED,tmp), result))
            rows = state.audit['counterfactual']['steps']
            self.assertIsNone(rows[5]['decision']['observer_proposed_full'])
            self.assertFalse(rows[6]['decision']['previous_actual_full'])
            self.assertEqual(rows[6]['decision']['observer_reason'], 'HOLD_LAG3')
            self.assertEqual(rows[19]['selected_branch'], 'full')
            for i in INPUT_STEPS:
                data = torch.load(state.snapshots/f'step{i:03d}_input_raw.pt', weights_only=True)
                self.assertTrue(torch.equal(data['packed'], next(c[2] for c in calls if c[0] == i)))
            for row in state.audit['counterfactual']['branches']:
                data = torch.load(row['file'], weights_only=True)
                self.assertEqual([readout.tensor_signature(data[k]) for k in ('video','audio')], row['normalized_stream_signatures'])
            self.assertEqual(state.audit['status'], 'complete')

    def test_off_is_exact_native_and_fixed_ignores_observer(self):
        with tempfile.TemporaryDirectory() as tmp:
            off = make_state(Path(tmp), lags=[12], policy='off', run_id='off')
            result, calls, chosen = execute(off)
            self.assertEqual(off.full_indices, [])
            self.assertEqual(off.audit['completed_forward_calls'], 20)
            self.assertTrue(torch.equal(single_forward(off,calls,chosen,[],tmp,'native'), result))
            fixed = make_state(Path(tmp), lags=[None], policy='fixed', fixed=','.join(map(str, EXPECTED)), run_id='fixed')
            result, calls, chosen = execute(fixed)
            self.assertEqual(fixed.full_indices, EXPECTED)
            self.assertTrue(torch.equal(single_forward(fixed,calls,chosen,EXPECTED,tmp,'fixed_reference'), result))

    def test_current_gate_boundaries_and_first_last_eligibility(self):
        c = Config('case', '/tmp/r12-tests')
        self.assertFalse(selection_decision(c,5,observation(24),False)['chosen_full'])
        self.assertFalse(selection_decision(c,6,observation(3),False)['chosen_full'])
        self.assertTrue(selection_decision(c,6,observation(4),False)['chosen_full'])
        self.assertTrue(selection_decision(c,19,observation(4),False)['chosen_full'])
        self.assertTrue(selection_decision(c,10,observation(3),True)['chosen_full'])
        for lag in [-24,-3,-2,0,2,None]:
            self.assertFalse(selection_decision(c,10,observation(lag),True)['chosen_full'])
        with self.assertRaises(ValueError):selection_decision(c,6,None,False)
        for index in [-1,20,True]:
            with self.assertRaises(ValueError):selection_decision(c,index,observation(4),False)
        for fixed in ['5','20','7,6','6,6','6,','a']:
            with self.assertRaises(ValueError):Config('case','/tmp/r12',policy='fixed',fixed_indices=fixed)
        with self.assertRaises(ValueError):Config('case','/tmp/r12',policy='native_observer',fixed_indices='6')

    def test_fail_closed_negative_cases(self):
        for failure in ('wrong_sigma','double_forward','rng','input_mutation','condition_mutation','duplicate_callback','duplicate_prediction','grid_mutation'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                state = make_state(Path(tmp))
                with self.assertRaises(ValueError):execute(state,fail=failure)
                self.assertEqual(state.audit['status'],'failed')
                self.assertTrue(state.finished);self.assertIsNone(state.phase)

    def test_cpu_timestep_snapshot_does_not_alias_mutated_sigma(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(Path(tmp))
            with self.assertRaisesRegex(ValueError, 'branch timestep mutated'):
                execute(state, fail='timestep_mutation')
            self.assertEqual(state.audit['status'], 'failed')

    def test_callback_error_exclusive_run_and_single_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(Path(tmp))
            with self.assertRaises(FileExistsError):make_state(Path(tmp))
            def bad_callback(*args):raise RuntimeError('consumer failed')
            with self.assertRaisesRegex(RuntimeError,'consumer failed'):execute(state,callback=bad_callback)
            self.assertEqual(state.audit['status'],'failed');self.assertEqual(state.callback_count,1)
            with self.assertRaisesRegex(ValueError,'single-use'):execute(state)

    def test_observer_and_protocol_frozen(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual((root/'extensions/H3NativeObserverRouter/observer.py').read_bytes(), (root/'audit/parent_observer.py').read_bytes())
        self.assertEqual(hashlib.sha256((root/'configs/protocol.json').read_bytes()).hexdigest(), '36ed6f433f4ee26ac06be136a275a171f11c6c16bf6c91fd3697d2e27b6f6807')

if __name__ == '__main__':unittest.main()
