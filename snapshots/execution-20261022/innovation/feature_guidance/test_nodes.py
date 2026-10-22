"""CPU interface contracts for opt-in Comfy graph integration."""
import tempfile
from pathlib import Path
import types
import unittest
from unittest import mock

import torch
from . import NODE_CLASS_MAPPINGS
from .frozen import load_frozen
from .nodes import H3FeatureGuidance


class NodeTests(unittest.TestCase):
    def positive(self):
        return [[torch.zeros(1, 3, 2), {"minimax_refs": [{
            "kind": "video", "latent_t": 5, "latent_h": 2, "latent_w": 2,
            "latent": torch.zeros(1, 24, 5, 2, 2), "ref_audio_t": 0}]}]]

    def test_registration_defaults(self):
        self.assertIs(NODE_CLASS_MAPPINGS["H3FeatureGuidance"], H3FeatureGuidance)
        spec = H3FeatureGuidance.INPUT_TYPES()["required"]
        for key, expected in (("enabled", False), ("alpha_prior", .25), ("end_frame", -1),
                              ("step_start", 0), ("step_end", 20), ("block_end", 50)):
            self.assertEqual(spec[key][1]["default"], expected)
        self.assertEqual(spec["run_id"][0], "STRING")
        self.assertEqual(spec["audit_dir"][0], "STRING")

    def test_disabled_has_no_dependencies_or_side_effects(self):
        model = object()
        with mock.patch("feature_guidance.nodes.load_frozen", side_effect=AssertionError), \
             mock.patch("feature_guidance.nodes.attach", side_effect=AssertionError):
            self.assertIs(H3FeatureGuidance().apply(model, None)[0], model)

    def test_all_frames_all_steps_and_blocks_forwarded(self):
        model, result = object(), object()
        with mock.patch("feature_guidance.nodes.attach", return_value=result) as attach:
            got = H3FeatureGuidance().apply(model, self.positive(), enabled=True,
                                             run_id="coverage_cpu", audit_dir="/tmp/coverage_audit")
        self.assertIs(got[0], result)
        args = attach.call_args.kwargs
        self.assertEqual((args["start_frame"], args["end_frame"]), (0, 16))
        self.assertEqual((args["step_start"], args["step_end"]), (0, 20))
        self.assertEqual((args["block_start"], args["block_end"]), (0, 50))
        self.assertEqual(args["config"].alpha_prior, .25)
        self.assertEqual(args["config"].probes, 8)
        self.assertEqual(args["run_id"], "coverage_cpu")

    def test_custom_mode_forwarded(self):
        with mock.patch("feature_guidance.nodes.attach") as attach:
            H3FeatureGuidance().apply(object(), self.positive(), enabled=True,
                mode="heads_budget", alpha_prior=.25, alpha_max=.5, probes=4)
        config=attach.call_args.kwargs['config']
        self.assertEqual(config.mode,'heads_budget')
        self.assertEqual(config.probes,4)

    def test_bad_intervals_fail_before_attach(self):
        for args in ({"step_start": 20}, {"step_end": 21}, {"block_end": 51},
                     {"block_start": 50}, {"end_frame": 17}, {"start_frame": -1},
                     {"start_frame": 7, "end_frame": 2}, {"probes": 0}, {"alpha_max": .1}, {"basis": "secants"}):
            with self.subTest(args=args), mock.patch("feature_guidance.nodes.attach") as attach:
                with self.assertRaises(ValueError):
                    H3FeatureGuidance().apply(object(), self.positive(), enabled=True, **args)
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
            result = H3FeatureGuidance().apply(model, self.positive(), enabled=True,
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

    def test_real_fifty_block_finish_and_failure_audit(self):
        import json
        from .attention import FeatureConfig, make_classes
        from .test_feature_attention import FeatureAttentionTests, dense
        core=load_frozen().core
        state_type,block_type=make_classes(core)
        q,k,v,heads,plan=FeatureAttentionTests().data()
        layout=object()
        def attention_pytorch():
            pass
        def original(args):
            override=args['transformer_options']['optimized_attention_override']
            return override(attention_pytorch,q,k,v,heads,skip_reshape=True)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(core,'flash_attention_lse',dense):
            state=state_type({},'mass_preserve',.25,0,0,0,16,0,50,0,20,'finish_cpu',tmp,
                             feature_config=FeatureConfig())
            with mock.patch.object(state,'plan_for',return_value=plan):
                for block in range(50):
                    args={'layout':layout,'transformer_options':{'block_index':block,
                          'minimax_h3_layout':layout,'sample_sigmas':torch.tensor([1.,0.])}}
                    block_type(state,block)(args,{'original_block':original})
                saved=json.loads((Path(tmp)/'finish_cpu.json').read_text())
                self.assertEqual(saved['completed_forward_calls'],1)
                self.assertEqual(saved['routed_calls'],50)
                self.assertEqual(len(saved['feature_forward_summaries'][0]['layers']),50)
                self.assertEqual(state.feature_pending,[])
                self.assertTrue(all(r['finite_output'] for r in saved['feature_forward_summaries'][0]['layers']))
                self.assertEqual(saved['intermediate_vae_decode_calls'],0)
                with self.assertRaisesRegex(ValueError,'unexpected block order'):
                    block_type(state,2)(args,{'original_block':original})
                failed=json.loads((Path(tmp)/'finish_cpu.json').read_text())
                self.assertEqual(failed['status'],'failed')
                self.assertEqual(failed['completed_forward_calls'],1)
