import json
import tempfile
import types
from pathlib import Path
import unittest
from unittest import mock
import torch
from . import NODE_CLASS_MAPPINGS
from .nodes import H3CausalLayerBudget
from .attention import FeatureConfig,make_classes
from .frozen import load_frozen
from .test_attention import data,dense

class NodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)
    def positive(self):
        return [[torch.zeros(1,3,2),{'minimax_refs':[{'kind':'video','latent_t':5,'latent_h':2,'latent_w':2,
            'latent':torch.zeros(1,24,5,2,2),'ref_audio_t':0}]}]]
    def test_registration_disabled_and_defaults(self):
        self.assertIs(NODE_CLASS_MAPPINGS['H3CausalLayerBudget'],H3CausalLayerBudget)
        spec=H3CausalLayerBudget.INPUT_TYPES()['required'];self.assertEqual(spec['mode'][0][0],'layer_budget')
        self.assertEqual(spec['probes'][1]['default'],8)
        obj=object()
        with mock.patch('feature_layer_budget.nodes.load_frozen',side_effect=AssertionError):
            self.assertIs(H3CausalLayerBudget().apply(obj,None)[0],obj)
    def test_node_forwards_geometry_and_rejects_bad_settings(self):
        with mock.patch('feature_layer_budget.nodes.attach') as attach:
            H3CausalLayerBudget().apply(object(),self.positive(),enabled=True)
            args=attach.call_args.kwargs;self.assertEqual((args['start_frame'],args['end_frame']),(0,16))
            self.assertEqual((args['block_start'],args['block_end']),(0,50));self.assertEqual(args['config'].mode,'layer_budget')
        for kw in ({'alpha_prior':.2},{'alpha_max':.8},{'probes':0},{'step_end':21},{'block_end':51},{'basis':'secants'}):
            with mock.patch('feature_layer_budget.nodes.attach') as attach,self.assertRaises(ValueError):
                H3CausalLayerBudget().apply(object(),self.positive(),enabled=True,**kw)
            attach.assert_not_called()
    def test_attach_clones_fifty_blocks(self):
        h3=types.ModuleType('comfy.ldm.minimax.model');h3.MiniMaxH3Model=type('MiniMaxH3Model',(),{})
        h3.FRAME_PER_TOKEN=(1,4,4,4,4)
        def attention_pytorch():pass
        h3.optimized_attention=attention_pytorch
        modules={n:types.ModuleType(n) for n in ('comfy','comfy.ldm','comfy.ldm.minimax')};modules['comfy.ldm.minimax.model']=h3
        modules['comfy'].ldm=modules['comfy.ldm'];modules['comfy.ldm'].minimax=modules['comfy.ldm.minimax'];modules['comfy.ldm.minimax'].model=h3
        diff=h3.MiniMaxH3Model();diff.blocks=[object() for _ in range(50)];model,clone=mock.Mock(),mock.Mock()
        model.get_model_object.return_value=diff;model.model_options={};model.clone.return_value=clone
        with tempfile.TemporaryDirectory() as tmp,mock.patch.dict('sys.modules',modules):
            result=H3CausalLayerBudget().apply(model,self.positive(),enabled=True,audit_dir=tmp,run_id='node')
            self.assertIs(result[0],clone);self.assertEqual(clone.set_model_patch_replace.call_count,50)
            saved=json.loads((Path(tmp)/'node.json').read_text());self.assertEqual(saved['schema'],'h3-causal-layer-budget-v1')
    def test_twenty_by_fifty_causality_energy_and_fallback(self):
        core=load_frozen().core;State,Block=make_classes(core);q,k,v,heads,plan=data();layout=object()
        now={'step':0,'block':0};outputs=[]
        def attention_pytorch():pass
        def components(s,r,p,n,m,**kw):
            shape=s.shape[:-1];step,b=now['step'],now['block']
            A=1. if step==0 else .3+(b+1)/25
            count=(m>0).clone()
            if step==3 and b==13:count.zero_()
            return {'temporal_energy':torch.full(shape,A)*count,'complement_energy':torch.ones(shape)*count,'valid':count}
        def original(args):
            qq=q*(1+.02*now['step']*(1+now['block']/50))
            out=args['transformer_options']['optimized_attention_override'](attention_pytorch,qq,k,v,heads,skip_reshape=True)
            if now['step']<2:
                expected=core.route_attention(qq,k,v,heads,plan,mode='mass_preserve',alpha=.25,attention=dense)
                self.assertTrue(torch.equal(out,expected))
            return out
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(core,'flash_attention_lse',dense),mock.patch('feature_layer_budget.attention.temporal_components',side_effect=components):
            state=State({},'mass_preserve',.25,0,0,0,16,0,50,0,20,'full',tmp,feature_config=FeatureConfig())
            with mock.patch.object(state,'plan_for',return_value=plan):
                for step in range(20):
                    snapshot=state.layer_plan.clone();anchors_before={b:a['last_step'] for b,a in state.anchors.items()}
                    for b in range(50):
                        now.update(step=step,block=b)
                        args={'layout':layout,'transformer_options':{'block_index':b,'minimax_h3_layout':layout,'sample_sigmas':torch.linspace(1,0,21)}}
                        Block(state,b)(args,{'original_block':original})
                        if b<49:
                            self.assertTrue(torch.equal(state.layer_plan,snapshot))
                            self.assertEqual({j:a['last_step'] for j,a in state.anchors.items()},anchors_before)
                            self.assertEqual(len(state.audit['layer_budget_summaries']),step)
                    self.assertEqual(state.plan_source_forward,step);self.assertEqual(state.plan_for_forward,step+1)
                saved=json.loads((Path(tmp)/'full.json').read_text())
                self.assertEqual(saved['completed_forward_calls'],20);self.assertEqual(saved['routed_calls'],1000)
                self.assertEqual(len(saved['layer_budget_summaries']),20);self.assertEqual(saved['full_dit_forward_calls_added'],0)
                self.assertEqual(saved['intermediate_vae_decode_calls'],0)
                for step,summary in enumerate(saved['layer_budget_summaries']):
                    self.assertEqual(summary['plan_source_forward'],step-1);self.assertEqual(summary['plan_for_forward'],step)
                    if step<2:self.assertEqual(summary['actual_alpha'],[.25]*50)
                    else:
                        self.assertAlmostEqual(summary['predicted_plan_budget']['ratio'],1.,places=12)
                    self.assertLessEqual(summary['allocation']['predicted_budget_ratio'],1.+1e-12)
                self.assertGreater(max(saved['layer_budget_summaries'][2]['actual_alpha'])-min(saved['layer_budget_summaries'][2]['actual_alpha']),.05)
                failed_layer=saved['feature_forward_summaries'][3]['layers'][13]
                self.assertTrue(failed_layer['local_fallback_to_prior']);self.assertEqual(failed_layer['alpha_mean'],.25)
                self.assertFalse(saved['layer_budget_summaries'][3]['current_eligible'][13])
                self.assertEqual(saved['layer_budget_summaries'][3]['next_alpha'][13],.25)
                self.assertTrue(any(abs(s['current_actual_drift']['ratio']-1.)>1e-4 for s in saved['layer_budget_summaries'][2:]))
                for summary in saved['feature_forward_summaries']:
                    for row in summary['layers']:
                        c=row['quality_calibration'];self.assertEqual(c['anchor_step'],0)
                        self.assertEqual(c['anchor_temporal'],12.);self.assertEqual(c['anchor_complement'],12.)
                        self.assertTrue(row['finite_output']);self.assertEqual(row['attention_calls'],5)
                calls=saved['completed_forward_calls']
                args['transformer_options']['block_index']=0
                with self.assertRaisesRegex(ValueError,'state already consumed'):Block(state,0)(args,{'original_block':original})
                self.assertEqual(state.audit['completed_forward_calls'],calls)
    def test_incomplete_forward_never_allocates_or_updates_anchors(self):
        core=load_frozen().core;State,Block=make_classes(core);q,k,v,heads,plan=data();layout=object()
        def attention_pytorch():pass
        def original(args):return args['transformer_options']['optimized_attention_override'](attention_pytorch,q,k,v,heads,skip_reshape=True)
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(core,'flash_attention_lse',dense):
            state=State({},'mass_preserve',.25,0,0,0,16,0,50,0,20,'failure',tmp,feature_config=FeatureConfig())
            with mock.patch.object(state,'plan_for',return_value=plan):
                for b in range(3):
                    args={'layout':layout,'transformer_options':{'block_index':b,'minimax_h3_layout':layout,'sample_sigmas':torch.tensor([1.,0.])}}
                    Block(state,b)(args,{'original_block':original})
                self.assertEqual(state.anchors,{});self.assertEqual(state.audit['layer_budget_summaries'],[])
                with self.assertRaisesRegex(ValueError,'unexpected block order'):Block(state,8)(args,{'original_block':original})
                self.assertEqual(state.audit['completed_forward_calls'],0);self.assertEqual(state.plan_source_forward,-1)
    def test_new_runs_have_independent_plans_and_anchors(self):
        core=load_frozen().core;State,_=make_classes(core)
        with tempfile.TemporaryDirectory() as tmp:
            a=State({},'mass_preserve',.25,0,0,0,16,0,50,0,20,'a',tmp,feature_config=FeatureConfig())
            b=State({},'mass_preserve',.25,0,0,0,16,0,50,0,20,'b',tmp,feature_config=FeatureConfig())
            a.layer_plan[0]=.5;a.anchors[0]={'x':1}
            self.assertEqual(b.layer_plan[0],.25);self.assertEqual(b.anchors,{})

    def test_real_probe_calibration_first_two_steps_and_fixed_anchors(self):
        core=load_frozen().core;State,Block=make_classes(core);q,k,v,heads,plan=data();layout=object()
        def attention_pytorch():pass
        def original(args):
            return args['transformer_options']['optimized_attention_override'](attention_pytorch,q,k,v,heads,skip_reshape=True)
        expected=core.route_attention(q,k,v,heads,plan,mode='mass_preserve',alpha=.25,attention=dense)
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(core,'flash_attention_lse',dense):
            state=State({},'mass_preserve',.25,0,0,0,16,0,50,0,20,'real_probes',tmp,feature_config=FeatureConfig())
            with mock.patch.object(state,'plan_for',return_value=plan):
                saved_anchors=None
                for step in range(2):
                    for b in range(50):
                        args={'layout':layout,'transformer_options':{'block_index':b,'minimax_h3_layout':layout,'sample_sigmas':torch.tensor([1.,.5,0.])}}
                        y=Block(state,b)(args,{'original_block':original})
                        self.assertTrue(torch.equal(y,expected))
                    now=[(float(x['anchor_temporal']),float(x['anchor_complement'])) for x in state.anchors.values()]
                    if saved_anchors is not None:self.assertEqual(now,saved_anchors)
                    saved_anchors=now
            self.assertTrue(all(x>0 and y>0 for x,y in saved_anchors))
            self.assertEqual(state.audit['layer_budget_summaries'][0]['current_quality'],[.5]*50)
            self.assertEqual(state.audit['layer_budget_summaries'][1]['actual_alpha'],[.25]*50)

    def test_stale_source_forward_rejected_before_attention(self):
        core=load_frozen().core;State,Block=make_classes(core);q,k,v,heads,plan=data();layout=object()
        def attention_pytorch():pass
        def original(args):return args['transformer_options']['optimized_attention_override'](attention_pytorch,q,k,v,heads,skip_reshape=True)
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(core,'flash_attention_lse',side_effect=dense) as attention:
            state=State({},'mass_preserve',.25,0,0,0,16,0,50,0,20,'stale',tmp,feature_config=FeatureConfig())
            state.plan_source_forward=-2
            with mock.patch.object(state,'plan_for',return_value=plan):
                args={'layout':layout,'transformer_options':{'block_index':0,'minimax_h3_layout':layout,'sample_sigmas':torch.tensor([1.,0.])}}
                with self.assertRaisesRegex(ValueError,'completed earlier forward'):Block(state,0)(args,{'original_block':original})
            attention.assert_not_called();self.assertEqual(state.audit['completed_forward_calls'],0)

    def test_low_old_anchor_signal_only_changes_next_plan(self):
        core=load_frozen().core;State,Block=make_classes(core);q,k,v,heads,plan=data();layout=object();now={'step':0,'block':0}
        def attention_pytorch():pass
        def original(args):return args['transformer_options']['optimized_attention_override'](attention_pytorch,q,k,v,heads,skip_reshape=True)
        def components(s,r,p,n,m,**kw):
            mask=(m>0);A=1. if now['step']==0 else .3+(now['block']+1)/25
            if now['step']==2:A=1e-10
            B=1e-10 if now['step']==2 else 1.
            return {'temporal_energy':mask*A,'complement_energy':mask*B,'valid':mask}
        with tempfile.TemporaryDirectory() as tmp,mock.patch.object(core,'flash_attention_lse',dense),mock.patch('feature_layer_budget.attention.temporal_components',side_effect=components):
            state=State({},'mass_preserve',.25,0,0,0,16,0,50,0,20,'tiny_anchor',tmp,feature_config=FeatureConfig())
            with mock.patch.object(state,'plan_for',return_value=plan):
                for step in range(3):
                    for b in range(50):
                        now.update(step=step,block=b)
                        args={'layout':layout,'transformer_options':{'block_index':b,'minimax_h3_layout':layout,'sample_sigmas':torch.linspace(1,0,4)}}
                        Block(state,b)(args,{'original_block':original})
            summary=state.audit['layer_budget_summaries'][2]
            self.assertGreater(max(summary['actual_alpha'])-min(summary['actual_alpha']),.05)
            self.assertEqual(summary['next_alpha'],[.25]*50)
            for row in state.audit['feature_forward_summaries'][2]['layers']:
                self.assertTrue(row['raw_probe_evidence_valid']);self.assertTrue(row['current_evidence_valid'])
                self.assertFalse(row['local_fallback_to_prior'])
                self.assertTrue(row['anchor_low_current_energy']);self.assertFalse(row['current_anchor_evidence_valid'])
                self.assertFalse(row['next_plan_eligible'])
