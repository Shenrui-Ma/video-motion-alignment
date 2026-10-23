import copy,json,tempfile,unittest,sys
from pathlib import Path
from types import SimpleNamespace
import torch
from one_forward import HistoricalOneForward,arm_router_options,verify_pair
from reconstruct import tensor_info,file_sha,pack
from source_oracles import actual_sampler_classes,actual_attention_and_layout

torch.set_num_threads(1);torch.set_grad_enabled(False)

class FrozenState:
    def __init__(self,mode='native'):
        self.forward_index=-1;self.next_block=0;self.mode=mode;self.alpha=.25;self.active_steps=tuple(range(20))
        self.audit={'started_calls':0,'completed_calls':0,'completed_forward_calls':0,'calls_by_forward':[],'routed_by_forward':[]}

class OneForwardTests(unittest.TestCase):
    def setUp(self):
        self.inference=torch.inference_mode();self.inference.__enter__()
        torch.manual_seed(53);self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.actual=actual_sampler_classes();h3=actual_attention_and_layout()
        self.shapes=[[1,24,4,4,8],[1,32,2,5]];self.noise=pack([torch.randn(s) for s in self.shapes]);self.sigmas=torch.linspace(1,0,21)
        self.x=self.noise*.93;self.rawold=self.noise*.42;v,a=self.rawold.split([3072,320],-1)
        self.old={'video':v.reshape(self.shapes[0]),'audio':a.reshape(self.shapes[1])/4,'metadata':{'step_zero_based':9,'seed':44}}
        torch.save(self.old,self.root/'old.pt')
        state={'step_zero_based':9,'historical_x0_file_sha256':file_sha(self.root/'old.pt'),'manifest_sha256':'historical-manifest','packed_x':self.x,'noise_sha256':tensor_info(self.noise)['sha256'],'shapes':self.shapes,'sigmas_video':self.sigmas.double().tolist()}
        torch.save(state,self.root/'state.pt')
        self.router=FrozenState();self.options={'transformer_options':{'sample_sigmas':self.sigmas,'patches_replace':{'dit':{('double_block',i):SimpleNamespace(state=self.router,block_index=i) for i in range(50)}}}}
        refs=[dict(kind='video',latent_t=4,latent_h=4,latent_w=8,ref_audio_t=0)]
        self.layout=h3['PackedLayout'](3,4,4,8,5,refs=refs)
        attn=h3['Attention'](16,56,128,1e-5,operations=torch.nn).eval()
        rope=h3['rope_rotation_table'](torch.randn(self.layout.seq_len,96)*.01,torch.float32)
        ms=self.actual['CONST']();ms.noise_scale=1.
        base=SimpleNamespace(latent_shapes=self.shapes,audio_scale=lambda:4.,model_sampling=ms,
                             diffusion_model=SimpleNamespace(blocks=[SimpleNamespace(attn=attn) for _ in range(50)]))
        def predict(x,sigma,model_options,seed):
            state=model_options['transformer_options']['patches_replace']['dit'][('double_block',0)].state
            state.forward_index+=1
            state.audit['calls_by_forward'].append(0);state.audit['routed_by_forward'].append(0)
            out=attn(x.reshape(-1)[:self.layout.seq_len*16].reshape(self.layout.seq_len,16),rope)
            state.audit['started_calls']+=50;state.audit['completed_calls']+=50;state.audit['completed_forward_calls']+=1
            state.audit['calls_by_forward'][state.forward_index]=50
            return x-sigma.view(1,1,1)*out.float().mean()
        base.predict=predict
        patcher=SimpleNamespace(model_options=self.options)
        self.guider=self.actual['CFGGuider'](patcher);self.guider.inner_model=base;self.guider.conds={'positive':[{'model_conds':{'minimax_payload':SimpleNamespace(cond={'layout':self.layout,'audio_scale':4,'seed':44})}}]}
        self.saved_modules={k:sys.modules.get(k) for k in ('comfy','comfy.model_management')}
        mm=SimpleNamespace(in_training=False);sys.modules['comfy']=SimpleNamespace(model_management=mm);sys.modules['comfy.model_management']=mm
    def tearDown(self):
        for k,v in self.saved_modules.items():
            if v is None:sys.modules.pop(k,None)
            else:sys.modules[k]=v
        self.tmp.cleanup();self.inference.__exit__(None,None,None)
    def run_actual_sampler(self,on,label,method='native'):
        fn=HistoricalOneForward(self.root/'state.pt',file_sha(self.root/'state.pt'),self.root/'old.pt',file_sha(self.root/'old.pt'),self.root/label,capture_on=on,valid_frames=13,expected_method=method)
        sampler=self.actual['KSAMPLER'](fn)
        # This actual KSAMPLER constructs/passes k_callback even though None below.
        result=sampler.sample(self.guider,self.sigmas,{'model_options':self.options,'seed':44},None,self.noise,torch.zeros_like(self.noise),None,True)
        return fn,result
    def test_actual_KSAMPLER_CFG_predict_two_finite_forwards(self):
        off,a=self.run_actual_sampler(False,'off');on,b=self.run_actual_sampler(True,'on')
        self.assertTrue(torch.equal(a,b));self.assertEqual(off.calls,1);self.assertEqual(on.calls,1)
        self.assertEqual(on.record['step_zero_based'],9);self.assertTrue((self.root/'on/qk.pt').exists())
        self.assertEqual(self.router.forward_index,-1);self.assertEqual(self.router.audit['started_calls'],0)
        data=torch.load(self.root/'on/qk.pt',weights_only=True)
        self.assertEqual(data['raw_Q_C'].shape,(4,8,56,128))
        self.assertEqual(data['physical_frame_spans_inclusive'],[[0,0],[1,4],[5,8],[9,12]])
    def test_actual_router_method_binding(self):
        with self.assertRaises(ValueError):self.run_actual_sampler(False,'wrong',method='global_weak')
    def test_actual_old_step_cannot_be_silently_zero(self):
        opts,state=arm_router_options(self.options,19,self.root)
        self.assertEqual(state.forward_index,18);self.assertEqual(len(state.audit['calls_by_forward']),19)
        self.assertTrue(state.audit['replay']['leading_zero_counters_are_skipped_not_executed'])
    def test_consumed_router_rejected(self):
        self.router.forward_index=0
        with self.assertRaises(ValueError):arm_router_options(self.options,9,self.root)
    def test_bad_noise_identity(self):
        self.noise[0,0,0]+=1
        with self.assertRaises(ValueError):self.run_actual_sampler(False,'badnoise')
    def test_full_schedule_must_survive(self):
        self.sigmas[4]-=.001
        with self.assertRaises(ValueError):self.run_actual_sampler(False,'badsigma')
    def test_second_sampler_call_rejected(self):
        fn,_=self.run_actual_sampler(False,'once')
        with self.assertRaises(RuntimeError):fn(None,None,None)
    def test_passive_and_historical_gate(self):
        old={k:torch.randn(1,2,3) for k in ('video','audio')}
        self.assertTrue(verify_pair(old,old,old)['passed'])
        changed={k:v.clone() for k,v in old.items()};changed['video'][0,0,0]+=1e-7
        self.assertFalse(verify_pair(old,changed,old)['passed'])
    def test_historical_mismatch_is_not_endpoint_excused(self):
        old={k:torch.randn(1,2,3) for k in ('video','audio')};bad={k:v+.1 for k,v in old.items()}
        gate=verify_pair(bad,bad,old)
        self.assertFalse(gate['passed']);self.assertTrue(gate['streams']['video']['hook_exact_equal'])
    def test_nonfinite_gate_fails(self):
        old={k:torch.ones(1,2,3) for k in ('video','audio')};old['audio'][0,0,0]=float('nan')
        with self.assertRaises(ValueError):verify_pair(old,old,old)

if __name__=='__main__':unittest.main()
