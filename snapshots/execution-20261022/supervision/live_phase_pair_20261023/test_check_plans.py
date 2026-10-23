import unittest,json,copy,hashlib
from pathlib import Path
from check_plans import verify
P=Path(__file__).resolve().parents[2]/'innovation/signed_phase_calibration_20261023/replay_live_pair/plans'
class Check(unittest.TestCase):
 def setUp(self):
  self.cb=(P/'native_contract.json').read_bytes();self.c=json.loads(self.cb);self.g=json.loads((P/'native_graph.json').read_text())
 def test_good(self):self.assertTrue(verify(self.g,self.c,'native',self.cb))
 def test_old_writer_path_rejected(self):
  self.g['50']['inputs']['audit_dir']='/old/audit'
  with self.assertRaises(AssertionError):verify(self.g,self.c,'native',self.cb)
 def test_old_output_identity_rejected(self):
  self.g['14']['inputs']['filename_prefix']='old_video'
  with self.assertRaises(AssertionError):verify(self.g,self.c,'native',self.cb)
 def test_extra_vae_node_rejected(self):
  self.g['777']={'class_type':'H3X0Readout','inputs':{}}
  with self.assertRaises(AssertionError):verify(self.g,self.c,'native',self.cb)
 def test_stale_contract_rejected(self):
  self.g['52']['inputs']['contract_sha256']='0'*64
  with self.assertRaises(AssertionError):verify(self.g,self.c,'native',self.cb)
 def test_midstep_vae_rejected(self):
  self.g['11']['inputs']['samples']=['52',0]
  with self.assertRaises(AssertionError):verify(self.g,self.c,'native',self.cb)
if __name__=='__main__':unittest.main()
