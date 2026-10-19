import unittest,tempfile,json,sys,os
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common,decode_reference
import torch
class Tests(unittest.TestCase):
 def test_tensor_accept(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'z.pt';z=torch.arange(24,dtype=torch.float32).reshape(1,2,3,4);torch.save(z,p)
   self.assertTrue(torch.equal(common.load_bound_tensor(p,common.tensor_signature(z)),z))
 def test_tensor_hash_reject(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'z.pt';z=torch.zeros(3);torch.save(z,p);sig=common.tensor_signature(z);sig['sha256']='0'*64
   with self.assertRaisesRegex(ValueError,'signature'):common.load_bound_tensor(p,sig)
 def test_nonfinite_reject(self):
  with self.assertRaisesRegex(ValueError,'finite'):common.tensor_signature(torch.tensor([float('nan')]))
 def test_no_external_normalization(self):
  import inspect
  body=inspect.getsource(decode_reference.main)
  self.assertIn('images=vae.decode(z)',body)
  self.assertNotIn('process_latent_',body)
 def test_fallback_reject(self):
  class Fake:
   def decode_tiled_3d(self):pass
  g=decode_reference.install_fallback_guard(Fake)
  with self.assertRaisesRegex(RuntimeError,'fallback'):Fake().decode_tiled_3d()
  self.assertEqual(g['calls'],1)
 def test_foreign_busy_admitted(self):
  uuid='GPU-test';values=[f'1, {uuid}, 50000, 30000, 55, 99\n','GPU-test, 99999999, 30000\n']
  with patch('subprocess.check_output',side_effect=values):
   r=decode_reference.admission(uuid,16384);self.assertEqual(r['utilization'],99)
 def test_low_memory_rejected(self):
  with patch('subprocess.check_output',return_value='1, GPU-test, 5000, 70000, 55, 99\n'):
   with self.assertRaisesRegex(ValueError,'free VRAM'):decode_reference.admission('GPU-test',16384)
 def test_uuid_mismatch_rejected(self):
  with patch('subprocess.check_output',return_value='1, GPU-other, 50000, 30000, 55, 99\n'):
   with self.assertRaisesRegex(ValueError,'UUID'):decode_reference.admission('GPU-test',16384)
 def test_lossless_source_video(self):
  with tempfile.TemporaryDirectory() as d:
   x=torch.rand(5,32,48,3);r=common.write_frames(x,[0,2,4],8,Path(d)/'test.mp4',__import__('shutil').which('ffmpeg'))
   self.assertEqual(r['frames'],3);self.assertTrue(r['lossless_pixel_verified'])
if __name__=='__main__':unittest.main()
