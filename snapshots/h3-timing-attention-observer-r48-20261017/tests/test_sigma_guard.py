import copy,json,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'extensions'),str(ROOT/'scripts')]
import H3AttentionStateProbe as node
from H3AttentionStateProbe.sigma_guard import (tensor_record,official_head_sigma,timestep_evidence,
    head_evidence,check_timestep,check_head)
from verify_completed import validate_sigma_path


def fixture():
    grid=torch.tensor(json.loads((ROOT/'configs/sources.json').read_text())['bad']['full_grid'],dtype=torch.float32)
    entry=grid[4].reshape(1).clone();sampling=types.SimpleNamespace(timestep=lambda x:x*1000)
    timestep=sampling.timestep(entry).float();head=official_head_sigma(timestep)
    ev,_=timestep_evidence(entry,timestep,sampling);hv,_=head_evidence(head,timestep,grid,(12.,3.));ev.update(hv)
    return entry,timestep,head,grid,sampling,ev


class SigmaTests(unittest.TestCase):
    def test_exact_mapping_and_readonly(self):
        entry,t,h,g,s,e=fixture();before=[x.clone() for x in [entry,t,h,g]];rng=torch.random.get_rng_state().clone()
        check_timestep(entry,t,s.timestep(entry).float(),g.tolist());check_head(h,official_head_sigma(t),g,(12.,3.),g.tolist(),e)
        validate_sigma_path({'sigma_path':e},{'full_grid':g.tolist()})
        self.assertTrue(all(torch.equal(x,y) for x,y in zip([entry,t,h,g],before)))
        self.assertTrue(torch.equal(rng,torch.random.get_rng_state()))

    def test_reciprocal_one_ulp_candidate_is_not_accepted_as_official_cpu(self):
        entry,t,h,g,s,e=fixture();candidate=(t.flatten()[0]*0.001).float().clamp(min=1e-6)
        self.assertEqual(abs(int(candidate.view(torch.int32))-int(h.view(torch.int32))),1)
        evidence,expected=head_evidence(candidate,t,g,(12.,3.))
        with self.assertRaisesRegex(ValueError,'same-device timestep path'):
            check_head(candidate,expected,g,(12.,3.),g.tolist(),evidence)
        self.assertFalse(evidence['exact_official_head_sigma'])

    def test_device_mapping_not_cpu_grid_equality(self):
        entry,t,h,g,s,e=fixture();mapped=torch.nextafter(h,torch.tensor(float('inf')))
        # Simulate an official device result one ULP from entry. Not evidence that
        # CUDA actually does this. A wrong value is rejected by the prior test.
        with patch('H3AttentionStateProbe.sigma_guard.official_head_sigma',return_value=mapped):
            evidence,expected=head_evidence(mapped,t,g,(12.,3.))
        check_head(mapped,expected,g,(12.,3.),g.tolist(),evidence)
        self.assertNotEqual(float(mapped),float(entry[0]));self.assertEqual(evidence['actual_index'],4)

    def test_wrong_timestep_grid_index_shift_and_dtype_rejected(self):
        entry,t,h,g,s,e=fixture()
        for wrong in [torch.nextafter(t,torch.full_like(t,float('inf'))),t.double(),t.reshape(())]:
            with self.assertRaises(ValueError):check_timestep(entry,wrong,t,g.tolist())
        for head,grid,shifts in [(g[5],g,(12,3)),(h,g+0.01,(12,3)),(h,g,(11,3)),(h.double(),g,(12,3))]:
            ev,expected=head_evidence(head,t,grid,shifts)
            with self.assertRaises(ValueError):check_head(head,expected,grid,shifts,g.tolist(),ev)

    def test_nonfinite_record_is_json_and_never_accepted(self):
        entry,t,h,g,s,e=fixture();bad=torch.tensor(float('nan'))
        ev,expected=head_evidence(bad,t,g,(12,3));json.dumps(ev,allow_nan=False)
        self.assertEqual(ev['actual_head_sigma']['values'],[None])
        with self.assertRaises(ValueError):check_head(bad,expected,g,(12,3),g.tolist(),ev)

    def test_wrong_device_skips_index_arithmetic_before_logging(self):
        entry,t,h,g,s,e=fixture()
        # Meta fixture needs no CUDA and would fail immediately on data arithmetic.
        wrong_device=torch.empty((),device='meta',dtype=torch.float32)
        with patch('H3AttentionStateProbe.sigma_guard.tensor_record',side_effect=lambda v:{'device':str(v.device)}):
            ev,_=head_evidence(wrong_device,t,g,(12,3))
        self.assertIsNone(ev['actual_index'])
        self.assertEqual(ev['actual_head_sigma']['device'],'meta')
        self.assertFalse(ev['exact_official_head_sigma'])

    def test_serialized_mapping_corruption_rejected(self):
        *_,g,s,e=fixture()
        for key,change in [('actual_head_sigma',lambda r:r['raw_bits_hex'].__setitem__(0,'00000000')),
                           ('actual_timestep',lambda r:r['device'].__class__)]:
            broken=copy.deepcopy(e)
            if key=='actual_timestep':broken[key]['device']='cuda:1'
            else:change(broken[key])
            with self.assertRaises(ValueError):validate_sigma_path({'sigma_path':broken},{'full_grid':g.tolist()})

    def test_hooks_failure_logs_and_restores(self):
        entry,t,h,g,s,e=fixture()
        for fault in ['none','timestep','head','grid','shifts','register']:
            with self.subTest(fault=fault):
                final=torch.nn.Module();final.forward=lambda *args:args[0]
                diffusion=torch.nn.Module();diffusion.final_layer=final
                def forward(x,timestep):
                    hs=official_head_sigma(timestep)
                    if fault=='head':hs=torch.nextafter(hs,torch.full_like(hs,float('inf')))
                    return final(x,x,(),(),hs,g+0.01 if fault=='grid' else g,(12,4) if fault=='shifts' else (12,3))
                diffusion.forward=forward
                model=types.SimpleNamespace(diffusion_model=diffusion,model_sampling=s,extra_conds=lambda **kw:{})
                saved=model.extra_conds;records=[]
                state=types.SimpleNamespace(active=True,entry_sigma=entry,source=types.SimpleNamespace(s={'full_grid':g.tolist()}),
                    audit={},extra_conds_calls=0,output_head_calls=0)
                state.write=lambda:records.append(copy.deepcopy(state.audit))
                try:
                    with patch.object(node,'output_head_contract',return_value={}), \
                         patch.object(final,'register_forward_pre_hook',side_effect=RuntimeError('intentional registration failure')) if fault=='register' else patch.object(node,'output_head_contract',return_value={}):
                        with node.ModelAudit(model,state):diffusion(torch.zeros(1),t+1 if fault=='timestep' else t)
                    self.assertEqual(fault,'none')
                except (ValueError,RuntimeError):self.assertNotEqual(fault,'none')
                self.assertIs(model.extra_conds,saved)
                self.assertFalse(diffusion._forward_pre_hooks);self.assertFalse(final._forward_pre_hooks)
                if fault!='register':self.assertIn('actual_timestep',records[0]['sigma_path'])
                if fault in ['head','grid','shifts']:
                    self.assertIn('actual_head_sigma',records[-1]['sigma_path'])


if __name__=='__main__':unittest.main()
