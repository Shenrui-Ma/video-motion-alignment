"""Synthetic CPU tensors only, including actual-source RNG, KSAMPLER and AV carry."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import torch
from identity import exact_tensor, check_files, tensor_info, file_sha
from condition import swap_latent, replaced_reference, ConditionRowsOracle, prepared_payload
from adapter import arm_native, context_signature, dispatch_delta, exact_capture, QK_NAMES, TENSOR_METADATA, VALUE_METADATA

torch.set_num_threads(1)
torch.set_grad_enabled(False)
SOURCE = json.loads((Path(__file__).parent/'cpu_source_fragments.json').read_text())['definitions']


def actual_condition_class():
    scope = dict(torch=torch, VISUAL_COND_TIMESTEP=.999)
    exec(SOURCE['patchify_video'], scope)
    exec('class Model:\n' + '\n'.join('    '+s for s in SOURCE['_cond_video_rows'].splitlines()), scope)
    scope['Model'].patch_size = (1,2,2)
    return scope['Model']


def payload(z):
    return dict(cond_video_latents=[z], refs=[dict(kind='video', latent=z, latent_t=32)],
                seed=2026101701, audio_scale=4, context=torch.ones(2,3), layout='fixed')


def guider(z):
    return NS(conds={'positive':[{'model_conds': {'minimax_payload':NS(cond=payload(z)), 'c_crossattn':NS(cond=torch.ones(2,3))}}]})


class ConditionTests(unittest.TestCase):
    def setUp(self):
        self.z=torch.arange(32,dtype=torch.float32).reshape(1,1,32,1,1).expand(1,24,32,46,82).clone()
    def test_swap_exact_full_geometry_and_boundaries(self):
        b=swap_latent(self.z)
        self.assertEqual(b.data_ptr()!=self.z.data_ptr(),True)
        self.assertTrue(torch.equal(swap_latent(b),self.z))
        self.assertTrue(torch.equal(b[:,:,5:10],self.z[:,:,10:15]))
        self.assertTrue(torch.equal(b[:,:,15:],self.z[:,:,15:]))
        self.assertEqual((b.device,b.dtype),(self.z.device,self.z.dtype))
    def test_invalid_shape_dtype_finite(self):
        for z in (self.z[:,:,:31],self.z.double(),self.z*float('nan')):
            with self.assertRaises(ValueError):swap_latent(z)
    def test_payload_alias_and_context_unchanged(self):
        g=guider(self.z);old=g.conds;sig=context_signature(g)
        with replaced_reference(g,True) as p:
            self.assertIs(p['refs'][0]['latent'],p['cond_video_latents'][0])
            self.assertIsNot(p['refs'],prepared_payload(NS(conds=old))['refs'])
            self.assertEqual(context_signature(g),sig)
        self.assertIs(g.conds,old)
    def test_payload_restored_on_exception(self):
        g=guider(self.z);old=g.conds
        with self.assertRaises(RuntimeError):
            with replaced_reference(g,True):raise RuntimeError('injected')
        self.assertIs(g.conds,old)
    def test_original_mutation_detected_and_restored_container(self):
        g=guider(self.z);old=g.conds
        with self.assertRaises(ValueError):
            with replaced_reference(g,False):self.z[0,0,0,0,0]+=1
        self.assertIs(g.conds,old)
    def test_real_source_noise_rows_exact_all_four_calls(self):
        m=actual_condition_class()();g=guider(self.z);rng=torch.get_rng_state().clone()
        with ConditionRowsOracle(m) as obs:
            for swap in (False,False,True,True):
                with replaced_reference(g,swap) as p:m._cond_video_rows(p,'cpu')
        self.assertEqual(len(obs.calls),4)
        self.assertEqual(len({v['noise']['sha256'] for v in obs.calls}),1)
        self.assertTrue(torch.equal(rng,torch.get_rng_state()))
        self.assertNotIn('_cond_video_rows',m.__dict__)
        self.assertEqual(obs.calls[0]['augmented_rows'],obs.calls[1]['augmented_rows'])
        self.assertNotEqual(obs.calls[0]['augmented_rows'],obs.calls[2]['augmented_rows'])
    def test_noise_uses_patch_rows_not_latent_shape(self):
        m=actual_condition_class()();p=payload(self.z)
        with ConditionRowsOracle(m) as obs:m._cond_video_rows(p,'cpu')
        g=torch.Generator('cpu').manual_seed(2026101701)
        wrong=m._cond_video_rows.__func__.__globals__['patchify_video'](torch.randn(self.z.shape,generator=g),(1,2,2))
        self.assertFalse(torch.equal(obs.noise,wrong))
    def test_seed_plus_step_forbidden_and_cleanup(self):
        m=actual_condition_class()();p=payload(self.z);p['seed']+=9
        with self.assertRaises(ValueError):
            with ConditionRowsOracle(m):m._cond_video_rows(p,'cpu')
        self.assertNotIn('_cond_video_rows',m.__dict__)


class GateTests(unittest.TestCase):
    def test_tiny_raw_AV_difference_rejected(self):
        a=torch.ones(1,1,10);b=a.clone();b[0,0,-1]+=torch.finfo(torch.float32).eps
        with self.assertRaises(ValueError):exact_tensor(a,b,'audio')
    def test_all_raw_actual_branches_and_norm_metadata(self):
        a={k:torch.ones(2) for k in QK_NAMES+TENSOR_METADATA};a.update({k:0 for k in VALUE_METADATA})
        self.assertTrue(exact_capture(a,copy.deepcopy(a)))
        for key in QK_NAMES+TENSOR_METADATA:
            b=copy.deepcopy(a);b[key][0]+=1
            with self.assertRaises(ValueError):exact_capture(a,b)
        b=copy.deepcopy(a);b['q_norm_eps']=1
        with self.assertRaises(ValueError):exact_capture(a,b)
    def test_swap_keeps_metadata_but_not_qk_equality(self):
        a={k:torch.ones(2) for k in QK_NAMES+TENSOR_METADATA};a.update({k:0 for k in VALUE_METADATA})
        b=copy.deepcopy(a);b['raw_Q_R']*=2
        self.assertTrue(exact_capture(a,b,include_qk=False))
    def test_file_sha_before_decode_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x';p.write_bytes(b'not tensor')
            with self.assertRaises(ValueError):check_files([dict(path=str(p),sha256='0'*64)])
            self.assertEqual(list(Path(tmp).iterdir()),[p])
    def test_actual_backend_schema(self):
        before={'operations':{b+'.'+op:dict(attempted_calls=0,successful_calls=0,failed_calls=0)
             for b in ('cuda','triton','eager') for op in ('int8_linear','w4a8_int8_linear')}}
        before['operations']['triton.int8_linear'].update(attempted_calls=17,successful_calls=17)
        after=copy.deepcopy(before);after['operations']['triton.int8_linear'].update(attempted_calls=217,successful_calls=217)
        self.assertEqual(dispatch_delta(before,after)['triton.int8_linear']['successful'],200)
        after['operations']['cuda.int8_linear']=dict(attempted_calls=1,successful_calls=1,failed_calls=0)
        with self.assertRaises(ValueError):dispatch_delta(before,after)
    def test_missing_backend_rejected(self):
        with self.assertRaises(ValueError):dispatch_delta({'operations':{}},{'operations':{'triton.int8_linear':dict(attempted_calls=200,successful_calls=200,failed_calls=0)}})
    def test_production_rejects_automatic_swaps_before_root_real_zero_review(self):
        from nodes import preflight
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'release.json'
            p.write_text(json.dumps(dict(schema='h3-content-coordinate-root-release-v1',scope='two_zero_then_two_swap',
                maximum_attempts=1,cohort='content_coordinate_calibration')))
            with self.assertRaises(ValueError):preflight(p,file_sha(p))
    def test_outer_failure_cannot_leave_passed_gate(self):
        from nodes import finalize_outer
        from identity import write_json
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'GATE.json'
            raw=torch.ones(1,1,6);shapes=[[1,1,3],[1,1,3]]
            for samples in (torch.ones(2),NS(is_nested=True,unbind=lambda:(torch.ones(1,1,3),torch.ones(1,1,3)))):
                write_json(path,dict(status='forwards_complete',passed=False,outer_normalization_pending=True))
                with self.assertRaises(ValueError):finalize_outer(tmp,samples,raw,shapes)
                self.assertFalse(json.loads(path.read_text())['passed'])
            write_json(path,dict(status='forwards_complete',passed=False,outer_normalization_pending=True))
            finalize_outer(tmp,NS(is_nested=True,unbind=lambda:(torch.ones(1,1,3),torch.ones(1,1,3)/4)),raw,shapes)
            self.assertTrue(json.loads(path.read_text())['passed'])
    def test_short_counter_schema_cannot_pass(self):
        with self.assertRaises(ValueError):dispatch_delta({'operations':{}},{'operations':{'triton.int8_linear':dict(attempted=200,successful=200,failed=0)}})
    def test_context_detects_multimodal_condition_change(self):
        g=guider(torch.zeros(1,24,32,46,82));a=context_signature(g)
        g.conds['positive'][0]['model_conds']['c_crossattn'].cond[0,0]+=1
        self.assertNotEqual(context_signature(g),a)
    def test_router_independent_native_counters(self):
        s=NS(mode='native',forward_index=-1,next_block=0,audit=dict(started_calls=0,completed_calls=0,completed_forward_calls=0))
        o={'transformer_options':{'patches_replace':{'dit':{('double_block',i):NS(state=s) for i in range(50)}}}}
        a,sa=arm_native(o,9,'/tmp/synthetic');b,sb=arm_native(o,19,'/tmp/synthetic')
        self.assertEqual((sa.forward_index,sb.forward_index,s.forward_index),(8,18,-1))
        self.assertIsNot(sa,sb);sa.audit['completed_calls']=50
        self.assertEqual(sb.audit['completed_calls'],0)
        s.forward_index=0
        with self.assertRaises(ValueError):arm_native(o,9,'/tmp/synthetic')
    def test_native_router_inactive_parameters_still_frozen(self):
        from adapter import check_router_contract
        state=NS(mode='native',alpha=1.,active_steps=(6,7,8),radius=0)
        expected=dict(mode='native',alpha=1.,active_steps=[6,7,8],radius=0)
        check_router_contract(state,expected)
        for key in ('alpha','radius','active_steps'):
            altered=copy.copy(state);setattr(altered,key,99)
            with self.assertRaises((ValueError,TypeError)):check_router_contract(altered,expected)


class ActualAVTests(unittest.TestCase):
    def test_actual_H3_audio_carry_once(self):
        class Executor:
            @classmethod
            def new_class_executor(cls,fn,*a):return NS(execute=fn)
        scope=dict(torch=torch,comfy=NS(model_prefetch=NS(malloc_graph_enabled=lambda d:False),patcher_extension=NS(
            WrapperExecutor=Executor,get_all_wrappers=lambda *a:[],WrappersMP=NS(DIFFUSION_MODEL='model'))))
        exec(SOURCE['time_shift_sigma'],scope)
        exec('class Model:\n'+'\n'.join('    '+s for s in SOURCE['forward'].splitlines()),scope)
        model=scope['Model']();model.sigma_shift_video=12;model.sigma_shift_audio=3
        observed=[]
        def inner(x,*a,**kw):observed.append([v.clone() for v in x]);return [x[0]*.2,x[1]*.3]
        model._forward=inner
        v=torch.ones(2);a=torch.ones(2)*4;sigma=torch.tensor(.75)
        result=model.forward([v,a],sigma.reshape(1)*1000,None,minimax_payload={'audio_scale':4})
        sa=scope['time_shift_sigma'](sigma,12,3);carry=sa/sigma
        self.assertEqual(len(observed),1)
        self.assertTrue(torch.equal(observed[0][1],a*carry))
        expected=(-3)*(a*carry)+(1+3*sa)*(.3*a*carry)
        self.assertTrue(torch.equal(result[1],expected))
        self.assertTrue(torch.equal(a,torch.ones(2)*4))
    def test_actual_ModelSamplingAV_scale(self):
        class Parent:
            def __init__(self,c=None):self.shift=12
            def set_parameters(self,shift=1.,**kw):self.shift=shift
        scope={'ModelSamplingDiscreteFlow':Parent}
        exec(SOURCE['ModelSamplingAV'],scope)
        a=scope['ModelSamplingAV'](NS(sampling_settings={'audio_shift':3}))
        self.assertEqual(a.audio_scale,4)
    def test_actual_KSAMPLER_replaces_initial_with_saved_x_only_once(self):
        class Sampler:
            def max_denoise(self,*a):return True
        scope=dict(torch=torch,Sampler=Sampler,detail=lambda *a,**kw:None)
        for name in ('reshape_sigma','CONST','KSamplerX0Inpaint','KSAMPLER'):exec(SOURCE[name],scope)
        ms=scope['CONST']();ms.noise_scale=1.
        calls=[];saved=torch.full((1,1,10),.42)
        def predict(x,sigma,**kw):calls.append(x.clone());return x*.2
        class Guider:
            inner_model=NS(model_sampling=ms)
            def __call__(self,x,sigma,**kw):return predict(x,sigma,**kw)
        def finite(m,x,sigmas,**kw):
            self.assertTrue(torch.equal(x,torch.ones_like(x)))
            return m(saved.clone(),sigmas[9]*saved.new_ones([1]),**kw['extra_args'])
        sampler=scope['KSAMPLER'](finite)
        out=sampler.sample(Guider(),torch.linspace(1,0,21),{'model_options':{},'seed':2026101701},None,
                           torch.ones_like(saved),torch.zeros_like(saved),None,True)
        self.assertEqual(len(calls),1);self.assertTrue(torch.equal(calls[0],saved))
        self.assertTrue(torch.equal(out,saved*.2))


class LiveMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.contract=json.loads((Path(__file__).parent/'native_contract.json').read_text())
        self.entries={};self.docs={}
        for step in (9,19):
            entry={};s=dict(schema='h3-live-phase-state-v1',step_zero_based=step,
                target_shapes=self.contract['target_shapes'],sample_sigmas_video=self.contract['sigmas_video'],
                packed_x=torch.zeros(1,1,2908288),raw_packed_x0=torch.ones(1,1,2908288))
            for name in ('state','qk'):
                p=self.root/(name+str(step));p.write_text(name+str(step));entry[name]=dict(path=str(p),sha256=file_sha(p))
            q=dict(schema='h3-passive-qk-capture-v1',step_zero_based=step,layer_zero_based=25,
                case=self.contract['case'],method='native',trajectory_id=self.contract['trajectory_id'],
                sample_sigmas_video=self.contract['sigmas_video'],heads=56,head_dim=128,
                spatial_ids=[0,135,269,404,538,673,807,942],valid_bins=[True]*31+[False])
            q.update({name:torch.zeros(32,8,56,128,dtype=torch.bfloat16) for name in QK_NAMES})
            q['forward_identity']=dict(case=q['case'],method=q['method'],trajectory_id=q['trajectory_id'],
                step_zero_based=step,layer_zero_based=25,state_file_sha256=entry['state']['sha256'],
                science_contract_sha256=file_sha(Path(__file__).parent/'native_contract.json'),
                sample_sigmas_video=self.contract['sigmas_video'],noise_sha256=self.contract['noise_tensor_sha256'],
                packed_x=tensor_info(s['packed_x']),raw_packed_x0=tensor_info(s['raw_packed_x0']))
            self.entries[str(step)]=entry;self.docs[entry['state']['path']]=s;self.docs[entry['qk']['path']]=q
    def tearDown(self):self.tmp.cleanup()
    def load(self):
        from identity import load_live_inputs
        with patch('identity.torch.load',side_effect=lambda p,**kw:self.docs[str(p)]):
            return load_live_inputs(self.entries,self.contract)
    def test_actual_state_file_sha256_schema(self):self.assertEqual(set(self.load()),{9,19})
    def test_old_wrong_state_sha_key_rejected(self):
        q=self.docs[self.entries['9']['qk']['path']];q['forward_identity']['state_sha256']=q['forward_identity'].pop('state_file_sha256')
        with self.assertRaises(KeyError):self.load()
    def test_trajectory_step_or_state_signature_rejected(self):
        q=self.docs[self.entries['9']['qk']['path']]
        for key,value in [('method','global_weak'),('step_zero_based',19),('science_contract_sha256','0'*64)]:
            old=q['forward_identity'][key];q['forward_identity'][key]=value
            with self.assertRaises(ValueError):self.load()
            q['forward_identity'][key]=old
        self.docs[self.entries['9']['state']['path']]['packed_x'][0,0,0]=1
        with self.assertRaises(ValueError):self.load()
    def test_all_file_hashes_checked_before_any_decode(self):
        from identity import load_live_inputs
        self.entries['19']['qk']['sha256']='0'*64
        with patch('identity.torch.load') as decode:
            with self.assertRaises(ValueError):load_live_inputs(self.entries,self.contract)
            decode.assert_not_called()


if __name__=='__main__':unittest.main()
