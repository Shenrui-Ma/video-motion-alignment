"""CPU interface contracts for opt-in Comfy graph integration."""
import tempfile
from pathlib import Path
import types
import unittest
from unittest import mock

import torch
from . import NODE_CLASS_MAPPINGS
from .frozen import load_frozen
from .nodes import H3TemporalGainFieldUniformEnergy


class NodeTests(unittest.TestCase):
    def positive(self):
        return [[torch.zeros(1, 3, 2), {"minimax_refs": [{
            "kind": "video", "latent_t": 5, "latent_h": 2, "latent_w": 2,
            "latent": torch.zeros(1, 24, 5, 2, 2), "ref_audio_t": 0}]}]]

    def test_registration_defaults(self):
        self.assertIs(NODE_CLASS_MAPPINGS["H3TemporalGainFieldUniformEnergy"], H3TemporalGainFieldUniformEnergy)
        spec = H3TemporalGainFieldUniformEnergy.INPUT_TYPES()["required"]
        for key, expected in (("enabled", False), ("alpha_prior", .25), ("end_frame", -1),
                              ("step_start", 0), ("step_end", 20), ("block_end", 50)):
            self.assertEqual(spec[key][1]["default"], expected)
        self.assertEqual(spec["run_id"][0], "STRING")
        self.assertEqual(spec["audit_dir"][0], "STRING")

    def test_disabled_has_no_dependencies_or_side_effects(self):
        model = object()
        with mock.patch("feature_gain_field_uniform_energy.nodes.load_frozen", side_effect=AssertionError), \
             mock.patch("feature_gain_field_uniform_energy.nodes.attach", side_effect=AssertionError):
            self.assertIs(H3TemporalGainFieldUniformEnergy().apply(model, None)[0], model)

    def test_all_frames_all_steps_and_blocks_forwarded(self):
        model, result = object(), object()
        with mock.patch("feature_gain_field_uniform_energy.nodes.attach", return_value=result) as attach:
            got = H3TemporalGainFieldUniformEnergy().apply(model, self.positive(), enabled=True,
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
        with mock.patch("feature_gain_field_uniform_energy.nodes.attach") as attach:
            H3TemporalGainFieldUniformEnergy().apply(object(), self.positive(), enabled=True,
                mode="fixed", alpha_prior=.25, alpha_max=.5, probes=4)
        config=attach.call_args.kwargs['config']
        self.assertEqual(config.mode,'fixed')
        self.assertEqual(config.probes,4)

    def test_bad_intervals_fail_before_attach(self):
        for args in ({"step_start": 20}, {"step_end": 21}, {"block_end": 51},
                     {"block_start": 50}, {"end_frame": 17}, {"start_frame": -1},
                     {"start_frame": 7, "end_frame": 2}, {"probes": 0}, {"alpha_max": .1}, {"basis": "secants"}):
            with self.subTest(args=args), mock.patch("feature_gain_field_uniform_energy.nodes.attach") as attach:
                with self.assertRaises(ValueError):
                    H3TemporalGainFieldUniformEnergy().apply(object(), self.positive(), enabled=True, **args)
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
            result = H3TemporalGainFieldUniformEnergy().apply(model, self.positive(), enabled=True,
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

    def test_causal_layer_states_across_steps_and_independent_runs(self):
        from .attention import FeatureConfig,make_classes
        from .test_feature_attention import FeatureAttentionTests,dense
        core=load_frozen().core;state_type,block_type=make_classes(core)
        q,k,v,heads,plan=FeatureAttentionTests().data();layout=object();inputs={'v':v}
        def attention_pytorch():pass
        def original(args):
            return args['transformer_options']['optimized_attention_override'](
                attention_pytorch,q,k,inputs['v'],heads,skip_reshape=True)
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(core,'flash_attention_lse',dense):
            states=[]
            for run in range(2):
                state=state_type({},'mass_preserve',.25,0,0,0,16,0,50,0,20,
                    'causal_run_'+str(run),tmp,feature_config=FeatureConfig())
                states.append(state)
                self.assertEqual(state.anchors,{})
                with mock.patch.object(state,'plan_for',return_value=plan):
                    for step in range(2):
                        inputs['v']=v*(2**step)*(run+1)
                        for block in range(50):
                            args={'layout':layout,'transformer_options':{'block_index':block,
                                'minimax_h3_layout':layout,'sample_sigmas':torch.tensor([1.,.5,0.])}}
                            block_type(state,block)(args,{'original_block':original})
                    self.assertEqual(state.audit['completed_forward_calls'],2)
                    self.assertEqual(len(state.anchors),50)
                    self.assertTrue(all(x['last_step']==1 and x['anchor_step'].tolist()==[-1,0,-1] for x in state.anchors.values()))
                    self.assertEqual(len({id(x) for x in state.anchors.values()}),50)
                    for step,summary in enumerate(state.audit['feature_forward_summaries']):
                        self.assertEqual(len(summary['layers']),50)
                        for row in summary['layers']:
                            self.assertAlmostEqual(row['alpha_mean'],.25,places=6)
                            self.assertEqual(row['control']['anchor_created'],[False,step==0,False])
                            self.assertEqual(row['control']['usable_evidence'],[False,step>0,False])
            self.assertIsNot(states[0].anchors[0],states[1].anchors[0])
            self.assertAlmostEqual(float(states[1].anchors[0]['anchor_temporal'][1]),
                4*float(states[0].anchors[0]['anchor_temporal'][1]),places=6)

    def test_reusing_consumed_model_fails_before_attention(self):
        from .attention import FeatureConfig,make_classes
        from .test_feature_attention import FeatureAttentionTests,dense
        core=load_frozen().core;state_type,block_type=make_classes(core)
        q,k,v,heads,plan=FeatureAttentionTests().data();layout=object()
        def attention_pytorch():pass
        def original(args):
            return args['transformer_options']['optimized_attention_override'](
                attention_pytorch,q,k,v,heads,skip_reshape=True)
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(core,'flash_attention_lse',side_effect=dense) as attention:
            state=state_type({},'mass_preserve',.25,0,0,0,16,0,50,0,20,
                'single_use',tmp,feature_config=FeatureConfig())
            with mock.patch.object(state,'plan_for',return_value=plan):
                for block in range(50):
                    args={'layout':layout,'transformer_options':{'block_index':block,
                        'minimax_h3_layout':layout,'sample_sigmas':torch.tensor([1.,0.])}}
                    block_type(state,block)(args,{'original_block':original})
                calls=attention.call_count
                args['transformer_options']['block_index']=0
                with self.assertRaisesRegex(ValueError,'state already consumed'):
                    block_type(state,0)(args,{'original_block':original})
                self.assertEqual(attention.call_count,calls)
                self.assertEqual(state.audit['completed_forward_calls'],1)
                self.assertEqual(state.audit['status'],'failed')

    def test_twenty_steps_fifty_layers_complete_finite_audit(self):
        import json
        from .attention import FeatureConfig,make_classes
        from .test_feature_attention import FeatureAttentionTests,dense
        core=load_frozen().core;state_type,block_type=make_classes(core)
        q,k,v,heads,plan=FeatureAttentionTests().data(frames=5,spatial=2,lo=0,hi=5,h=2,d=4)
        layout=object();inputs={'v':v}
        def attention_pytorch():pass
        def original(args):
            return args['transformer_options']['optimized_attention_override'](
                attention_pytorch,q,k,inputs['v'],heads,skip_reshape=True)
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(core,'flash_attention_lse',dense):
            state=state_type({},'mass_preserve',.25,0,0,0,16,0,50,0,20,
                'full_twenty',tmp,feature_config=FeatureConfig())
            with mock.patch.object(state,'plan_for',return_value=plan):
                for step in range(20):
                    for block in range(50):
                        inputs['v']=v*(1+.02*block)*(1+.01*step)
                        args={'layout':layout,'transformer_options':{'block_index':block,
                            'minimax_h3_layout':layout,'sample_sigmas':torch.linspace(1,0,21)}}
                        block_type(state,block)(args,{'original_block':original})
            saved=json.loads((Path(tmp)/'full_twenty.json').read_text())
            self.assertEqual(saved['schema'],'h3-temporal-gain-field-uniform-energy-v1')
            self.assertEqual(saved['completed_forward_calls'],20);self.assertEqual(saved['routed_calls'],1000)
            self.assertEqual(saved['intermediate_vae_decode_calls'],0)
            self.assertEqual(saved['full_dit_forward_calls_added'],0)
            self.assertEqual(len(state.anchors),50)
            for step,summary in enumerate(saved['feature_forward_summaries']):
                self.assertEqual(summary['forward'],step);self.assertEqual(len(summary['layers']),50)
                for block,row in enumerate(summary['layers']):
                    self.assertEqual(row['block'],block);self.assertTrue(row['finite_output'])
                    self.assertEqual(row['attention_calls'],5)
                    self.assertEqual(row['control']['anchor_step'],[-1,0,0,0,-1])
                    self.assertEqual(row['control']['anchor_created'],[False,step==0,step==0,step==0,False])
                    self.assertEqual(row['alpha'][0],.25);self.assertEqual(row['alpha'][-1],.25)
                    self.assertAlmostEqual(row['alpha_mean'],.25,places=5)
                    self.assertAlmostEqual(row['applied_energy'],.0625*row['correction_energy'],places=5)
                    for segment in row['control']['segments']:
                        self.assertTrue(segment['converged']);self.assertLessEqual(segment['kkt_inf'],segment['numeric_tolerance'])
            self.assertEqual(state.anchors[0]['last_step'],19)
            self.assertIsNot(state.anchors[0],state.anchors[49])
            self.assertFalse(torch.equal(state.anchors[0]['anchor_temporal'],state.anchors[49]['anchor_temporal']))
