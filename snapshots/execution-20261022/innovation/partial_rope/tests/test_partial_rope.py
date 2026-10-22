"""CPU-only algebra, legacy equivalence and audited-source integration tests."""

import ast
import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import torch

from H3PartialRoPE import NODE_CLASS_MAPPINGS
from H3PartialRoPE.adapter import (
    SCHEDULES,
    PartialBlockPatch,
    PartialPhaseState,
    source_hash,
    validate_runtime,
)
from H3PartialRoPE.core import (
    PartialTemporalRotation,
    parse_frequency_mask,
    partial_phase_attention,
)
from H3PartialRoPE.layout import FRAME_RESCALE

ROOT = Path(__file__).resolve().parents[1]


def extract(path, names, namespace):
    """Execute only named audited functions/classes, never import Comfy/CUDA."""
    tree = ast.parse(path.read_text())
    selected = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                and node.name in names]
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)  # noqa: S102 -- pinned source functions only
    return namespace


def dense_attention(q, k, v):
    logits = q @ k.transpose(-1, -2) / math.sqrt(q.shape[-1])
    return logits.softmax(-1) @ v, logits.logsumexp(-1)


def source_fixture():
    path = ROOT / "sources/host9_model.py"
    tree = ast.parse(path.read_text())
    names = {"Attention": "forward", "MiniMaxH3Model": "rope_freqs"}
    selected = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ("rope_rotation_table", "_video_t_grid", "_video_t_spans"):
            selected.append(node)
        if isinstance(node, ast.ClassDef) and node.name in names:
            methods = [item for item in node.body if isinstance(item, ast.FunctionDef) and item.name == names[node.name]]
            node.bases, node.body = [], methods
            selected.append(node)
    comfy = SimpleNamespace(model_management=SimpleNamespace(cast_to=lambda tensor, **kw: tensor.to(**kw)))
    ns = {"torch": torch, "comfy": comfy, "FRAME_PER_TOKEN": (1, 4, 4, 4, 4), "FRAME_RESCALE": 5/3}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), ns)  # noqa: S102 -- pinned source functions only
    h3 = SimpleNamespace(**ns)
    h3.optimized_attention = type("Native", (), {"__name__": "attention_pytorch"})()
    diffusion = h3.MiniMaxH3Model()
    diffusion.patch_size, diffusion.latents_dim = (1, 2, 2), 24
    diffusion.rope = SimpleNamespace(inv_freq=torch.linspace(0.9, 0.01, 16, dtype=torch.float64))
    diffusion.blocks = []
    for _ in range(50):
        attn = h3.Attention()
        attn.heads, attn.head_dim = 56, 128
        diffusion.blocks.append(SimpleNamespace(attn=attn))
    return h3, diffusion


class RotationTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(111)
        self.inv = torch.linspace(0.91, 0.003, 16, dtype=torch.float64)
        self.q = torch.randn(1, 2, 5, 128, dtype=torch.float64)
        self.mask = [1 if i in (0, 2, 7, 15) else 0 for i in range(16)]

    def test_delta_zero_identity(self):
        self.assertIs(PartialTemporalRotation(self.inv, 0, self.mask)(self.q), self.q)

    def test_mask_zero_identity(self):
        self.assertIs(PartialTemporalRotation(self.inv, 12, [0]*16)(self.q), self.q)

    def test_all_band_equals_actual_legacy_rotation(self):
        ns = extract(ROOT / "sources/legacy_phase_core.py", {"TemporalRotation"},
                     {"torch": torch, "math": math, "hashlib": hashlib, "FRAME_RESCALE": FRAME_RESCALE})
        for dtype in (torch.float64, torch.float32, torch.float16, torch.bfloat16):
            for delta in (-12, 12):
                q = self.q.to(dtype)
                actual = PartialTemporalRotation(self.inv, delta, [1]*16)(q)
                expected = ns["TemporalRotation"](self.inv, delta)(q)
                self.assertTrue(torch.equal(actual, expected), (dtype, delta))

    def test_positive_negative_inverse_and_sign(self):
        plus = PartialTemporalRotation(self.inv, 3, self.mask)
        minus = PartialTemporalRotation(self.inv, -3, self.mask)
        torch.testing.assert_close(minus(plus(self.q)), self.q, atol=1e-14, rtol=1e-14)
        basis = torch.zeros_like(self.q)
        basis[..., 0] = 1
        theta = self.inv[0] * 3 * FRAME_RESCALE
        torch.testing.assert_close(plus(basis)[..., 48], torch.full_like(basis[..., 48], theta.sin()))
        torch.testing.assert_close(minus(basis)[..., 48], -plus(basis)[..., 48])

    def test_norm_preserved(self):
        out = PartialTemporalRotation(self.inv, -18, self.mask)(self.q)
        torch.testing.assert_close(out.square().sum(-1), self.q.square().sum(-1), atol=1e-12, rtol=1e-14)

    def test_spatial_tail_unselected_time_exact_and_no_mutation(self):
        before = self.q.clone()
        result = PartialTemporalRotation(self.inv, 20, self.mask)(self.q)
        selected = {i for i, x in enumerate(self.mask) if x} | {i+48 for i, x in enumerate(self.mask) if x}
        others = [i for i in range(128) if i not in selected]
        self.assertTrue(torch.equal(result[..., others], self.q[..., others]))
        self.assertTrue(torch.equal(before, self.q))

    def test_mask_validation(self):
        for value in ([1]*15, [1]*17, [0.5]*16, [2]*16, "null", "[1]"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_frequency_mask(value)

    def test_nonfinite_invalid_parameters(self):
        for delta in (float("nan"), float("inf"), True):
            with self.assertRaises(ValueError):
                PartialTemporalRotation(self.inv, delta, self.mask)
        with self.assertRaises(ValueError):
            PartialTemporalRotation(torch.full((16,), float("nan")), 1, self.mask)
        with self.assertRaises(ValueError):
            PartialTemporalRotation(torch.ones(15), 1, self.mask)

    def test_noncontiguous_query(self):
        q = self.q.transpose(1, 2)
        out = PartialTemporalRotation(self.inv, 4, self.mask)(q)
        self.assertEqual(out.shape, q.shape)
        torch.testing.assert_close(out.square().sum(-1), q.square().sum(-1))

    def test_actual_source_rope_and_kernel_coordinate_shift(self):
        h3, diffusion = source_fixture()
        diffusion.rope.inv_freq = self.inv
        kernel = extract(ROOT / "sources/host9_kitchen_eager_rope.py",
                         {"apply_rope_split_half1", "_rms_rope1", "rms_rope_split_half"}, {"torch": torch})
        raw = self.q.transpose(1, 2)  # [B,S,H,D], as the real kernel receives.
        positions = torch.tensor([[i, 0.3*i, 2.0-i] for i in range(5)], dtype=torch.float64)
        angles = diffusion.rope_freqs(positions, "cpu")
        self.assertEqual(tuple(angles.shape), (5, 96))
        self.assertTrue(torch.equal(angles[..., :48], angles[..., 48:]))
        table = h3.rope_rotation_table(angles, torch.float64)
        q0, _ = kernel["rms_rope_split_half"](raw, raw, table, torch.ones(128, dtype=torch.float64), rot_dim=96)
        delta = 1.5
        shifted_angles = angles.clone()
        for i, active in enumerate(self.mask):
            if active:
                shifted_angles[:, i] += self.inv[i] * delta * FRAME_RESCALE
                shifted_angles[:, i+48] += self.inv[i] * delta * FRAME_RESCALE
        qt, _ = kernel["rms_rope_split_half"](raw, raw, h3.rope_rotation_table(shifted_angles, torch.float64),
                                               torch.ones(128, dtype=torch.float64), rot_dim=96)
        post = PartialTemporalRotation(self.inv, delta, self.mask)(q0.transpose(1, 2))
        torch.testing.assert_close(post, qt.transpose(1, 2), atol=2e-14, rtol=2e-14)

    def test_metadata_does_not_assume_frequency_order(self):
        inv = self.inv.flip(0)
        rotation = PartialTemporalRotation(inv, 3, self.mask)
        meta = rotation.metadata()
        self.assertEqual(meta["inv_freq"], inv.tolist())
        self.assertEqual(meta["rotated_channel_pairs"], [[0, 48], [2, 50], [7, 55], [15, 63]])

    def test_real_checkpoint_buffer_and_all_band_legacy(self):
        saved = json.loads((ROOT/"sources/checkpoint_inv_freq.json").read_text())
        inv = torch.tensor(saved["inv_freq"], dtype=torch.float32)
        self.assertEqual(tuple(inv.shape), (16,))
        self.assertTrue(bool((inv[:-1] > inv[1:]).all()))
        ns = extract(ROOT/"sources/legacy_phase_core.py", {"TemporalRotation"},
            {"torch": torch,"math": math,"hashlib": hashlib,"FRAME_RESCALE": FRAME_RESCALE})
        for delta in (-107, -12, 12, 107):
            rotation = PartialTemporalRotation(inv, delta, [1]*16)
            self.assertTrue(torch.equal(rotation(self.q), ns["TemporalRotation"](inv, delta)(self.q)))


class AttentionTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(222)
        self.q, self.k, self.v = [torch.randn(1, 2, 12, 128, dtype=torch.float64) for _ in range(3)]
        self.inv = torch.linspace(0.95, 0.005, 16, dtype=torch.float64)
        self.plan = {"query_interval_half_open": [8, 11], "reference_video_segment": [2, 6],
                         "target_video_segment": [7, 12], "reference_image_segments": [[1, 2]]}
        self.rotation = PartialTemporalRotation(self.inv, -9, [0]*8+[1]*8)

    def run_attention(self, **kwargs):
        return partial_phase_attention(self.q, self.k, self.v, 2, self.plan,
            rotation=kwargs.pop("rotation", self.rotation), attention=dense_attention, **kwargs)

    def test_three_identity_switches_exact(self):
        base = dense_attention(self.q, self.k, self.v)[0].transpose(1, 2).reshape(1, 12, 256)
        for kw in ({"enabled": False}, {"alpha": 0},
                   {"rotation": PartialTemporalRotation(self.inv, 0, [1]*16)},
                   {"rotation": PartialTemporalRotation(self.inv, 12, [0]*16)}):
            with self.subTest(kw=kw):
                self.assertTrue(torch.equal(self.run_attention(**kw), base))

    def test_all_band_attention_equals_actual_legacy(self):
        ns = extract(ROOT / "sources/legacy_phase_core.py", {"TemporalRotation", "phase_attention"},
                     {"torch": torch, "math": math, "hashlib": hashlib, "FRAME_RESCALE": FRAME_RESCALE,
                          "flash_attention_lse": dense_attention})
        for delta in (-12, 12):
            expected = ns["phase_attention"](self.q, self.k, self.v, 2, self.plan,
                rotation=ns["TemporalRotation"](self.inv, delta), alpha=0.7)
            actual = self.run_attention(rotation=PartialTemporalRotation(self.inv, delta, [1]*16), alpha=0.7)
            torch.testing.assert_close(actual, expected, atol=2e-16, rtol=1e-14)

    def test_explicit_probability_mass_replacement_oracle(self):
        logits = self.q @ self.k.transpose(-1, -2) / math.sqrt(128)
        probability = logits.softmax(-1)
        expected_probability = probability.clone()
        qa, qb = self.plan["query_interval_half_open"]
        ra, rb = self.plan["reference_video_segment"]
        ref_mass = probability[:, :, qa:qb, ra:rb].sum(-1, keepdim=True)
        rotated_logits = self.rotation(self.q[:, :, qa:qb]) @ self.k[:, :, ra:rb].transpose(-1, -2) / math.sqrt(128)
        alpha = 0.6
        expected_probability[:, :, qa:qb, ra:rb] = ((1-alpha)*probability[:, :, qa:qb, ra:rb]
                                                   + alpha*ref_mass*rotated_logits.softmax(-1))
        expected = (expected_probability @ self.v).transpose(1, 2).reshape(1, 12, 256)
        torch.testing.assert_close(self.run_attention(alpha=alpha), expected, atol=7e-16, rtol=2e-13)
        torch.testing.assert_close(expected_probability.sum(-1), torch.ones((1,2,12), dtype=torch.float64))
        torch.testing.assert_close(expected_probability[:, :, qa:qb, ra:rb].sum(-1, keepdim=True), ref_mass)

    def test_original_joint_qkv_and_ref_kv_unmodified(self):
        originals = [x.clone() for x in (self.q, self.k, self.v)]
        calls = []
        def recording(q, k, v):
            calls.append((q.clone(), k.clone(), v.clone()))
            return dense_attention(q, k, v)
        partial_phase_attention(self.q, self.k, self.v, 2, self.plan,
            rotation=self.rotation, attention=recording)
        self.assertEqual(len(calls), 3)
        for actual, original in zip(calls[0], originals):
            self.assertTrue(torch.equal(actual, original))
        for actual, original in zip((self.q, self.k, self.v), originals):
            self.assertTrue(torch.equal(actual, original))
        for a, b in zip(calls[1][1:], calls[2][1:]):
            self.assertTrue(torch.equal(a, b))

    def test_only_selected_output_rows_change(self):
        native = self.run_attention(enabled=False)
        changed = self.run_attention()
        self.assertTrue(torch.equal(native[:, :8], changed[:, :8]))
        self.assertTrue(torch.equal(native[:, 11:], changed[:, 11:]))
        self.assertGreater(float((native[:, 8:11]-changed[:, 8:11]).abs().max()), 0)

    def test_layout_and_alpha_guards(self):
        for alpha in (-0.1, 1.1, float("nan"), True):
            with self.assertRaises(ValueError):
                self.run_attention(alpha=alpha)
        for change in ({"query_interval_half_open": [1,3]}, {"reference_video_segment": [1,6]}):
            with self.assertRaises(ValueError):
                partial_phase_attention(self.q, self.k, self.v, 2, {**self.plan, **change},
                    rotation=self.rotation, attention=dense_attention)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.h3, self.diffusion = source_fixture()
        self.model = SimpleNamespace(model_options={}, object_patches={})

    def test_audited_source_contract_and_runtime(self):
        observed = validate_runtime(self.h3, self.diffusion, self.model)
        self.assertEqual(observed, json.loads((ROOT/'H3PartialRoPE/source_contract.json').read_text()))
        self.assertEqual(source_hash(self.h3.Attention.forward), observed["Attention.forward"])

    def test_runtime_rejects_sage_or_existing_override(self):
        self.model.object_patches = {"diffusion_model.blocks.0.attn.forward": object()}
        with self.assertRaises(ValueError):
            validate_runtime(self.h3, self.diffusion, self.model)
        self.model.object_patches = {}
        self.model.model_options = {"transformer_options": {"optimized_attention_override": object()}}
        with self.assertRaises(ValueError):
            validate_runtime(self.h3, self.diffusion, self.model)

    def test_schedule_membership_matches_frozen(self):
        path = ROOT.parents[1]/"inference/package/custom_nodes/H3Study/schedule.py"
        node = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "SCHEDULES" for t in n.targets))
        ns = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)  # noqa: S102 -- frozen schedule assignment only
        self.assertEqual({k:SCHEDULES[k] for k in ns["SCHEDULES"]}, ns["SCHEDULES"])

    def test_comfy_node_registration_is_disabled_by_default(self):
        node = NODE_CLASS_MAPPINGS["H3PartialRoPE"]
        self.assertFalse(node.INPUT_TYPES()["required"]["enabled"][1]["default"])
        self.assertEqual(node.RETURN_TYPES, ("MODEL",))

    def test_cpu_block_adapter_full_20_step_lifecycle(self):
        metadata = {"text_len": 1, "refs": [{"kind": "image", "index": 0, "frame_rows": 1,
            "latent_t": 1,"latent_h": 2,"latent_w": 2,"ref_audio_t": 0},{"kind": "video","index": 1,
            "frame_rows": 1,"latent_t": 2,"latent_h": 2,"latent_w": 2,"ref_audio_t": 0}]}
        layout = SimpleNamespace(signature=(1,2,2,2,0),seq_len=6,
            segments=[(0,1,"text"),(1,2,"ref_img"),(2,4,"ref_img"),(4,4,"audio"),(4,6,"video")],
            position_ids=torch.tensor([[0,0,0],[1,0,0],[2,0,0],[2+5/3,0,0],
                [2+25/3,0,0],[2+30/3,0,0]], dtype=torch.float64))
        rotation = PartialTemporalRotation(self.diffusion.rope.inv_freq, -3, [0]*8+[1]*8)
        sigmas = torch.linspace(1,0,21)
        q,k,v = [torch.randn(1,56,6,128,dtype=torch.float64) for _ in range(3)]
        native = type("Native", (), {"__name__":"attention_pytorch"})()
        with tempfile.TemporaryDirectory(dir=ROOT/"reports") as temporary:
            state = PartialPhaseState(metadata, rotation, enabled=True, alpha=0.5, schedule="fixed",
                start_frame=0,end_frame=4,block_start=10,block_end=12,run_id="cpu_adapter",
                audit_dir=temporary,runtime_source_hashes={})
            block_patches = [PartialBlockPatch(state,i) for i in range(50)]
            def cpu_attention(*args, **kwargs):
                return partial_phase_attention(*args, **kwargs, attention=dense_attention)
            def original(args):
                override = args["transformer_options"]["optimized_attention_override"]
                return {"img":override(native,q,k,v,56,mask=None,skip_reshape=True)}
            with patch("H3PartialRoPE.adapter.partial_phase_attention", side_effect=cpu_attention):
                for _ in range(20):
                    for i, block in enumerate(block_patches):
                        options = {"block_index": i,"minimax_h3_layout": layout,"sample_sigmas": sigmas}
                        result = block({"layout": layout,"transformer_options": options},{"original_block": original})
                        self.assertEqual(result["img"].shape, (1,6,56*128))
                        self.assertNotIn("optimized_attention_override", options)
            self.assertEqual(state.audit["status"],"complete")
            self.assertEqual(state.audit["completed_blocks"],1000)
            self.assertEqual(state.audit["compensated_calls"],18)
            self.assertEqual(state.audit["completed_forwards"],20)
            self.assertEqual(json.loads(state.path.read_text())["status"],"complete")


if __name__ == "__main__":
    unittest.main()
