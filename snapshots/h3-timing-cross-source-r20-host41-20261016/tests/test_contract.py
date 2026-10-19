import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'extensions'),str(ROOT/'scripts')]
from preflight import check,read,ARMS,REMOTE,expected_graph
from H3EventAudit import audit_root,H3EventAuditNoise
from H3TemporalRouter import validate_run_contract,core
from H3TemporalRouter.layout import event_latent_range
import service

def dense(q,k,v):
    z=q@k.transpose(-1,-2)/math.sqrt(q.shape[-1]);return z.softmax(-1)@v,z.logsumexp(-1).float()

class Tests(unittest.TestCase):
    def test_static_contract(self):
        self.assertTrue(check(ROOT)['passed'])
        self.assertEqual(event_latent_range(54,69,42),(16,22))
        for run in ARMS:
            g=read(ROOT/'configs'/f'{run}.json')
            with patch.object(Path,'mkdir'):
                self.assertEqual(str(audit_root(g['5']['inputs']['audit_dir'])),REMOTE+'/audit')
                self.assertEqual(len(H3EventAuditNoise().get_noise(**g['6']['inputs'])),1)
            args={k:v for k,v in g['50']['inputs'].items() if k not in ('model','positive')}
            validate_run_contract(**args)
            for key,value in [('end_frame',65),('step_end',20),('mode','hard_route'),('alpha',.5),('run_id','bad')]:
                with self.subTest(key=key),self.assertRaises(ValueError):validate_run_contract(**dict(args,**{key:value}))
        for path in ['/tmp','/data5/researcher/h3_runs/timing_spatial_r3_20261016/audit',REMOTE+'/audit/../../other']:
            with self.assertRaises(ValueError):audit_root(path)

    def test_runtime_admission_stays_fail_closed(self):
        p=read(ROOT/'configs/protocol.json')
        self.assertEqual(str(service.RUN),REMOTE);self.assertEqual(service.PORT,8480)
        self.assertEqual(service.GPU,p['gpu_uuid'])
        self.assertNotIn('H3FeedbackRouter',service.command())
        self.assertNotIn('H3PhaseRoPE',service.command())
        self.assertIn("assert 'H3TemporalRouter' in info",(ROOT/'scripts/launch_remote.py').read_text())
        with patch.object(service.subprocess,'run',side_effect=RuntimeError('CUDA unknown error')):
            with self.assertRaises(RuntimeError):service.gpu_readiness()
        with patch.object(service.subprocess,'run',return_value=type('Result',(),{'stdout':'Problem with GPU 0000:06:00.0: Unknown Error\n','stderr':''})()):
            with self.assertRaises(RuntimeError):service.gpu_readiness()

    def test_schedule_and_math_both_arms(self):
        torch.set_num_threads(1);gen=torch.Generator().manual_seed(20)
        q,k,v=[torch.randn(1,2,29,8,generator=gen) for _ in range(3)]
        before=[x.clone() for x in (q,k,v)]
        plan={'reference_video_segment':[3,15],'query_interval_half_open':[20,26],
              'latent_interval_half_open':[1,3],'frame_rows':3,'seq_len':29}
        route=core.route_attention
        def cpu_route(*a,**kw):return route(*a,**kw,attention=dense)
        def attention_pytorch(*a,**kw):raise AssertionError('only identity supplied')
        layout=object();rng=torch.get_rng_state().clone()
        native=cpu_route(q,k,v,2,plan,mode='native')
        full=cpu_route(q,k,v,2,plan,mode='mass_preserve')
        self.assertTrue(torch.equal(native[:,:20],full[:,:20]))
        self.assertTrue(torch.equal(native[:,26:],full[:,26:]))
        for mode in ('native','mass_preserve'):
            with tempfile.TemporaryDirectory() as folder:
                state=core.RouterState({},mode,1.,0,0,54,69,0,50,6,15,'cpu',folder)
                state.plan_for=lambda _:plan;patches=[core.EventBlockPatch(state,b) for b in range(50)]
                def original(args):return args['transformer_options']['optimized_attention_override'](attention_pytorch,q,k,v,2,skip_reshape=True)
                with patch.object(core,'route_attention',side_effect=cpu_route),patch.object(core,'temporal_readout',return_value={}):
                    for index in range(20):
                        for b in range(50):
                            options={'block_index':b,'minimax_h3_layout':layout,'sample_sigmas':torch.linspace(1,0,21)}
                            got=patches[b]({'layout':layout,'transformer_options':options},{'original_block':original})
                            self.assertTrue(torch.equal(got,full if mode=='mass_preserve' and 6<=index<15 else native))
                            self.assertNotIn('optimized_attention_override',options)
                self.assertEqual(state.audit['completed_forward_calls'],20)
                self.assertEqual(state.audit['completed_calls'],1000)
                self.assertEqual(state.audit['routed_calls'],450 if mode=='mass_preserve' else 0)
                self.assertEqual(state.audit['routed_by_forward'],[0]*6+[50 if mode=='mass_preserve' else 0]*9+[0]*5)
        self.assertTrue(torch.equal(rng,torch.get_rng_state()))
        self.assertTrue(all(torch.equal(a,b) for a,b in zip(before,(q,k,v))))

    def test_positive_alpha_dense_formula(self):
        gen=torch.Generator().manual_seed(21)
        q,k,v=[torch.randn(1,2,29,8,generator=gen,dtype=torch.float64) for _ in range(3)]
        plan={'reference_video_segment':[3,15],'query_interval_half_open':[20,26],
              'latent_interval_half_open':[1,3],'frame_rows':3,'seq_len':29}
        actual=core.route_attention(q,k,v,2,plan,mode='mass_preserve',attention=dense).reshape(1,29,2,8).transpose(1,2)
        o,l=dense(q,k,v);ref,lr=dense(q[:,:,20:26],k[:,:,3:15],v[:,:,3:15])
        expected=o.clone();same=[]
        for local,t in enumerate((1,2)):
            same.append(dense(q[:,:,20+3*local:23+3*local],k[:,:,3+3*t:6+3*t],v[:,:,3+3*t:6+3*t])[0])
        # Production correction accumulates in FP32, so use its declared arithmetic.
        expected[:,:,20:26]=(o[:,:,20:26].float()+(lr.float()-l[:,:,20:26].float()).clamp(max=0).exp().unsqueeze(-1)*(torch.cat(same,2).float()-ref.float())).to(o.dtype)
        torch.testing.assert_close(actual,expected,rtol=0,atol=0)

if __name__=='__main__':unittest.main()
