"""CPU FP64 probability and split-half rotation checks for staged PhaseRoPE."""

import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "extensions"))
from H3PhaseRoPE.core import TemporalRotation, phase_attention, PhaseState, PhaseBlockPatch, PhaseAttentionOverride
from H3PhaseRoPE.architecture import architecture_contract
from H3PhaseRoPE.layout import event_latent_range


def fake_model():
    class Model:
        pass
    model = Model()
    model.hidden_size = 5376
    model.blocks = [SimpleNamespace(attn=SimpleNamespace(heads=42, head_dim=128,
        qkv_proj=SimpleNamespace(in_features=5376, out_features=16128),
        out_proj=SimpleNamespace(in_features=5376, out_features=5376))) for _ in range(50)]
    return model

CONTRACT = architecture_contract(fake_model())


def independent_rotation(query, frequency, delta):
    # Independent explicit 2x2 rotations: no production TemporalRotation call.
    result = query.clone()
    angle = frequency.to(query) * (delta * 5 / 3)
    for pair in range(16):
        c, s = math.cos(float(angle[pair])), math.sin(float(angle[pair]))
        matrix = query.new_tensor([[c, -s], [s, c]])
        values = torch.stack((query[..., pair], query[..., 48 + pair]), -1)
        rotated = values @ matrix.T
        result[..., pair], result[..., 48 + pair] = rotated.unbind(-1)
    return result


def dense_attention(q, k, v):
    logits = q @ k.transpose(-1, -2) / math.sqrt(q.shape[-1])
    return logits.softmax(-1) @ v, logits.logsumexp(-1)


class PhaseRoPETests(unittest.TestCase):
    def setUp(self):
        generator = torch.Generator().manual_seed(11)
        self.q, self.k, self.v = [torch.randn(1, 2, 11, 128, generator=generator, dtype=torch.float64) for _ in range(3)]
        self.frequency = torch.linspace(0.002, 0.31, 16, dtype=torch.float64)
        self.plan = {"query_interval_half_open": [7, 9], "reference_video_segment": [1, 5]}

    def test_dense_mass_redistribution_rest_unchanged_and_normalized(self):
        for delta in (-4.0, 4.0):
            for alpha in (0.5, 1.0):
                with self.subTest(delta=delta, alpha=alpha):
                    rotation = TemporalRotation(self.frequency, delta)
                    logits = self.q @ self.k.transpose(-1, -2) / math.sqrt(128)
                    old = logits.softmax(-1)
                    new = old.clone()
                    conditional_logits = independent_rotation(self.q[:, :, 7:9], self.frequency, delta) @ self.k[:, :, 1:5].transpose(-1, -2) / math.sqrt(128)
                    mass = old[:, :, 7:9, 1:5].sum(-1, keepdim=True)
                    new[:, :, 7:9, 1:5] = ((1 - alpha) * old[:, :, 7:9, 1:5]
                                                       + alpha * mass * conditional_logits.softmax(-1))
                    torch.testing.assert_close(new.sum(-1), torch.ones_like(new.sum(-1)), atol=4e-16, rtol=4e-16)
                    torch.testing.assert_close(new[:, :, 7:9, 1:5].sum(-1, keepdim=True), mass, atol=2e-16, rtol=2e-16)
                    self.assertTrue(torch.equal(old[..., :1], new[..., :1]))
                    self.assertTrue(torch.equal(old[..., 5:], new[..., 5:]))
                    expected = (new @ self.v).transpose(1, 2).reshape(1, 11, 256)
                    actual = phase_attention(self.q, self.k, self.v, 2, self.plan,
                                             rotation=rotation, alpha=alpha, attention=dense_attention)
                    torch.testing.assert_close(actual, expected, atol=7e-16, rtol=2e-13)
                    native, _ = dense_attention(self.q, self.k, self.v)
                    actual_heads = actual.reshape(1, 11, 2, 128).transpose(1, 2)
                    self.assertTrue(torch.equal(actual_heads[:, :, :7], native[:, :, :7]))
                    self.assertTrue(torch.equal(actual_heads[:, :, 9:], native[:, :, 9:]))

    def test_native_fast_paths_exact_and_only_one_attention(self):
        expected = dense_attention(self.q, self.k, self.v)[0].transpose(1, 2).reshape(1, 11, 256)
        for delta, alpha, plan in ((0, 1, self.plan), (13, 0, self.plan),
                                   (13, 1, {**self.plan, "query_interval_half_open": [7, 7]})):
            calls = []
            def attention(*args):
                calls.append(1)
                return dense_attention(*args)
            actual = phase_attention(self.q, self.k, self.v, 2, plan,
                                     rotation=TemporalRotation(self.frequency, delta), alpha=alpha,
                                     attention=attention)
            self.assertTrue(torch.equal(expected, actual))
            self.assertEqual(len(calls), 1)

    def test_rotation_norm_composition_inverse_and_untouched_channels(self):
        rotated = TemporalRotation(self.frequency, 13)(self.q)
        self.assertTrue(torch.equal(rotated[..., 16:48], self.q[..., 16:48]))
        self.assertTrue(torch.equal(rotated[..., 64:128], self.q[..., 64:128]))
        torch.testing.assert_close(rotated.norm(dim=-1), self.q.norm(dim=-1), atol=4e-15, rtol=4e-16)
        inverse = TemporalRotation(self.frequency, -13)(rotated)
        torch.testing.assert_close(inverse, self.q, atol=9e-16, rtol=3e-14)
        composed = TemporalRotation(self.frequency, -3)(TemporalRotation(self.frequency, 8)(self.q))
        direct = TemporalRotation(self.frequency, 5)(self.q)
        torch.testing.assert_close(composed, direct, atol=2e-15, rtol=4e-14)
        self.assertIs(TemporalRotation(self.frequency, 0)(self.q), self.q)

    def test_physical_frame_units_and_signed_toy_response(self):
        # A single frequency has a unique local optimum: no semantic claim about real video.
        frequency = torch.zeros(16, dtype=torch.float64)
        frequency[0] = 0.05
        key_times = torch.arange(7, dtype=torch.float64)
        keys = torch.zeros(1, 1, 7, 128, dtype=torch.float64)
        theta = key_times * (5 / 3) * frequency[0]
        keys[0, 0, :, 0], keys[0, 0, :, 48] = theta.cos(), theta.sin()
        query = keys[:, :, 3:4].clone()
        for delta, expected_peak in ((2, 5), (-2, 1), (0, 3)):
            rotation = TemporalRotation(frequency, delta)
            scores = rotation(query) @ keys.transpose(-1, -2)
            self.assertEqual(int(scores.argmax(-1)), expected_peak)
            self.assertAlmostEqual(rotation.delta_rope, delta * 5 / 3)

    def test_inputs_and_frequency_immutable_rotation_branch_only(self):
        inputs = [x.clone() for x in (self.q, self.k, self.v, self.frequency)]
        calls = []
        def attention(q, k, v):
            calls.append((q.clone(), k.clone(), v.clone()))
            return dense_attention(q, k, v)
        phase_attention(self.q, self.k, self.v, 2, self.plan,
                        rotation=TemporalRotation(self.frequency, 13), attention=attention)
        self.assertEqual(len(calls), 3)
        for before, after in zip(inputs, (self.q, self.k, self.v, self.frequency)):
            self.assertTrue(torch.equal(before, after))
        self.assertTrue(torch.equal(calls[0][0], self.q))
        self.assertTrue(torch.equal(calls[1][0], self.q[:, :, 7:9]))
        self.assertTrue(torch.equal(calls[1][1], calls[2][1]))
        self.assertTrue(torch.equal(calls[1][2], calls[2][2]))
        self.assertFalse(torch.equal(calls[1][0], calls[2][0]))

    def test_large_reference_mass_matches_dense_without_other_subtraction(self):
        q = self.q.clone()
        k = self.k.clone()
        # Make reference probabilities extremely concentrated, stressing group mixture.
        k[:, :, 1:5] = q[:, :, 7:8] * 50
        rotation = TemporalRotation(self.frequency, -9)
        old = (q @ k.transpose(-1, -2) / math.sqrt(128)).softmax(-1)
        mass = old[:, :, 7:9, 1:5].sum(-1, keepdim=True)
        self.assertGreater(float(mass[:, :, :1].min()), 0.999)
        new = old.clone()
        new[:, :, 7:9, 1:5] = mass * (rotation(q[:, :, 7:9]) @ k[:, :, 1:5].transpose(-1, -2) / math.sqrt(128)).softmax(-1)
        expected = (new @ self.v).transpose(1, 2).reshape(1, 11, 256)
        actual = phase_attention(q, k, self.v, 2, self.plan, rotation=rotation, attention=dense_attention)
        torch.testing.assert_close(actual, expected, atol=1e-14, rtol=1e-12)

    def test_frequency_checkpoint_values_not_assumed_and_invalid_inputs(self):
        metadata = TemporalRotation(self.frequency, 3).metadata()
        self.assertEqual(metadata["inv_freq"], self.frequency.tolist())
        self.assertEqual(metadata["inv_freq_sha256"], hashlib.sha256(self.frequency.view(torch.uint8).numpy().tobytes()).hexdigest())
        for frequency in (torch.ones(15), torch.ones(16, 1), torch.ones(16, dtype=torch.int32), torch.full((16,), float("nan"))):
            with self.assertRaises(ValueError):
                TemporalRotation(frequency, 1)
        for delta in (float("inf"), float("nan"), True):
            with self.assertRaises(ValueError):
                TemporalRotation(self.frequency, delta)
        rotation = TemporalRotation(self.frequency, 1)
        for alpha in (-1, 1.1, float("nan"), True):
            with self.assertRaises(ValueError):
                phase_attention(self.q, self.k, self.v, 2, self.plan, rotation=rotation, alpha=alpha, attention=dense_attention)
        with self.assertRaises(ValueError):
            phase_attention(self.q, self.k, self.v, 2, {**self.plan, "query_interval_half_open": [2, 4]},
                            rotation=rotation, attention=dense_attention)
        with self.assertRaises(ValueError):
            rotation(self.q[..., :96])

    def test_bf16_untouched_channels_are_bitwise_and_work_is_finite(self):
        q = self.q.bfloat16()
        rotated = TemporalRotation(self.frequency.float(), 13)(q)
        self.assertEqual(rotated.dtype, torch.bfloat16)
        self.assertTrue(torch.equal(rotated[..., 16:48], q[..., 16:48]))
        self.assertTrue(torch.equal(rotated[..., 64:128], q[..., 64:128]))
        self.assertTrue(bool(torch.isfinite(rotated).all()))

    def test_frozen_layout_copy_exact_and_physical_window_mapping(self):
        self.assertEqual(hashlib.sha256((ROOT / "extensions/H3PhaseRoPE/layout.py").read_bytes()).hexdigest(),
                         "bf2aac3b639bcc1b48e0733640d693d8b229cb7c9e270d54d608609322cbbafe")
        self.assertEqual(event_latent_range(50, 65, 42), (14, 20))

    def test_state_half_open_bounds_and_reject_duplicate_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = PhaseState({}, self.frequency, 13, 0.5, 50, 65, 10, 40, 5, 15, "test", temporary, model_contract=CONTRACT)
            state.forward_index = 5
            self.assertFalse(state.selected(9))
            self.assertTrue(state.selected(10))
            self.assertFalse(state.selected(40))
            state.forward_index = 15
            self.assertFalse(state.selected(10))
            with self.assertRaises(FileExistsError):
                PhaseState({}, self.frequency, 13, 0.5, 50, 65, 10, 40, 5, 15, "test", temporary, model_contract=CONTRACT)
            for bounds in ((0, 51, 0, 20), (0, 50, 0, 21), (0, 50, 20, 20)):
                with self.assertRaises(ValueError):
                    PhaseState({}, self.frequency, 1, 1, 50, 65, *bounds, "bad", temporary, model_contract=CONTRACT)

    def test_block_forwarding_counts_failure_and_option_immutability(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = PhaseState({}, self.frequency, 0, 1, 50, 65, 0, 50, 0, 20, "blocks", temporary, model_contract=CONTRACT)
            layout = object()
            plan = {**self.plan, "seq_len": 11}
            state.plan_for = lambda current: plan
            q, k, v = [x[:, :1].expand(-1, 42, -1, -1).clone() for x in (self.q, self.k, self.v)]
            def attention_pytorch(q, k, v, heads, **kwargs):
                return dense_attention(q, k, v)[0].transpose(1, 2).reshape(1, q.shape[2], heads*128)
            return_value = {"img": object()}
            def original(args):
                args["transformer_options"]["optimized_attention_override"](
                    attention_pytorch, q, k, v, 42, skip_reshape=True)
                return return_value
            # Replace the production attention function only inside this toy test.
            from H3PhaseRoPE import core as phase_core
            real_phase = phase_core.phase_attention
            def cpu_phase(*args, **kwargs):
                return real_phase(*args, **kwargs, attention=dense_attention)
            with patch.object(phase_core, "phase_attention", side_effect=cpu_phase):
                for block in range(50):
                    options = {"block_index": block, "minimax_h3_layout": layout,
                               "sample_sigmas": torch.linspace(1, 0, 21)}
                    args = {"layout": layout, "transformer_options": options}
                    result = PhaseBlockPatch(state, block)(args, {"original_block": original})
                    self.assertIs(result, return_value)
                    self.assertNotIn("optimized_attention_override", options)
            self.assertEqual(state.audit["completed_calls"], 50)
            self.assertEqual(state.audit["completed_forward_calls"], 1)
            self.assertEqual(state.audit["phase_calls"], 0)
            with self.assertRaisesRegex(ValueError, "block order"):
                PhaseBlockPatch(state, 2)({}, {})
            self.assertEqual(json.loads(state.path.read_text())["status"], "failed")


if __name__ == "__main__":
    unittest.main()
