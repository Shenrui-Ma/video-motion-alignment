from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
import torch

from counterfactual_support import make_state, execute, run_blocks, cpu_attention
from H3CounterfactualRouter.core import FULL_STEPS, INPUT_STEPS, condition_signature, readout, router

torch.set_num_threads(1)

class CounterfactualTests(unittest.TestCase):
    def test_fixed29_nfe_same_input_all_archives_and_euler_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = make_state(Path(tmp), lags=(None, -20, 20, 0))
            rng = torch.random.get_rng_state().clone()
            result, calls, chosen = execute(state, nested_callback=True)
            self.assertTrue(torch.equal(rng, torch.random.get_rng_state()))
            self.assertEqual(state.callback_count, 20)
            self.assertEqual(state.audit['completed_calls'], 1450)
            self.assertEqual(state.audit['routed_calls'], 450)
            self.assertEqual(len(calls), 29)
            self.assertEqual(len(chosen), 20)
            self.assertEqual([i for i, branch, *_ in calls if branch=='full'], list(FULL_STEPS))
            for i in FULL_STEPS:
                pair=[call for call in calls if call[0]==i]
                self.assertEqual([p[1] for p in pair],['native','full'])
                self.assertTrue(torch.equal(pair[0][2],pair[1][2]))
                self.assertTrue(torch.equal(pair[0][3],pair[1][3]))
            # Independent one-call-per-step reference uses unchanged old router.
            baseline=router.RouterState({'refs':[]},'mass_preserve',1.0,0,0,50,65,0,50,6,15,'baseline',tmp)
            baseline.plan_for=state.plan_for
            patches={('double_block',i):router.EventBlockPatch(baseline,i) for i in range(50)}
            x=calls[0][2].clone();grid=torch.linspace(1,0,21)
            with cpu_attention():
                for n in range(20):
                    value=run_blocks(baseline,patches,sigmas=grid)
                    y=x*0.25+value.mean()*0.001
                    self.assertTrue(torch.equal(y,chosen[n]), n)
                    x=x+(x-y)/grid[n]*(grid[n+1]-grid[n])
            self.assertTrue(torch.equal(x,result))
            for i in INPUT_STEPS:
                payload=torch.load(state.snapshots/f'step{i:03d}_input_raw.pt',weights_only=True)
                self.assertTrue(torch.equal(payload['packed'], next(c[2] for c in calls if c[0]==i)))
                self.assertEqual(payload['metadata']['full_grid'],grid.double().tolist())
            for row in state.audit['counterfactual']['branches']:
                data=torch.load(row['file'],weights_only=True)
                self.assertEqual([readout.tensor_signature(data[k]) for k in ('video','audio')],row['normalized_stream_signatures'])
            self.assertEqual(state.audit['status'],'complete')

    def test_zero_correction_native_noop(self):
        with tempfile.TemporaryDirectory() as tmp, patch('counterfactual_support.ZERO_VALUES', True):
            state = make_state(Path(tmp))
            result, calls, chosen = execute(state)
            x = calls[0][2].clone(); grid = torch.linspace(1,0,21)
            for n in range(20):
                y = x*0.25
                self.assertTrue(torch.equal(y,chosen[n]))
                x = x + (x-y)/grid[n]*(grid[n+1]-grid[n])
            self.assertTrue(torch.equal(result,x))
            self.assertEqual(state.audit['completed_forward_calls'],29)

    def test_fail_closed_negative_cases(self):
        for failure in ('wrong_sigma','double_forward','rng','input_mutation','condition_mutation','duplicate_callback'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                state=make_state(Path(tmp))
                with self.assertRaises(ValueError): execute(state,fail=failure)
                self.assertEqual(state.audit['status'],'failed')
                self.assertTrue(state.finished)
                self.assertIsNone(state.phase)

    def test_callback_error_and_exclusive_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=make_state(Path(tmp))
            with self.assertRaises(FileExistsError):make_state(Path(tmp))
            def bad_callback(*args):raise RuntimeError('consumer failed')
            with self.assertRaisesRegex(RuntimeError,'consumer failed'):execute(state,callback=bad_callback)
            self.assertEqual(state.audit['status'],'failed')
            self.assertEqual(state.callback_count,1)

    def test_protocol_frozen(self):
        root=Path(__file__).resolve().parents[1]
        self.assertEqual(hashlib.sha256((root/'configs/protocol.json').read_bytes()).hexdigest(),
                         'a0fd7bfe97f50a0efcf7939799544fe7fbe15dc9b5144d5da695a13b21a61465')

if __name__=='__main__':unittest.main()
