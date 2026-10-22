import copy
import unittest
from verify_result import groups, reduced, validate_release, EXPECTED_PRODUCTS

class VerifyTests(unittest.TestCase):
    def test_common_mask_includes_all_three_domains(self):
        c={k:[True]*158 for k in ['rgb_full_domain_valid','observed147_valid','output_bin_latent_domain_valid']}
        c.update(cross17_rgb=[False]*158,decoder_overlap_first5=[False]*158)
        for i,k in enumerate(['rgb_full_domain_valid','observed147_valid','output_bin_latent_domain_valid']):c[k][i]=False
        masks=groups(c)
        self.assertEqual(sum(masks['common_valid147']),155)
        self.assertEqual(sum(masks['invalid_or_padding']),3)
        self.assertEqual(reduced([1.0]*158,masks['common_valid147']),{'frames':155,'mean_absolute_rgb_error':1.0})
        self.assertEqual(reduced([1.0]*158,masks['cross17_common_valid147']),{'frames':0,'mean_absolute_rgb_error':None})
    def test_exit_and_success_required(self):
        r={'pid':7,'status':'complete','vae_encode_calls':3,'vae_decode_calls':6,'model_forward_calls':0,'fallback_guard':{'calls':0},'operations':[{}]*9,'products':dict.fromkeys(EXPECTED_PRODUCTS)}
        p={'pid':7,'passed':True,'process_absent':True,'CUDA_allocation_absent':True}
        validate_release(r,p)
        for k in ['passed','process_absent','CUDA_allocation_absent']:
            bad=copy.deepcopy(p);bad[k]=False
            with self.assertRaises(AssertionError):validate_release(r,bad)
        bad=copy.deepcopy(p);bad['pid']=8
        with self.assertRaises(AssertionError):validate_release(r,bad)
        r['fallback_guard']['calls']=1
        with self.assertRaises(AssertionError):validate_release(r,p)

if __name__=='__main__':unittest.main()
