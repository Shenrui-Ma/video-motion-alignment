import copy,unittest
import torch
from diagnose import reapply,materialized,inverse_matrix,diagnose,eager_functions
torch.set_num_threads(1)

def fixture(dtype=torch.bfloat16):
    torch.manual_seed(23);t,p,h,d,rot=5,8,3,128,96
    angle=torch.randn(1,t*p,1,rot//2)
    rope=torch.stack((angle.cos(),-angle.sin(),angle.sin(),angle.cos()),-1).reshape(1,t*p,1,rot//2,2,2).to(dtype)
    q=torch.randn(d).to(dtype);k=torch.randn(d).to(dtype)
    data={'rot_dim':rot,'q_norm_weight':q,'k_norm_weight':k,'q_norm_eps':1e-5,'k_norm_eps':1e-5,'rope_canvas':rope,'rope_reference':rope.clone()}
    for name in ('Q_C','Q_R','K_R'):
        raw=(torch.randn(t,p,h,d)*3).to(dtype);w=k if name=='K_R' else q
        data['raw_'+name]=raw;data['actual_'+name]=reapply(raw,w,rope,1e-5,rot)
    return data

class DiagnoseTests(unittest.TestCase):
    def test_literal_eager_oracle_exact_all_heads(self):
        r=diagnose(fixture(),strict_geometry=False);self.assertTrue(r['numerical_definition_pass'])
        self.assertTrue(all(x['exact_fraction']==1 for b in r['branches'].values() for x in b['full']))
    def test_fp32_weight_final_inplace_copy_cast(self):
        x=fixture();raw=x['raw_Q_C'];weight=x['q_norm_weight'].float();t,p,h,d=raw.shape
        out=eager_functions()['_rms_rope1'](raw.reshape(1,t*p,h,d),x['rope_canvas'],weight,1e-5,split_half=True,rot_dim=96)
        actual=raw.clone();actual.copy_(out.reshape_as(raw))
        pred=reapply(raw,weight,x['rope_canvas'],1e-5,96)
        self.assertEqual(pred.dtype,torch.bfloat16);self.assertTrue(torch.equal(pred,actual))
    def test_bfloat_rounding_tail_and_inverse(self):
        x=fixture();r=diagnose(x,strict_geometry=False)
        raw=x['raw_Q_C'];m=materialized(raw,x['q_norm_weight'],1e-5)
        self.assertEqual(m.dtype,torch.bfloat16);self.assertTrue(torch.equal(m[...,96:],x['actual_Q_C'][...,96:]))
        inv=inverse_matrix(x['actual_Q_C'],x['rope_canvas'],96)
        self.assertFalse(torch.equal(inv[...,:96],m[...,:96].double()))
        self.assertLess(max(a['nrmse'] for a in r['branches']['Q_C']['inverse_to_materialized_pre_rope_norm']),.01)
    def test_wrong_rope_detected_without_changing_gate(self):
        x=fixture();x['rope_canvas']=x['rope_canvas'].roll(1,1)
        r=diagnose(x,strict_geometry=False);self.assertFalse(r['numerical_definition_pass']);self.assertTrue(r['historical_replay_release_unchanged'])
    def test_wrong_norm_weight_detected(self):
        x=fixture();x['q_norm_weight']=-x['q_norm_weight']
        self.assertFalse(diagnose(x,strict_geometry=False)['numerical_definition_pass'])
    def test_nonfinite_fails_closed(self):
        for key in ('raw_Q_C','actual_K_R','rope_reference','q_norm_weight'):
            x=fixture();x[key].flatten()[0]=float('nan')
            with self.assertRaises(ValueError):diagnose(x,strict_geometry=False)
    def test_different_dtype_holds_even_if_exact(self):
        self.assertFalse(diagnose(fixture(torch.float32),strict_geometry=False)['numerical_definition_pass'])
    def test_production_geometry_is_pinned(self):
        with self.assertRaises(ValueError):diagnose(fixture())
    def test_singular_rotation_rejected(self):
        x=fixture();x['rope_canvas'].zero_()
        with self.assertRaises(ValueError):diagnose(x,strict_geometry=False)

if __name__=='__main__':unittest.main()
