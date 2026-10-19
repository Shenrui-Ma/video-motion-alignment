import json
import ast
import math
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from endpoint import Config, EndpointController, Proposal, euler, gain, install, signature
from proposal_math import codec_proposal, local_coordinates, fit_current

torch.set_num_threads(2)
GRAPH = json.loads((ROOT/'configs/R65_PARENT_GRAPH.json').read_text())
SIGMAS = tuple(torch.tensor([float(x) for x in GRAPH['9']['inputs']['sigmas'].split(',')], dtype=torch.float32).tolist())
VIDEO = (1,24,47,48,72)
AUDIO = (1,32,2,263)
TOTAL = math.prod(VIDEO)+math.prod(AUDIO)


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def controller(self, arm='B', provider=None):
        c = Config('test_'+arm, arm, self.temp.name, SIGMAS)
        def default(z, context):
            mask = torch.zeros(47); mask[:11] = 1
            delta = torch.zeros_like(z); delta[:,:,:11] = .2
            return Proposal(delta, mask, context['video']['sha256'])
        return EndpointController(c, provider or default)

    def simulate(self, arm, provider=None):
        control = self.controller(arm, provider)
        control.begin(torch.tensor(SIGMAS))
        x = torch.linspace(-.5,.5,TOTAL).reshape(1,1,TOTAL)
        for i in range(20):
            z = x*.5
            before_x, before_z = signature(x), signature(z)
            result = control({'input':x,'denoised':z,'sigma':torch.tensor([SIGMAS[i]]),'cond_scale':1})
            self.assertEqual(signature(x), before_x)
            self.assertEqual(signature(z), before_z)
            self.assertTrue(torch.equal(result[...,math.prod(VIDEO):].view(torch.uint8), z[...,math.prod(VIDEO):].view(torch.uint8)))
            if arm == 'A' or i != 6:
                self.assertIs(result,z)
            x = euler(x,result,SIGMAS[i],SIGMAS[i+1])
        control.finish(x)
        return control

    def test_actual_shape_abc_twenty_steps_and_x7(self):
        # Save metadata through real JSON; avoid 1+ GiB of repeated temporary PT.
        with patch('endpoint.torch.save'):
            for arm in ('A','B','C'):
                control = self.simulate(arm)
                self.assertEqual(control.report['status'],'complete')
                self.assertEqual(control.report['intervention_steps'],[] if arm=='A' else [6])
                self.assertEqual(control.report['calls'][7]['x7_check']['max_abs'],0)
                self.assertLess(control.report['calls'][6]['proposal']['analytic_increment_max_abs_error'],2e-6)

    def test_gain_matches_real_grid(self):
        self.assertAlmostEqual(gain('C',SIGMAS[6],SIGMAS[7]),4.900008917317525)
        self.assertEqual(gain('A',SIGMAS[6],SIGMAS[7]),0)
        self.assertEqual(gain('B',SIGMAS[6],SIGMAS[7]),1)

    def test_float64_signal_identity(self):
        x,z,d = torch.randn(3,97,dtype=torch.float64)
        s,n = SIGMAS[6:8]; c=(s-n)/s; lam=gain('C',s,n)
        expected=euler(x,z,s,n)+c*lam*d
        self.assertTrue(torch.allclose(euler(x,z+lam*d,s,n),expected,atol=1e-14,rtol=1e-14))
        epsilon=(x-(1-s)*z)/s
        self.assertTrue(torch.allclose(expected,n*epsilon+(1-n)*(z+d),atol=1e-14,rtol=1e-14))

    def test_mask_audio_and_original_inputs(self):
        with patch('endpoint.torch.save'):
            control=self.simulate('B')
        row=control.report['calls'][6]
        self.assertEqual(row['proposal']['mask'][11:],[0.]*36)

    def test_bad_sigma_and_shape_rejected(self):
        control=self.controller(); control.begin(torch.tensor(SIGMAS))
        args={'input':torch.zeros(1,1,3),'denoised':torch.zeros(1,1,3),'sigma':torch.tensor([1.]),'cond_scale':1}
        with self.assertRaisesRegex(ValueError,'shape'):control(args)
        args['input']=args['denoised']=torch.zeros(1,1,TOTAL)
        args['sigma']=torch.tensor([SIGMAS[1]])
        with self.assertRaisesRegex(ValueError,'sigma'):control(args)

    def test_incomplete_and_repeated_begin_rejected(self):
        control=self.controller();control.begin(torch.tensor(SIGMAS))
        with self.assertRaises(ValueError):control.begin(torch.tensor(SIGMAS))
        with self.assertRaises(ValueError):control.finish(torch.zeros(1,1,TOTAL))

    def test_existing_run_report_is_preserved_on_reservation_failure(self):
        directory=Path(self.temp.name)/'test_B';directory.mkdir()
        path=directory/'REPORT.json';path.write_text('preserve existing run')
        control=self.controller()
        try:
            control.begin(torch.tensor(SIGMAS))
        except FileExistsError as error:
            control.fail(error)
        else:self.fail('existing directory accepted')
        self.assertEqual(path.read_text(),'preserve existing run')

    def test_actual_x7_mismatch_is_rejected(self):
        control=self.controller();control.begin(torch.tensor(SIGMAS))
        x=torch.zeros(1,1,TOTAL)
        with patch('endpoint.torch.save'):
            for i in range(7):
                z=x*.5
                result=control({'input':x,'denoised':z,'sigma':torch.tensor([SIGMAS[i]]),'cond_scale':1})
                x=euler(x,result,SIGMAS[i],SIGMAS[i+1])
            x[...,0]+=1
            with self.assertRaisesRegex(ValueError,'observed x7'):
                control({'input':x,'denoised':x*.5,'sigma':torch.tensor([SIGMAS[7]]),'cond_scale':1})

    def test_duplicate_hook_call_rejected(self):
        control=self.controller();control.begin(torch.tensor(SIGMAS))
        x=torch.zeros(1,1,TOTAL)
        args={'input':x,'denoised':x,'sigma':torch.tensor([SIGMAS[0]]),'cond_scale':1}
        control(args)
        with self.assertRaisesRegex(ValueError,'sigma'):control(args)

    def test_proposal_cannot_reference_final_trajectory(self):
        def wrong(z,c):return Proposal(torch.zeros_like(z),torch.zeros(47),c['video']['sha256'],basis='final_video')
        with patch('endpoint.torch.save'),self.assertRaisesRegex(ValueError,'current-x0'):
            self.simulate('B',wrong)

    def test_proposal_sha_mismatch_rejected(self):
        def wrong(z,c):return Proposal(torch.zeros_like(z),torch.zeros(47),'wrong')
        with patch('endpoint.torch.save'),self.assertRaisesRegex(ValueError,'another trajectory'):
            self.simulate('B',wrong)

    def test_provider_cannot_rewrite_actual_context(self):
        def wrong(z,c):
            c['video']['sha256']='forged'
            return Proposal(torch.zeros_like(z),torch.zeros(47),'forged')
        with patch('endpoint.torch.save'),self.assertRaisesRegex(ValueError,'another trajectory'):
            self.simulate('B',wrong)

    def test_out_of_mask_delta_rejected(self):
        def wrong(z,c):return Proposal(torch.ones_like(z),torch.zeros(47),c['video']['sha256'])
        with patch('endpoint.torch.save'),self.assertRaisesRegex(ValueError,'outside declared'):
            self.simulate('B',wrong)

    def test_ineligible_returns_original(self):
        def skipped(z,c):return Proposal(torch.zeros_like(z),torch.zeros(47),c['video']['sha256'],eligible=False)
        with patch('endpoint.torch.save'):
            c=self.simulate('C',skipped)
        self.assertEqual(c.report['intervention_steps'],[])
        self.assertFalse(c.report['calls'][6]['proposal']['eligible'])

    def test_identity_signed_zero_and_padding(self):
        coords,mask=local_coordinates(np.arange(49))
        z=torch.zeros(1,2,47,2,2);z[0,0,0]=-.0
        e=z+.1
        proposal=codec_proposal(z,e,e,coords,mask,{})
        self.assertTrue(torch.equal(proposal.delta,torch.zeros_like(z)))
        self.assertEqual(coords['rgb_positions'][46:],list(map(float,range(46,158))))
        self.assertEqual(mask[13:].tolist(),[0.]*34)

    def test_nonuniform_centers_and_shift_direction(self):
        phi=np.arange(49);phi[2:10]+=1
        coords,mask=local_coordinates(phi)
        self.assertEqual(coords['nominal_bin_centers_rgb_frames'][:6],[0.,2.5,6.5,10.5,14.5,17.])
        self.assertGreater(coords['rgb_positions'][6],6)
        self.assertGreater(coords['latent_positions'][2],2)
        self.assertTrue(np.all(np.diff(coords['rgb_positions'])>=0))

    def test_nonclosed_window_rejected(self):
        phi=np.arange(49);phi[15]=16
        with self.assertRaises(ValueError):local_coordinates(phi)

    def test_transport_formula_exact_and_support(self):
        phi=np.arange(49);phi[2:10]+=1
        coords,mask=local_coordinates(phi)
        z,ei,ep=torch.randn(3,1,2,47,2,2)
        import operators
        expected=(operators.interpolate(z,coords['latent_positions'],2)+(ep-operators.interpolate(ei,coords['latent_positions'],2))-z)*mask.view(1,1,47,1,1)
        actual=codec_proposal(z,ei,ep,coords,mask,{})
        self.assertTrue(torch.equal(actual.delta,expected))
        self.assertTrue(bool((actual.delta[:,:,mask==0]==0).all()))

    def test_current_pose_fitter_reproduces_archived_map(self):
        parent=Path('/Users/researcher/DevProjects/h3-vae-temporal-operator-r70-20261018/analysis/current_x0_phase_fit')
        p=json.loads((parent/'PROTOCOL.json').read_text())
        result=fit_current(json.loads(Path(p['inputs']['source_pose']['file']).read_text()),
                           json.loads(Path(p['inputs']['native_pose']['file']).read_text()))
        expected=json.loads((parent/'RESULT.json').read_text())
        self.assertEqual(result['mapping'],[x['native_index'] for x in expected['mapping']])
        self.assertAlmostEqual(result['cost_sum'],expected['sum_cost'])
        self.assertTrue(result['eligible'])
        _,mask=local_coordinates(result['mapping'])
        self.assertEqual(np.flatnonzero(mask).tolist(),list(range(11)))
        self.assertEqual(mask[9:11].tolist(),[.75,.25])

    def test_actual_euler_source_and_comfy_wrapper(self):
        tree=ast.parse((ROOT/'audit/source_code/sampling.py').read_text())
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('sample_euler','to_d')]
        ns={'torch':torch,'trange':lambda n,**kwargs:range(n),
            'utils':types.SimpleNamespace(append_dims=lambda x,n:x.reshape(x.shape+(1,)*(n-x.ndim)))}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'pinned_sample_euler','exec'),ns)
        class Patcher:
            def __init__(self):self.model_options={};self.wrappers={}
            def get_wrappers(self,kind,key):return self.wrappers.get((kind,key),[])
            def clone(self):return Patcher()
            def set_model_sampler_post_cfg_function(self,fn):self.model_options['sampler_post_cfg_function']=[fn]
            def add_wrapper_with_key(self,kind,key,fn):self.wrappers[(kind,key)]=fn
        c=Config('wrapper_C','C',self.temp.name,SIGMAS)
        def provider(z,context):
            delta=torch.zeros_like(z);delta[:,:,:10]=.1
            mask=torch.zeros(47);mask[:10]=1
            return Proposal(delta,mask,context['video']['sha256'])
        extension=types.ModuleType('comfy.patcher_extension')
        extension.WrappersMP=types.SimpleNamespace(SAMPLER_SAMPLE='sample')
        with patch.dict(sys.modules,{'comfy':types.ModuleType('comfy'),'comfy.patcher_extension':extension}):
            model,control=install(Patcher(),c,provider)
            with self.assertRaisesRegex(ValueError,'other post-CFG'):install(model,c,provider)
        inner=types.SimpleNamespace(latent_shapes=[VIDEO,AUDIO],audio_scale=lambda:4,
                                    latent_format=types.SimpleNamespace(scale_factor=1))
        def executor(model_wrap,sigmas,extra_args,callback,noise,*args):
            def predict(x,sigma,**kwargs):
                return control({'input':x,'denoised':x*.5,'sigma':sigma,'cond_scale':1})
            return ns['sample_euler'](predict,noise,sigmas,callback=callback,disable=True)
        executor.class_obj=types.SimpleNamespace(sampler_function=ns['sample_euler'],extra_options={})
        wrapper=model.wrappers[('sample','R77/single_endpoint')]
        with patch('endpoint.torch.save'):
            result=wrapper(executor,types.SimpleNamespace(inner_model=inner),torch.tensor(SIGMAS),{},None,
                           torch.zeros(1,1,TOTAL))
        self.assertEqual(control.report['status'],'complete')
        self.assertEqual(control.report['calls'][7]['x7_check']['max_abs'],0)
        self.assertEqual(control.report['intervention_steps'],[6])
        self.assertEqual(tuple(result.shape),(1,1,TOTAL))


if __name__=='__main__':unittest.main(verbosity=2)
