import ast
import copy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

import torch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions'),str(ROOT/'analysis/postrun')]
import r132_contract as contract
import H3TemporalRouter as node
import H3TemporalRouter.reference_origin as branch
from fixtures import fixture
from test_reference_origin import dense
from verify_reference_origin import check_reference_origin, clean_condition, compare_conditions


class ContractTests(unittest.TestCase):
    def test_exact_parent_graph_except_operator_and_admin(self):
        jobs,order=contract.registry()
        self.assertEqual(order,[contract.RUN_ID])
        self.assertEqual(jobs[order[0]]['arm'],'reference_origin')
        self.assertEqual(contract.read(ROOT/'configs/graphs'/f'{contract.RUN_ID}.json'),contract.expected_graph(ROOT))

    def test_controller_queries_the_actual_graph_node(self):
        class_name=contract.expected_graph(ROOT)['50']['class_type']
        constants=[n.value for n in ast.walk(ast.parse((ROOT/'scripts/start_controller.py').read_text()))
                   if isinstance(n,ast.Constant) and isinstance(n.value,str)]
        self.assertIn(class_name,constants)
        self.assertTrue(any(value.endswith('/object_info/'+class_name) for value in constants))
        self.assertFalse(any('H3AlignedMediaClock' in value for value in constants))

    def test_modified_sampler_or_prompt_rejected(self):
        original=contract.read
        for kind in ('sigma','prompt'):
            def changed(path):
                value=original(path)
                if Path(path).parent.name=='graphs':
                    if kind=='sigma':value['9']['inputs']['sigmas']='1,0'
                    else:value['5']['inputs']['prompt']+=' fast'
                return value
            with self.subTest(kind=kind),mock.patch.object(contract,'read',side_effect=changed),self.assertRaises(ValueError):contract.registry()

    def test_core_diff_is_only_local_override_factory(self):
        adapter=contract.read(ROOT/'design/CORE_FACTORY_ADAPTER.json')
        original=(ROOT/'design/R129_core.py').read_text()
        self.assertEqual(contract.sha(ROOT/'design/R129_core.py'),adapter['parent_sha256'])
        expected=original.replace('class EventBlockPatch:\n','class EventBlockPatch:\n    override_class = TemporalAttentionOverride\n').replace('override = TemporalAttentionOverride(state, plan, self.block_index)','override = self.override_class(state, plan, self.block_index)')
        self.assertEqual((ROOT/'extensions/H3TemporalRouter/core.py').read_text(),expected)

    def test_preflight_and_original_condition_preservation(self):
        from preflight import check
        self.assertTrue(check()['passed'])
        original=contract.read(ROOT/'design/r122_long_0039_shared_conditioning.json');other=copy.deepcopy(original)
        other['run_id']='new';other['pair_snapshot']={'admin':True}
        self.assertEqual(clean_condition(original),clean_condition(other))
        other['packed_layout']['position_ids']['sha256']='f'*64
        self.assertNotEqual(clean_condition(original),clean_condition(other))

    def test_manifest_declares_actual_prefix_and_noise(self):
        science=contract.read(ROOT/'configs/scientific_contract.json')
        self.assertEqual(science['parent_noise_sha256'],'149c638af54913020b9c3f49c5625aba8a44efa3e326738834f6be9e87a1f943')
        self.assertFalse(science['reference_origin']['first_six_prediction_equality_required'])
        manifest=contract.read(ROOT/'design/R122_native_x0_manifest.json')
        self.assertEqual(manifest['run_id'],science['parent_run']);self.assertEqual(manifest['callback_count'],20)

    def test_cross_host_conditions_record_float_changes_but_reject_pixel_layout_changes(self):
        original=contract.read(ROOT/'design/r122_long_0039_shared_conditioning.json')
        changed=copy.deepcopy(original)
        for record in (changed['native_vae_calls'][0]['latent'],changed['conditioning_embedding']):
            record['sha256']='f'*64;record['tensor_file']='tensor_blobs/other.pt'
        comparison=compare_conditions(changed,original)
        self.assertTrue(comparison['strict_metadata_pixels_tokens_positions_equal'])
        self.assertFalse(comparison['floating_model_output_hashes']['vae_latent']['sha256_equal'])
        for key in ('input_video','token_tags'):
            bad=copy.deepcopy(changed);bad[key]['sha256']='e'*64
            self.assertFalse(compare_conditions(bad,original)['strict_metadata_pixels_tokens_positions_equal'])
        bad=copy.deepcopy(changed);bad['packed_layout']['position_ids']['sha256']='e'*64
        self.assertFalse(compare_conditions(bad,original)['strict_metadata_pixels_tokens_positions_equal'])
        bad=copy.deepcopy(changed);bad['conditioning_embedding']['shape'][1]+=1
        with self.assertRaises(ValueError):compare_conditions(bad,original)

    def test_cross_host_prefix_difference_is_observed_and_schema_is_strict(self):
        from prefix_diagnostics import summarize,compare
        parent=torch.arange(2048,dtype=torch.float32);summary=summarize(parent)
        same=compare(parent,summary);changed=compare(parent+2,summary)
        self.assertTrue(same['full_tensor_sha256_equal'])
        self.assertFalse(changed['full_tensor_sha256_equal']);self.assertFalse(changed['equality_required'])
        self.assertEqual(changed['sample_difference_rms'],2.)
        self.assertEqual(changed['sample_difference_max_abs'],2.)
        with self.assertRaises(ValueError):compare(parent[:100],summary)


class RuntimeTests(unittest.TestCase):
    def test_1000_original_table_calls_fixed450_branch_calls_no_rng_or_mutation(self):
        meta,layout,_=fixture(True)
        inv=torch.linspace(.01,1,16)
        with tempfile.TemporaryDirectory() as directory:
            state=branch.ReferenceOriginState(meta,'mass_preserve',1.,0,0,0,5,0,50,6,15,
                'runtime_fixture',directory,inv_freq=inv)
            patches=[branch.ReferenceOriginBlockPatch(state,i) for i in range(50)]
            torch.manual_seed(5)
            q,k,v=[torch.randn(1,1,layout.seq_len,128) for _ in range(3)]
            original_qkv=[x.clone() for x in (q,k,v)];table=torch.ones(1)
            rng=torch.random.get_rng_state().clone();pos=layout.position_ids.clone()
            seen=[];baseline=dense(q,k,v)[0].transpose(1,2).reshape(1,layout.seq_len,128)
            actual_origin=branch.origin_attention;actual_native=branch.route_attention
            def origin(*args,**kwargs):return actual_origin(*args,**kwargs,attention=dense)
            def native(*args,**kwargs):return actual_native(*args,**kwargs,attention=dense)
            def attention_pytorch(*args,**kwargs):raise AssertionError('unwrapped native')
            def original(args):
                self.assertIs(args['rope_freqs'],table);self.assertIs(args['layout'],layout)
                out=args['transformer_options']['optimized_attention_override'](attention_pytorch,q,k,v,1,skip_reshape=True)
                if state.forward_index<6 or state.forward_index>=15:self.assertTrue(torch.equal(out,baseline))
                seen.append(state.forward_index)
                return {'img':out}
            with mock.patch.object(branch,'origin_attention',side_effect=origin),mock.patch.object(branch,'route_attention',side_effect=native):
                for step in range(20):
                    for i,patch in enumerate(patches):
                        options={'block_index':i,'minimax_h3_layout':layout,'sample_sigmas':torch.linspace(1,0,21)}
                        args={'layout':layout,'rope_freqs':table,'transformer_options':options}
                        patch(args,{'original_block':original})
                        self.assertNotIn('optimized_attention_override',options)
            self.assertEqual(len(seen),1000)
            self.assertEqual(state.audit['routed_by_forward'],[0]*6+[50]*9+[0]*5)
            self.assertEqual(state.audit['routed_by_block'],[9]*50)
            self.assertEqual(state.audit['reference_origin']['rotation_calls'],450)
            self.assertEqual(state.audit['reference_origin']['original_rope_table_calls'],1000)
            self.assertEqual(state.audit['reference_origin']['layout_validation_count'],1)
            self.assertEqual(len(state.rotation.cache),1)
            self.assertTrue(torch.equal(pos,layout.position_ids));self.assertTrue(torch.equal(rng,torch.random.get_rng_state()))
            for a,b in zip((q,k,v),original_qkv):self.assertTrue(torch.equal(a,b))
            layout.position_ids[0,0]+=1
            with self.assertRaises(ValueError):state.prepare_origin(layout)

    def test_gate_rejects_wrong_sign_or_scope_or_counts(self):
        from H3TemporalRouter.alignment import aligned_positions
        meta,layout,_=fixture();_,details=aligned_positions(layout,meta)
        rotation=branch.TemporalPhaseRotation(torch.linspace(.01,1,16),details['target_time_displacement'])
        record={'run_id':contract.RUN_ID,'reference_origin':{'layout':details,'rotation':rotation.metadata(),
            'new_method_claim':False,'original_QKV_and_table_preserved':True,'extra_query_scope':'target_video_only',
            'reference_scope':'all_video_reference_keys','first_six_prediction_equality_required':False,
            'layout_validation_count':1,'rotation_calls':450,'original_rope_table_calls':1000}}
        self.assertTrue(check_reference_origin(record,contract.RUN_ID,details['original_position_sha256']))
        for key,value in [('rotation_calls',1000),('extra_query_scope','all_queries'),('original_rope_table_calls',999),('first_six_prediction_equality_required',True)]:
            altered=copy.deepcopy(record);altered['reference_origin'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):check_reference_origin(altered,contract.RUN_ID,details['original_position_sha256'])
        altered=copy.deepcopy(record);altered['reference_origin']['rotation']['displacement_rope_units']*= -1
        with self.assertRaises(ValueError):check_reference_origin(altered,contract.RUN_ID,details['original_position_sha256'])


class NodeTests(unittest.TestCase):
    def test_patches_all50_blocks_with_shared_reference_state(self):
        meta,_,_=fixture()
        class Diffusion:
            patch_size=(1,2,2);latents_dim=24;blocks=[None]*50
            rope=types.SimpleNamespace(inv_freq=torch.linspace(.01,1,16))
        diffusion=Diffusion()
        class Model:
            model_options={}
            def __init__(self):self.patches={}
            def get_model_object(self,name):return diffusion
            def clone(self):return Model()
            def set_model_patch_replace(self,patch,family,kind,index):self.patches[index]=patch
        model=Model();h3=types.ModuleType('comfy.ldm.minimax.model');h3.MiniMaxH3Model=Diffusion
        h3.FRAME_PER_TOKEN=(1,4,4,4,4);h3.FRAME_RESCALE=5/3
        def attention_pytorch(*a):pass
        h3.optimized_attention=attention_pytorch
        modules={name:types.ModuleType(name) for name in ('comfy','comfy.ldm','comfy.ldm.minimax')};modules['comfy.ldm.minimax.model']=h3
        for a,b in [('comfy','ldm'),('comfy.ldm','minimax'),('comfy.ldm.minimax','model')]:setattr(modules[a],b,modules[a+'.'+b])
        kw={k:v for k,v in contract.expected_graph(ROOT)['50']['inputs'].items() if k not in ('model','positive')}
        with tempfile.TemporaryDirectory() as folder,mock.patch.dict(sys.modules,modules),mock.patch.object(node,'validate_run_contract'),mock.patch.object(node,'conditioning_metadata',return_value=meta):
            kw['audit_dir']=folder;result=node.H3ReferenceOrigin().apply(model,[],**kw)[0]
            self.assertEqual(len(result.patches),50);self.assertEqual(model.patches,{})
            self.assertTrue(all(isinstance(p,branch.ReferenceOriginBlockPatch) for p in result.patches.values()))
            self.assertEqual(len({id(p.state) for p in result.patches.values()}),1)
            state=result.patches[0].state;self.assertEqual((state.step_start,state.step_end,state.alpha),(6,15,1.))
            self.assertTrue(torch.equal(state.actual_inv_freq,diffusion.rope.inv_freq))


if __name__=='__main__':
    torch.set_num_threads(2)
    unittest.main()
