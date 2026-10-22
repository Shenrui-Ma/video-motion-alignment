import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "source_snapshot")]
import cpu_contract as contract
from router import core
import torch


def oracle(q, k, v):
    logits = q.float() @ k.float().transpose(-1, -2) / q.shape[-1] ** 0.5
    return logits.softmax(-1) @ v.float(), logits.logsumexp(-1)


def state_for(arm, step, alpha=1.0):
    state = object.__new__(core.RouterState)
    state.block_start, state.block_end = 0, 50
    state.step_start, state.step_end = contract.STAGES[arm]
    state.forward_index = step
    state.mode, state.alpha, state.radius, state.time_offset = "mass_preserve", alpha, 0, 0
    state.pending_stats = []
    state.audit = dict(native_override_calls=0, routed_calls=0, diagnostic_calls=0,
                       routed_by_block=[0] * 50, routed_by_forward=[0] * 20)
    return state


class CPUContractTests(unittest.TestCase):
    def test_exact_two_jobs_and_parent_bindings(self):
        self.assertTrue(contract.check()["passed"])

    def test_actual_selected_half_open_boundaries(self):
        for arm, (start, end) in contract.STAGES.items():
            rows = []
            for step in range(20):
                state = state_for(arm, step)
                rows.append(sum(state.selected(block) for block in range(50)))
                self.assertFalse(state.selected(-1))
                self.assertFalse(state.selected(50))
            self.assertEqual(rows, [50 if start <= i < end else 0 for i in range(20)])
            self.assertEqual(sum(rows), 450)
            self.assertFalse(state_for(arm, -1).selected(0))
            self.assertFalse(state_for(arm, 20).selected(0))

    def test_real_override_off_equals_native_operator(self):
        generator = torch.Generator().manual_seed(143)
        q, k, v = [torch.randn(1, 2, 8, 4, generator=generator) for _ in range(3)]
        original = [t.clone() for t in (q, k, v)]
        plan = {"seq_len": 8, "query_interval_half_open": [0, 4],
                "reference_video_segment": [4, 8], "frame_rows": 2,
                "latent_interval_half_open": [0, 2]}
        native = oracle(q, k, v)[0].transpose(1, 2).reshape(1, 8, 8)
        route = core.route_attention

        def attention_pytorch():
            raise AssertionError("entry point is used for validation only")

        def injected(*args, **kwargs):
            return route(*args, **kwargs, attention=oracle)

        with patch.object(core, "route_attention", side_effect=injected):
            for arm, (start, end) in contract.STAGES.items():
                for step in range(20):
                    if start <= step < end:
                        continue
                    state = state_for(arm, step)
                    override = core.TemporalAttentionOverride(state, plan, 0)
                    actual = override(attention_pytorch, q, k, v, 2, skip_reshape=True)
                    self.assertTrue(torch.equal(actual, native))
                    self.assertEqual(state.audit["routed_calls"], 0)
                    self.assertEqual(state.audit["native_override_calls"], 1)
                    self.assertEqual(override.calls, 1)
            for arm, (start, _) in contract.STAGES.items():
                state = state_for(arm, start, alpha=0.0)
                actual = core.TemporalAttentionOverride(state, plan, 0)(
                    attention_pytorch, q, k, v, 2, skip_reshape=True)
                self.assertTrue(torch.equal(actual, native))
                self.assertEqual(state.audit["routed_calls"], 0)
        self.assertTrue(all(torch.equal(a, b) for a, b in zip((q, k, v), original)))

    def test_non_schedule_graph_changes_rejected(self):
        original_read = contract.read
        for node, key, value in [("6", "noise_seed", 1), ("50", "alpha", 0.5),
                                 ("50", "step_end", 10), ("8", "sampler_name", "heun"),
                                 ("5", "prompt", "different text")]:
            def mutated(path):
                data = original_read(path)
                if Path(path).parent == ROOT / "configs/graphs":
                    data = copy.deepcopy(data)
                    data[node]["inputs"][key] = value
                return data
            with patch.object(contract, "read", side_effect=mutated):
                with self.assertRaisesRegex(ValueError, "graph changes"):
                    contract.check()

    def test_old_pid_reuse_is_not_old_generation(self):
        saved = {"uid": 1016, "start_ticks": "2649851739"}
        self.assertTrue(contract.same_generation(saved, dict(saved, cmdline="changed")))
        self.assertFalse(contract.same_generation(saved, None))
        self.assertFalse(contract.same_generation(saved, {"uid": 1025, "start_ticks": "2650348172"}))
        self.assertFalse(contract.same_generation(saved, {"uid": 1016, "start_ticks": "2650348172"}))


if __name__ == "__main__":
    unittest.main()
