import copy
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from compare import frame_error, release_gate, NAMES


class ConsumerTests(unittest.TestCase):
    def pair(self):
        identity={'pid':123,'uid':456,'start_ticks':'789','cmdline_sha256':'abc'}
        result={'status':'complete','pid':123,'uid':456,'root_gate':{'identity':identity},
                'model_forward_calls':0,'vae_encode_calls':0,'vae_decode_calls':4,'fallback_guard':{'calls':0},
                'products':dict.fromkeys(NAMES,{}),'operations':[{'name':n,'kind':'decode'} for n in NAMES]}
        receipt={'passed':True,'pid':123,'process_absent':True,'CUDA_allocation_absent':True,'identity':copy.deepcopy(identity)}
        return result,receipt

    def test_complete(self):
        release_gate(*self.pair())

    def test_waiting_or_failed_rejected(self):
        for status in ['running','failed','failed_cleanup']:
            r,x=self.pair();r['status']=status
            with self.assertRaises(RuntimeError):release_gate(r,x)

    def test_wrong_identity_rejected(self):
        for field in ['pid','uid','start_ticks','cmdline_sha256']:
            r,x=self.pair();x['identity'][field]='wrong'
            with self.assertRaises(RuntimeError):release_gate(r,x)

    def test_cuda_allocation_rejected(self):
        r,x=self.pair();x['CUDA_allocation_absent']=False
        with self.assertRaises(RuntimeError):release_gate(r,x)

    def test_unexpected_encode_or_fallback_rejected(self):
        r,x=self.pair();r['vae_encode_calls']=1
        with self.assertRaises(RuntimeError):release_gate(r,x)
        r,x=self.pair();r['fallback_guard']['calls']=1
        with self.assertRaises(RuntimeError):release_gate(r,x)

    def test_rgb8_unsigned_subtraction(self):
        a=np.array([0,255,50],dtype=np.uint8);b=np.array([255,0,100],dtype=np.uint8)
        self.assertEqual(frame_error(a,b),560/765)
        self.assertEqual(frame_error(a,a),0)

    def test_rgb8_full_range(self):
        self.assertEqual(frame_error(np.zeros((2,3),np.uint8),np.full((2,3),255,np.uint8)),1)

    def test_float_mix_rejected(self):
        with self.assertRaises(RuntimeError):frame_error(np.zeros(3,np.float32),np.zeros(3,np.uint8))


if __name__=='__main__':unittest.main()
