"""CPU interface contracts for opt-in Comfy graph integration."""
import tempfile
from pathlib import Path
import types
import unittest
from unittest import mock

import torch
from . import NODE_CLASS_MAPPINGS
from .frozen import load_frozen
from .nodes import H3TemporalCoverage


class NodeTests(unittest.TestCase):
    def positive(self):
        return [[torch.zeros(1, 3, 2), {"minimax_refs": [{
            "kind": "video", "latent_t": 5, "latent_h": 2, "latent_w": 2,
            "latent": torch.zeros(1, 24, 5, 2, 2), "ref_audio_t": 0}]}]]

    def test_registration_defaults(self):
        self.assertIs(NODE_CLASS_MAPPINGS["H3TemporalCoverage"], H3TemporalCoverage)
        spec = H3TemporalCoverage.INPUT_TYPES()["required"]
        for key, expected in (("enabled", False), ("alpha", .25), ("end_frame", -1),
                              ("step_start", 0), ("step_end", 20), ("block_end", 50)):
            self.assertEqual(spec[key][1]["default"], expected)
        self.assertEqual(spec["run_id"][0], "STRING")
        self.assertEqual(spec["audit_dir"][0], "STRING")

    def test_disabled_has_no_dependencies_or_side_effects(self):
        model = object()
        with mock.patch("temporal_coverage.nodes.load_frozen", side_effect=AssertionError), \
             mock.patch("temporal_coverage.nodes.attach_h3_coverage", side_effect=AssertionError):
            self.assertIs(H3TemporalCoverage().apply(model, None)[0], model)

    def test_all_frames_all_steps_and_blocks_forwarded(self):
        model, result = object(), object()
        with mock.patch("temporal_coverage.nodes.attach_h3_coverage", return_value=result) as attach:
            got = H3TemporalCoverage().apply(model, self.positive(), enabled=True,
                                             run_id="coverage_cpu", audit_dir="/tmp/coverage_audit")
        self.assertIs(got[0], result)
        args = attach.call_args.kwargs
        self.assertEqual((args["start_frame"], args["end_frame"]), (0, 16))
        self.assertEqual((args["step_start"], args["step_end"]), (0, 20))
        self.assertEqual((args["block_start"], args["block_end"]), (0, 50))
        self.assertEqual(args["alpha"], .25)
        self.assertEqual(args["config"].radius, 2)
        self.assertEqual(args["run_id"], "coverage_cpu")

    def test_custom_window_and_solver_forwarded(self):
        with mock.patch("temporal_coverage.nodes.attach_h3_coverage") as attach:
            H3TemporalCoverage().apply(object(), self.positive(), enabled=True, start_frame=1,
                end_frame=8, step_start=6, step_end=15, block_start=4, block_end=10,
                radius=0, entropy=.7, temporal_penalty=.4, iterations=256,
                tolerance=.001, min_quality_span=.002, minimum_mean_gap=.1)
        a = attach.call_args.kwargs
        self.assertEqual((a["start_frame"], a["end_frame"]), (1, 8))
        self.assertEqual((a["step_start"], a["step_end"]), (6, 15))
        self.assertEqual(a["config"].radius, 0)
        self.assertEqual(a["config"].iterations, 256)
        self.assertEqual(a["config"].minimum_mean_gap, .1)

    def test_bad_intervals_fail_before_attach(self):
        for args in ({"step_start": 20}, {"step_end": 21}, {"block_end": 51},
                     {"block_start": 50}, {"end_frame": 17}, {"start_frame": -1},
                     {"start_frame": 7, "end_frame": 2}, {"radius": -1}):
            with self.subTest(args=args), mock.patch("temporal_coverage.nodes.attach_h3_coverage") as attach:
                with self.assertRaises(ValueError):
                    H3TemporalCoverage().apply(object(), self.positive(), enabled=True, **args)
                attach.assert_not_called()

    def test_real_factory_patches_clone_fifty_blocks(self):
        # Mock only host Comfy module and model patch storage; real frozen RouterState runs.
        h3 = types.ModuleType("comfy.ldm.minimax.model")
        h3.MiniMaxH3Model = type("MiniMaxH3Model", (), {})
        h3.FRAME_PER_TOKEN = (1, 4, 4, 4, 4)
        def attention_pytorch():
            pass
        h3.optimized_attention = attention_pytorch
        modules = {name: types.ModuleType(name) for name in ("comfy", "comfy.ldm", "comfy.ldm.minimax")}
        modules["comfy.ldm.minimax.model"] = h3
        modules["comfy"].ldm = modules["comfy.ldm"]
        modules["comfy.ldm"].minimax = modules["comfy.ldm.minimax"]
        modules["comfy.ldm.minimax"].model = h3
        diffusion = h3.MiniMaxH3Model()
        diffusion.blocks = [object() for _ in range(50)]
        model, clone = mock.Mock(), mock.Mock()
        model.get_model_object.return_value = diffusion
        model.model_options = {}
        model.clone.return_value = clone
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("sys.modules", modules):
            result = H3TemporalCoverage().apply(model, self.positive(), enabled=True,
                                                audit_dir=tmp, run_id="cpu_patch")
            self.assertIs(result[0], clone)
            self.assertEqual(clone.set_model_patch_replace.call_count, 50)
            self.assertTrue((Path(tmp) / "cpu_patch.json").is_file())
            state = clone.set_model_patch_replace.call_args_list[0].args[0].state
            self.assertEqual((state.step_start, state.step_end), (0, 20))
            self.assertEqual((state.start_frame, state.end_frame), (0, 16))
            self.assertEqual(state.alpha, .25)

    def test_frozen_hashes_checked(self):
        frozen = load_frozen()
        self.assertEqual(set(frozen.hashes), {"core.py", "layout.py", "schedule.py"})
        self.assertTrue(Path(frozen.root).is_dir())
