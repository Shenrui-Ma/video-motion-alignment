"""CPU-only tests; no Comfy installation, weights or GPU are needed."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "extensions"))
from H3X0Readout.core import CaptureConfig, PassiveRecorder, tensor_signature

spec = importlib.util.spec_from_file_location("decode_x0", ROOT / "scripts" / "decode_x0.py")
decoder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decoder)
from H3X0Readout import core


class Nested:
    is_nested = True

    def __init__(self, tensors):
        self.tensors = list(tensors)

    def unbind(self):
        return self.tensors


def unpack(value, shapes):
    result, start = [], 0
    for shape in shapes:
        count = torch.Size(shape).numel()
        result.append(value[..., start:start + count].reshape(shape))
        start += count
    return result


def sample_euler():
    pass


class Harness:
    def __init__(self, root, *, nested=False, scale=4.0, callback=True):
        self.config = CaptureConfig("test_run", str(root), 32, 32, 5)
        self.video = torch.arange(torch.Size(self.config.shapes[0]).numel(), dtype=torch.float32).reshape(self.config.shapes[0]) / 50
        self.audio = torch.arange(torch.Size(self.config.shapes[1]).numel(), dtype=torch.float32).reshape(self.config.shapes[1]) / 7
        packed = torch.cat([t.reshape(1, 1, -1) for t in (self.video, self.audio)], dim=-1)
        self.x0 = Nested((self.video, self.audio)) if nested else packed
        self.noise = torch.ones_like(packed)
        self.latent = torch.zeros_like(packed)
        self.mask = object()
        self.sigmas = torch.linspace(1, 0, 21)
        self.extra_args = {"seed": 123, "model_options": {"sentinel": [1, 2, 3]}}
        self.model = SimpleNamespace(latent_shapes=self.config.shapes,
                                     latent_format=SimpleNamespace(scale_factor=1.0),
                                     audio_scale=lambda: scale,
                                     process_latent_out=lambda value: Nested((value.unbind()[0], value.unbind()[1] * (1 / scale))))
        self.model_wrap = SimpleNamespace(inner_model=self.model)
        self.calls = []
        self.callback = self.observe if callback else None
        self.result = packed.clone() + 0.000001
        self.steps = list(range(20))
        self.total_steps = 20
        self.exception = None
        self.executor_calls = 0
        self.sampler = SimpleNamespace(sampler_function=sample_euler, extra_options={})

    def observe(self, step, x0, x, total):
        self.calls.append((step, x0, x, total))
        return "callback-sentinel"

    def execute(self, model_wrap, sigmas, args, callback, noise, latent, mask, disable):
        self.executor_calls += 1
        assert model_wrap is self.model_wrap and sigmas is self.sigmas
        assert args is self.extra_args and noise is self.noise and latent is self.latent
        assert mask is self.mask and disable is True
        for step in self.steps:
            returned = callback(step, self.x0, self.noise, self.total_steps)
            if self.callback:
                assert returned == "callback-sentinel"
        if self.exception:
            raise self.exception
        return self.result

    def run(self):
        recorder = PassiveRecorder(self.config, unpack=unpack, nested_factory=Nested)
        harness = self

        class Executor:
            class_obj = harness.sampler

            def __call__(self, *args):
                return harness.execute(*args)

            def execute(self, *args):
                raise AssertionError("must call executor(), not executor.execute()")

        return recorder(Executor(), self.model_wrap, self.sigmas, self.extra_args,
                        self.callback, self.noise, self.latent, self.mask, True)

    @property
    def manifest_path(self):
        return Path(self.config.output_dir) / self.config.run_id / "manifest.json"


class RecorderTests(unittest.TestCase):
    def test_packed_and_nested_preserve_inputs_callbacks_rng_and_outputs(self):
        for nested in (False, True):
            with self.subTest(nested=nested), tempfile.TemporaryDirectory() as temporary:
                harness = Harness(Path(temporary), nested=nested)
                original = [t.clone() for t in (harness.video, harness.audio, harness.noise, harness.latent, harness.sigmas)]
                args = copy.deepcopy(harness.extra_args)
                rng = torch.get_rng_state().clone()
                self.assertIs(harness.run(), harness.result)
                self.assertTrue(torch.equal(rng, torch.get_rng_state()))
                self.assertEqual(harness.executor_calls, 1)
                self.assertEqual(harness.extra_args, args)
                for before, after in zip(original, (harness.video, harness.audio, harness.noise, harness.latent, harness.sigmas)):
                    self.assertTrue(torch.equal(before, after))
                self.assertEqual([call[0] for call in harness.calls], list(range(20)))
                for _, x0, x, total in harness.calls:
                    self.assertIs(x0, harness.x0)
                    self.assertIs(x, harness.noise)
                    self.assertEqual(total, 20)
                manifest = json.loads(harness.manifest_path.read_text())
                self.assertEqual(manifest["status"], "complete")
                self.assertEqual(manifest["callback_count"], 20)
                self.assertGreater(manifest["endpoint_comparison"]["differences"]["video"]["max_abs"], 0)
                self.assertEqual([c["step_zero_based"] for c in manifest["captures"]], [5, 6, 7, 8, 9, 10, 15, 19])
                for step in core.CAPTURE_STEPS:
                    path = harness.manifest_path.parent / f"x0_step{step:03d}.pt"
                    payload = decoder.load_snapshot(path, core)
                    self.assertTrue(torch.equal(payload["video"], harness.video))
                    self.assertTrue(torch.equal(payload["audio"], harness.audio / 4))
                    self.assertEqual(payload["metadata"]["endpoint_sanity"], step == 19)
                    self.assertEqual(payload["metadata"]["video"], tensor_signature(harness.video))
                self.assertFalse(any(p.name.startswith(".") for p in harness.manifest_path.parent.iterdir()))
                final = decoder.load_snapshot(harness.manifest_path.parent / "sampler_final.pt", core)
                self.assertEqual(final["metadata"]["snapshot_kind"], "sampler_final")

    def test_no_original_callback_and_audio_scale_one(self):
        with tempfile.TemporaryDirectory() as temporary:
            harness = Harness(Path(temporary), callback=False, scale=1)
            harness.run()
            value = torch.load(harness.manifest_path.parent / "x0_step019.pt", weights_only=True)
            self.assertTrue(torch.equal(value["audio"], harness.audio))
            self.assertEqual(harness.calls, [])

    def test_strict_config_and_full_shapes(self):
        for kwargs in ({"run_id": "../escape"}, {"run_id": "a/b"}, {"output_dir": "relative"},
                       {"width": 31}, {"length": 140}, {"height": 736.0}):
            values = dict(run_id="safe", output_dir="/tmp", width=1312, height=736, length=141)
            values.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                CaptureConfig(**values)
        self.assertEqual(CaptureConfig("full", "/tmp").shapes,
                         ((1, 24, 42, 46, 82), (1, 32, 2, 235)))

    def test_wrong_model_geometry_rejected_before_sampler(self):
        with tempfile.TemporaryDirectory() as temporary:
            harness = Harness(Path(temporary))
            harness.model.latent_shapes = ((1, 24, 2, 4, 4), harness.config.shapes[1])
            with self.assertRaisesRegex(ValueError, "latent_shapes"):
                harness.run()
            self.assertEqual(harness.executor_calls, 0)

    def test_invalid_streams_leave_failure_manifest(self):
        for mutation in ("extra", "dtype", "nan", "swap", "third"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                harness = Harness(Path(temporary))
                if mutation == "extra":
                    harness.x0 = torch.cat((harness.x0, torch.zeros(1, 1, 1)), -1)
                elif mutation == "dtype":
                    harness.x0 = harness.x0.double()
                elif mutation == "nan":
                    harness.x0[0, 0, 0] = float("nan")
                elif mutation == "swap":
                    harness.x0 = Nested((harness.audio, harness.video))
                else:
                    harness.x0 = Nested((harness.video, harness.audio, harness.audio))
                with self.assertRaises(ValueError):
                    harness.run()
                self.assertEqual(json.loads(harness.manifest_path.read_text())["status"], "failed")

    def test_invalid_callback_sequences(self):
        for steps, total in ((list(range(19)), 20), ([0, 1, 1], 20), ([1], 20), (list(range(20)), 19)):
            with self.subTest(steps=steps, total=total), tempfile.TemporaryDirectory() as temporary:
                harness = Harness(Path(temporary))
                harness.steps, harness.total_steps = steps, total
                with self.assertRaises(ValueError):
                    harness.run()
                self.assertEqual(json.loads(harness.manifest_path.read_text())["status"], "failed")

    def test_sampler_errors_propagate_and_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            harness = Harness(Path(temporary))
            harness.exception = RuntimeError("intentional sampler failure")
            with self.assertRaisesRegex(RuntimeError, "intentional sampler failure"):
                harness.run()
            original = harness.manifest_path.read_bytes()
            with self.assertRaises(FileExistsError):
                harness.run()
            self.assertEqual(harness.manifest_path.read_bytes(), original)

    def test_preflight_rejects_sampler_churn_bad_grid_and_normalization(self):
        for mutation in ("sampler", "churn", "grid", "video_scale", "audio_scale"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                harness = Harness(Path(temporary))
                if mutation == "sampler":
                    harness.sampler.sampler_function = lambda: None
                elif mutation == "churn":
                    harness.sampler.extra_options["s_churn"] = 1
                elif mutation == "grid":
                    harness.sigmas[8] = harness.sigmas[7]
                elif mutation == "video_scale":
                    harness.model.latent_format.scale_factor = 2
                else:
                    harness.model.audio_scale = lambda: float("nan")
                with self.assertRaises(ValueError):
                    harness.run()
                self.assertEqual(harness.executor_calls, 0)

    def test_normalization_mismatch_and_original_callback_error_propagate(self):
        for mutation in ("normalization", "callback"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                harness = Harness(Path(temporary))
                if mutation == "normalization":
                    harness.model.process_latent_out = lambda value: value
                else:
                    def broken(*args):
                        raise ValueError("original callback failed")
                    harness.callback = broken
                with self.assertRaises(ValueError):
                    harness.run()
                self.assertEqual(json.loads(harness.manifest_path.read_text())["status"], "failed")

    def test_decoder_rejects_corruption_and_incomplete_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            harness = Harness(Path(temporary))
            harness.run()
            path = harness.manifest_path.parent / "x0_step005.pt"
            payload = torch.load(path, weights_only=True)
            payload["video"][0, 0, 0, 0, 0] += 1
            torch.save(payload, path)
            with self.assertRaisesRegex(ValueError, "hash-mismatched"):
                decoder.load_snapshot(path, core)
            manifest = json.loads(harness.manifest_path.read_text())
            manifest["status"] = "failed"
            harness.manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "incomplete"):
                decoder.load_snapshot(harness.manifest_path.parent / "x0_step019.pt", core)

    def test_decoder_gpu_admission_is_fail_closed(self):
        uuid = "GPU-example-full-uuid"
        for rows, processes, accepted in ((uuid + ", 4, 0\n", "", True),
                                          (uuid + ", 400, 0\n", "", False),
                                          (uuid + ", 4, 50\n", "", False),
                                          (uuid + ", 4, 0\n", "1234\n", False),
                                          ("GPU-other, 4, 0\n", "", False)):
            with self.subTest(rows=rows, processes=processes), patch.object(
                    decoder.subprocess, "check_output", side_effect=[rows, processes]):
                if accepted:
                    self.assertEqual(decoder.assert_idle_gpu(uuid)["uuid"], uuid)
                else:
                    with self.assertRaises(RuntimeError):
                        decoder.assert_idle_gpu(uuid)
        with self.assertRaises(ValueError):
            decoder.assert_idle_gpu("2")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "existing ffmpeg/ffprobe required")
    def test_decoder_encoder_keeps_frame_count_geometry_and_fps(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "tiny.mp4"
            images = torch.linspace(0, 1, 5 * 32 * 64 * 3).reshape(5, 32, 64, 3)
            images[0, 0, 0] = torch.tensor([-0.25, 0.5, 1.5])
            before = images.clone()
            stats = decoder.write_video(images, output, shutil.which("ffmpeg"))
            self.assertTrue(torch.equal(images, before))
            self.assertEqual(len(stats["preencode_rgb24_frame_sha256"]), 5)
            expected_rgb = (images * 255).clamp(0, 255).byte()
            self.assertEqual(expected_rgb[0, 0, 0].tolist(), [0, 127, 255])
            self.assertEqual(stats["preencode_rgb24_sha256"], hashlib.sha256(expected_rgb.numpy().tobytes()).hexdigest())
            self.assertEqual(stats["preencode_rgb24_frame_sha256"][0], hashlib.sha256(expected_rgb[0].numpy().tobytes()).hexdigest())
            self.assertEqual(stats["decoded_tensor_sha256"], hashlib.sha256(images.view(torch.uint8).numpy().tobytes()).hexdigest())
            probe = json.loads(subprocess.check_output([
                shutil.which("ffprobe"), "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,nb_frames,r_frame_rate", "-of", "json", str(output)]))
            self.assertEqual(probe["streams"][0], {"width": 64, "height": 32, "r_frame_rate": "24/1", "nb_frames": "5"})


if __name__ == "__main__":
    unittest.main()
