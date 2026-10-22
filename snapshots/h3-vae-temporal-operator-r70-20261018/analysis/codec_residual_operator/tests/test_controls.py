import copy
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import compensation
import run_codec
import operators

torch.set_num_threads(2)

class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config,cls.z,cls.encoded,cls.coords=run_codec.inputs()
    def test_1_identity_bitwise_including_negative_zero(self):
        z=self.z.clone();z.reshape(-1)[0]=-0.0
        for mode in ['anchor','transport']:
            out=compensation.apply(z,self.encoded['identity'],self.encoded['identity'],self.coords['identity'],mode)
            self.assertTrue(torch.equal(out.view(torch.uint8),z.view(torch.uint8)))
    def test_2_shape_dtype_finite_guards(self):
        for value in [self.z[:,:,:46],self.z.double(),torch.full_like(self.z,float('nan'))]:
            with self.assertRaises(ValueError):compensation.apply(value,self.encoded['identity'],self.encoded['shift3'],self.coords['shift3'],'anchor')
    def test_3_exact_registered_formulas(self):
        for name in ['shift3','offline_mapping']:
            e=self.encoded[name];eid=self.encoded['identity'];positions=self.coords[name]['latent_positions']
            a=compensation.apply(self.z,eid,e,self.coords[name],'anchor')
            b=compensation.apply(self.z,eid,e,self.coords[name],'transport')
            self.assertTrue(torch.equal(a,self.z+(e-eid)))
            self.assertTrue(torch.equal(b,operators.interpolate(self.z,positions,2)+(e-operators.interpolate(eid,positions,2))))
    def test_4_same_coordinates_direction_and_endpoints(self):
        x=json.loads((compensation.PARENT/'inputs/OFFLINE_DEVELOPMENT_MAPPING.json').read_text())
        maps=operators.make_maps([r['native_index'] for r in x['mapping']])
        for n,v in maps.items():self.assertEqual(self.coords[n],operators.coordinates(v))
        self.assertEqual(maps['shift3'][0],3)
        self.assertEqual(maps['shift3'][100],103)
        self.assertTrue(np.array_equal(maps['offline_mapping'][144:],np.arange(144,158)))
        self.assertEqual(len(self.coords['shift3']['output_bin_index']),158)
    def test_5_changed_input_hash_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'input';p.write_bytes(b'original');digest=run_codec.sha(p)
            run_codec.verify_file(p,digest);p.write_bytes(b'changed')
            with self.assertRaises(ValueError):run_codec.verify_file(p,digest)
    def test_6_actual_same_x0_and_original_encoded_outputs(self):
        self.assertEqual(run_codec.tensor_signature(self.z)['sha256'],self.config['input_x0_raw_sha256'])
        self.assertEqual(self.config['input_x0_raw_sha256'],'33d8d678915e2fccf8b4e9ca2c4b63e737b5b9156639b19df4924121793cc4b6')
        for n,v in self.encoded.items():self.assertEqual(run_codec.tensor_signature(v),self.config['encoded_signatures'][n])
        self.assertEqual(self.config['order'],[[n,a] for n in ['shift3','offline_mapping'] for a in ['anchor','transport']])
        self.assertFalse(torch.cuda.is_initialized())

class RootGate(unittest.TestCase):
    def gate(self,tamper):
        identity={'pid':11,'uid':12,'start_ticks':'13','cmdline_sha256':'a'*64}
        config=json.loads((ROOT/'contract.json').read_text())
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'control'
            def root():
                for _ in range(200):
                    if (path/'ready.json').exists():break
                    time.sleep(.01)
                ready=json.loads((path/'ready.json').read_text())
                if tamper:ready['identity']['start_ticks']='other'
                run_codec.write(path/'go.json',ready)
            task=threading.Thread(target=root);task.start()
            try:
                with mock.patch.object(run_codec.runtime,'process_identity',return_value=identity):
                    if tamper:
                        with self.assertRaises(ValueError):run_codec.root_gate(path,config['gpu_uuid'],config,Path(folder)/'out')
                    else:
                        got=run_codec.root_gate(path,config['gpu_uuid'],config,Path(folder)/'out')
                        self.assertEqual(got['identity'],identity)
            finally:task.join()
    def test_exact_go(self):self.gate(False)
    def test_wrong_identity_go_rejected(self):self.gate(True)

if __name__=='__main__':unittest.main()
