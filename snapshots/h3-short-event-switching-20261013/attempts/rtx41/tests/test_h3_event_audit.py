"""CPU-only checks against the installed native Comfy implementation.

Run with H3_COMFY_ROOT=/path/to/ComfyUI CUDA_VISIBLE_DEVICES='' python this_file.
The test uses fake encoders, never loads weights, and enables Comfy --cpu.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.argv.append("--cpu")
sys.path.insert(0, os.environ["H3_COMFY_ROOT"])
import torch
if os.environ.get("H3_AST_ONLY") == "1":
    from native_cpu_harness import install_native_subset
    install_native_subset(Path(os.environ["H3_COMFY_ROOT"]))
else:
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
from comfy_extras.nodes_minimax_h3 import MiniMaxH3ReferenceToVideo, video_latent_t
from comfy.nested_tensor import NestedTensor
import comfy.sample

extension = Path(__file__).resolve().parents[1] / "extensions/H3EventAudit/__init__.py"
spec = importlib.util.spec_from_file_location("h3_event_audit", extension)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class FakeVAE:
    def __init__(self):
        self.encoded_inputs = []

    def encode(self, frames):
        self.encoded_inputs.append(frames)
        t = 1 if len(frames) == 1 else video_latent_t(len(frames))
        return torch.ones((1, 24, t, frames.shape[1] // 16, frames.shape[2] // 16)) * frames.mean()


class FakeClip:
    def __init__(self):
        self.items = None

    def tokenize(self, prompt, **kwargs):
        self.items = kwargs["minimax_ref_items"]
        return {"qwen3vl_32b": [[(len(prompt), 1.0)]]}

    def encode_from_tokens_scheduled(self, tokens):
        n = tokens["qwen3vl_32b"][0][0][0]
        return [[torch.ones((1, n, 8)), {"minimax_token_tags": torch.ones(n, dtype=torch.long)}]]


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "short_event_switching_20261013" / "audit"
        self.root.mkdir(parents=True)
        self.frames = torch.arange(107, dtype=torch.float32)[:, None, None, None].expand(107, 64, 64, 3) / 107

    def tearDown(self):
        self.temp.cleanup()

    def call(self, clip, fps=2, phase=0, prompt="normal", run="run"):
        return audit.H3EventAuditReference().encode(
            clip, FakeVAE(), self.frames, prompt, 64, 64, 107,
            str(self.root), run, fps, phase)

    def test_native_default_equivalence(self):
        native_clip, wrapped_clip = FakeClip(), FakeClip()
        native = MiniMaxH3ReferenceToVideo.execute(
            clip=native_clip, vae=FakeVAE(), prompt="normal", width=64, height=64,
            length=107, ref_videos={"ref_video_0": self.frames})
        actual = self.call(wrapped_clip)
        self.assertTrue(torch.equal(native[0][0][0], actual[0][0][0]))
        self.assertTrue(torch.equal(native[0][0][1]["minimax_refs"][0]["latent"], actual[3]["samples"]))
        for a, b in zip(native[1]["samples"].unbind(), actual[1]["samples"].unbind()):
            self.assertTrue(torch.equal(a, b))
        self.assertTrue(torch.equal(native_clip.items[0]["data"], wrapped_clip.items[0]["data"]))
        self.assertEqual(native_clip.items[0]["timestamps"], wrapped_clip.items[0]["timestamps"])
        manifest = json.loads((self.root / "run_conditioning.json").read_text())
        self.assertEqual(manifest["qwen_presentation"][0]["sampling"]["sample_indices"], list(range(0, 107, 12)))
        self.assertEqual(manifest["qwen_presentation"][0]["sampling"]["temporal_blocks"][-1]["source_frames"], [96, 96])
        self.assertEqual(manifest["packed_layout"]["segments"][-1][2], "video")

    def test_optional_image_and_141frames_delegate_native_exactly(self):
        frames = torch.arange(141, dtype=torch.float32)[:, None, None, None].expand(141, 64, 64, 3) / 141
        picture = torch.full((1, 64, 64, 3), .73)
        native_clip, wrapped_clip = FakeClip(), FakeClip()
        native_vae = FakeVAE()
        native = MiniMaxH3ReferenceToVideo.execute(
            clip=native_clip, vae=native_vae, prompt="character", width=64, height=64,
            length=141, ref_image_size="match", ref_images={"ref_image_0": picture},
            ref_videos={"ref_video_0": frames})
        actual = audit.H3EventAuditReference().encode(
            wrapped_clip, FakeVAE(), frames, "character", 64, 64, 141,
            str(self.root), "image141", ref_image=picture)
        self.assertEqual([item["type"] for item in wrapped_clip.items], ["image", "video"])
        for left, right in zip(native_clip.items, wrapped_clip.items):
            self.assertTrue(torch.equal(left["data"], right["data"]))
        for left, right in zip(native[1]["samples"].unbind(), actual[1]["samples"].unbind()):
            self.assertTrue(torch.equal(left, right))
        self.assertEqual(actual[1]["samples"].unbind()[0].shape[2], 42)
        self.assertTrue(torch.equal(actual[2], native_vae.encoded_inputs[-1]))
        manifest = json.loads((self.root / "image141_conditioning.json").read_text())
        self.assertEqual(len(manifest["native_vae_calls"]), 2)
        self.assertEqual(manifest["native_vae_calls"][0]["prepared_frames"]["shape"][0], 1)
        self.assertEqual(manifest["qwen_presentation"][0]["data"]["tensor"]["sha256"],
                         manifest["native_vae_calls"][0]["prepared_frames"]["sha256"])
        self.assertEqual(manifest["qwen_presentation"][1]["sampling"]["sample_indices"], list(range(0, 141, 12)))

    def test_semantic_change_preserves_dense_path_and_real_times(self):
        base = self.call(FakeClip(), run="base")
        phase_clip = FakeClip()
        phase = self.call(phase_clip, phase=4, run="phase")
        self.assertTrue(torch.equal(base[2], phase[2]))
        self.assertTrue(torch.equal(base[3]["samples"], phase[3]["samples"]))
        self.assertEqual(phase_clip.items[0]["timestamps"][0], 4 / 24)
        self.assertTrue(torch.equal(phase_clip.items[0]["data"][0], base[2][4]))
        dense_clip = FakeClip()
        self.call(dense_clip, fps=4, run="4fps")
        self.assertEqual(len(dense_clip.items[0]["data"]), len(range(0, 107, 6)))

    def test_nested_noise_matches_native_and_reuses_exact_values(self):
        latent = {"samples": NestedTensor([torch.zeros(1, 24, 2, 4, 4), torch.zeros(1, 32, 2, 8)])}
        expected = comfy.sample.prepare_noise(latent["samples"], 4321)
        noise1 = audit.CachedNoise(4321, self.root, "A", "pair").generate_noise(latent)
        for a, b in zip(expected.unbind(), noise1.unbind()):
            self.assertTrue(torch.equal(a, b))
        noise1.tensors[0].fill_(99)
        noise2 = audit.CachedNoise(4321, self.root, "B", "pair").generate_noise(latent)
        for a, b in zip(expected.unbind(), noise2.unbind()):
            self.assertTrue(torch.equal(a, b))
        a = json.loads((self.root / "A_noise.json").read_text())
        b = json.loads((self.root / "B_noise.json").read_text())
        self.assertEqual(a["actual_noise_streams"], b["actual_noise_streams"])
        with self.assertRaisesRegex(ValueError, "mismatch"):
            audit.CachedNoise(4322, self.root, "C", "pair").generate_noise(latent)

    def test_cache_tampering_rejected(self):
        latent = {"samples": torch.zeros(1, 4, 4, 4)}
        audit.CachedNoise(4, self.root, "A", "pair").generate_noise(latent)
        saved = torch.load(self.root / "pair_noise.pt", weights_only=True)
        saved["tensors"][0][0, 0, 0, 0] += 1
        torch.save(saved, self.root / "pair_noise.pt")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            audit.CachedNoise(4, self.root, "B", "pair").generate_noise(latent)

    def test_plan_and_path_validation(self):
        for args in ((107, 5, 0), (107, 2, 12), (107, 2, -1)):
            with self.assertRaises(ValueError):
                audit.sampling_plan(*args)
        with self.assertRaises(ValueError):
            audit.safe_id("../bad")
        with self.assertRaises(ValueError):
            audit.audit_root("/tmp/unrelated")

    def test_native_reference_augmentation_deterministic(self):
        from comfy.ldm.minimax.model import MiniMaxH3Model
        holder = type("Holder", (), {"patch_size": (1, 2, 2)})()
        z = torch.arange(768, dtype=torch.float32).reshape(1, 24, 2, 4, 4) / 768
        payload = {"seed": 9321, "cond_video_latents": [z]}
        method = MiniMaxH3Model._cond_video_rows
        first = method(holder, payload, "cpu")
        torch.manual_seed(777)
        torch.randn(100)
        second = method(holder, payload, "cpu")
        self.assertTrue(torch.equal(first, second))
        other = method(holder, dict(payload, seed=9322), "cpu")
        self.assertFalse(torch.equal(first, other))


if __name__ == "__main__":
    sys.argv.remove("--cpu")
    unittest.main(verbosity=2)
