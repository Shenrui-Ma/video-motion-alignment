"""Actual Euler + KSAMPLER + CFGGuider + EventBlockPatch lifecycle on CPU.

The selected attention uses the real H3 Attention/RMS/RoPE source. Other block
bodies are cheap toy identities; each real EventBlockPatch still executes once.
This tests observation, not numerical equivalence of a full trained H3 model.
"""
import ast,copy,json,math,os,re,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import torch
from observer import LiveObservation
from reconstruct import pack,tensor_info
from source_oracles import actual_sampler_classes,actual_attention_and_layout,actual_euler

torch.set_num_threads(1);torch.set_grad_enabled(False)

class OriginalFailure(RuntimeError):pass

def real_router(root):
    class Override:
        def __init__(self,state,plan,block):self.calls=0
    scope=dict(math=math,re=re,Path=Path,time=time,json=json,os=os,MODES=('native','mass_preserve'),VALUE_SPLIT_MODES=(),TemporalAttentionOverride=Override)
    tree=ast.parse((Path(__file__).parent/'sources/frozen_router_core.py').read_text())
    for n in tree.body:
        if getattr(n,'name',None) in ('RouterState','EventBlockPatch'):exec(compile(ast.Module(body=[n],type_ignores=[]),'frozen_router_core','exec'),scope)
    state=scope['RouterState']({},'native',1.,0,0,0,12,0,50,6,15,'toy',str(root/'router'))
    state.active_steps=tuple(range(6,15));state.plan_for=lambda layout:{'seq_len':layout.seq_len}
    return state,scope['EventBlockPatch']

class LiveTests(unittest.TestCase):
    def setUp(self):
        self.inf=torch.inference_mode();self.inf.__enter__();torch.manual_seed(812)
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.actual=actual_sampler_classes();self.h3=actual_attention_and_layout()
        self.shapes=[[1,24,4,4,8],[1,32,2,5]];self.noise=pack([torch.randn(s) for s in self.shapes]);self.sigmas=torch.linspace(1,0,21)
        self.state,Patch=real_router(self.root)
        self.layout=self.h3['PackedLayout'](3,4,4,8,5,refs=[dict(kind='video',latent_t=4,latent_h=4,latent_w=8,ref_audio_t=0)])
        self.attn=self.h3['Attention'](16,56,128,1e-5,operations=torch.nn).eval()
        self.rope=self.h3['rope_rotation_table'](torch.randn(self.layout.seq_len,96)*.01,torch.float32)
        self.patches={('double_block',i):Patch(self.state,i) for i in range(50)}
        self.options={'transformer_options':{'sample_sigmas':self.sigmas,'patches_replace':{'dit':self.patches}}}
        owner=self
        class TinyModel(torch.nn.Module):
            def __init__(self):
                super().__init__();self.a=owner.attn;self.blocks=[SimpleNamespace(attn=owner.attn) for _ in range(50)];self.calls=0;self.xs=[];self.x0s=[]
            def forward(self,x,sigma):
                call=self.calls;self.calls+=1
                if getattr(owner,'fail_at',None)==call:raise OriginalFailure('model failure at actual step9')
                y=x.reshape(-1)[:owner.layout.seq_len*16].reshape(owner.layout.seq_len,16)
                for i in range(50):
                    args={'layout':owner.layout,'transformer_options':{'block_index':i,'minimax_h3_layout':owner.layout,'sample_sigmas':owner.sigmas}}
                    def block(a,i=i):
                        a['transformer_options']['optimized_attention_override'].calls+=1
                        return self.a(y,owner.rope) if i==25 else None
                    val=owner.patches[('double_block',i)](args,{'original_block':block})
                    if i==25:mean=val.float().mean()
                result=x*.71-sigma.view(1,1,1)*mean
                self.xs.append(x.clone());self.x0s.append(result.clone())
                return result
        self.model=TinyModel().eval()
        sampling=self.actual['CONST']();sampling.noise_scale=1.
        self.base=SimpleNamespace(latent_shapes=self.shapes,audio_scale=lambda:4.,model_sampling=sampling,diffusion_model=self.model,predict=lambda x,sigma,model_options,seed:self.model(x,sigma))
        self.guider=self.actual['CFGGuider'](SimpleNamespace(model_options=self.options,model=self.base));self.guider.inner_model=self.base
        self.guider.conds={'positive':[{'model_conds':{'minimax_payload':SimpleNamespace(cond={'layout':self.layout,'audio_scale':4.,'seed':44})}}]}
        self.sampler=self.actual['KSAMPLER'](actual_euler())
        class Executor:
            class_obj=owner.sampler
            def __call__(self,*a):
                self.result=self.class_obj.sample(*a);return self.result
        self.executor=Executor()
        self.spec={'trajectory_id':'live_toy','output_dir':str(self.root/'observation'),'case':'short_0358','method':'native','seed':44,'valid_frames':13,'sigmas_video':self.sigmas.double().tolist(),'target_shapes':self.shapes,'noise_tensor_sha256':tensor_info(self.noise)['sha256'],'router':{'mode':'native','alpha':1.,'active_steps':list(range(6,15)),'radius':0,'time_offset':0,'start_frame':0,'end_frame':12,'block_start':0,'block_end':50}}
        self.modules={k:sys.modules.get(k) for k in ('comfy','comfy.model_management')};mm=SimpleNamespace(in_training=False);sys.modules['comfy']=SimpleNamespace(model_management=mm);sys.modules['comfy.model_management']=mm
    def tearDown(self):
        for k,v in self.modules.items():
            if v is None:sys.modules.pop(k,None)
            else:sys.modules[k]=v
        self.tmp.cleanup();self.inf.__exit__(None,None,None)
    def run_sample(self,observe=True,callback=None):
        args=(self.guider,self.sigmas,{'model_options':self.options,'seed':44},callback,self.noise,torch.zeros_like(self.noise),None,True)
        if observe:
            self.fn=LiveObservation(self.spec,'science-sha');return self.fn(self.executor,*args)
        return self.executor(*args)
    def manifest(self):return json.loads((self.root/'observation/live_toy/OBSERVATION.json').read_text())
    def clean_hooks(self):
        for mod in (self.model,self.attn,self.attn.qkv_proj):self.assertEqual(len(mod._forward_hooks),0);self.assertEqual(len(mod._forward_pre_hooks),0)
    def test_real20step50block_capture_returns_original_object(self):
        calls=[];rng=torch.random.get_rng_state().clone();result=self.run_sample(callback=lambda *a:calls.append(a[0]))
        self.assertIs(result,self.executor.result);self.assertEqual(calls,list(range(20)));self.assertTrue(torch.equal(rng,torch.random.get_rng_state()))
        m=self.manifest();self.assertEqual(m['status'],'complete');self.assertEqual(m['actual_model_forward_count'],20);self.assertEqual(m['completed_blocks'],1000)
        for row in m['captures']:
            n=row['step_zero_based'];data=torch.load(row['state_file'],weights_only=True);qk=torch.load(row['qk_file'],weights_only=True)
            self.assertTrue(torch.equal(data['packed_x'],self.model.xs[n]));self.assertTrue(torch.equal(data['raw_packed_x0'],self.model.x0s[n]));self.assertEqual(qk['forward_identity'],row['forward_identity'])
            self.assertEqual(qk['raw_Q_C'].shape,(4,8,56,128))
        self.clean_hooks()
    def test_passive_exact_same_euler_trajectory(self):
        # Save exact weights/noise, execute original sampler with/without observer.
        weights=copy.deepcopy(self.model.state_dict());noise=self.noise.clone();plain=self.run_sample(False).clone();xs=[x.clone() for x in self.model.xs]
        self.tearDown();self.setUp();self.model.load_state_dict(weights);self.noise.copy_(noise)
        observed=self.run_sample();self.assertTrue(torch.equal(plain,observed))
        self.assertTrue(all(torch.equal(a,b) for a,b in zip(xs,self.model.xs)));self.clean_hooks()
    def test_partial_hook_registration_failure_unhooks(self):
        with patch.object(self.attn.qkv_proj,'register_forward_hook',side_effect=OriginalFailure('register failure')):
            with self.assertRaisesRegex(OriginalFailure,'register failure'):self.run_sample()
        self.clean_hooks();self.assertEqual(self.manifest()['status'],'failed')
    def test_model_failure_before_callback9_preserved_and_unhooked(self):
        self.fail_at=9
        with self.assertRaisesRegex(OriginalFailure,'model failure'):self.run_sample()
        self.assertEqual(self.manifest()['status'],'failed');self.clean_hooks()
    def test_capture_save_failure_preserved_and_unhooked(self):
        with patch('observer.torch.save',side_effect=OriginalFailure('disk capture failure')):
            with self.assertRaisesRegex(OriginalFailure,'disk capture failure'):self.run_sample()
        self.assertEqual(self.manifest()['status'],'failed');self.clean_hooks()
    def test_failure_manifest_write_cannot_mask_model_exception(self):
        import observer
        original=observer.atomic;self.fail_at=9
        def write(path,obj):
            if obj['status']=='failed':raise OSError('second disk error')
            return original(path,obj)
        with patch('observer.atomic',write):
            with self.assertRaisesRegex(OriginalFailure,'model failure'):self.run_sample()
        self.clean_hooks()
    def test_original_callback_failure_after_arming_unhooks(self):
        def callback(step,*a):
            if step==8:raise OriginalFailure('callback failure')
        with self.assertRaisesRegex(OriginalFailure,'callback failure'):self.run_sample(callback=callback)
        self.clean_hooks();self.assertEqual(self.manifest()['status'],'failed')
    def test_global_weak_same_observation_lifecycle(self):
        self.state.mode='mass_preserve';self.state.alpha=.25;self.state.active_steps=tuple(range(20))
        self.spec['method']='global_weak';self.spec['router'].update(mode='mass_preserve',alpha=.25,active_steps=list(range(20)))
        self.run_sample();self.assertEqual(self.manifest()['completed_blocks'],1000);self.clean_hooks()
    def test_noise_scaling_patch_rejected(self):
        self.base.model_sampling.noise_scale=2
        with self.assertRaises(ValueError):self.run_sample()
        self.assertEqual(self.model.calls,0)
    def test_noise_changed_rejected(self):
        self.noise[0,0,0]+=1
        with self.assertRaises(ValueError):self.run_sample()
        self.assertEqual(self.model.calls,0)
    def test_schedule_mode_binding_rejected(self):
        self.state.mode='mass_preserve'
        with self.assertRaises(ValueError):self.run_sample()
    def test_consumed_state_rejected(self):
        self.state.forward_index=1
        with self.assertRaises(ValueError):self.run_sample()
    def test_extra_actual_model_call_rejected(self):
        original=self.base.predict
        def duplicate(*a):original(*a);return original(*a)
        self.base.predict=duplicate
        with self.assertRaisesRegex(ValueError,'count differs'):self.run_sample()
        self.clean_hooks()
    def test_reuse_rejected(self):
        self.run_sample()
        with self.assertRaisesRegex(RuntimeError,'single-trajectory'):self.fn(None,None,None,None,None,None)

if __name__=='__main__':unittest.main()
