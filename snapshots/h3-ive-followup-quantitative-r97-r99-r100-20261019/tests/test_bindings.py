import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import common as c
class BindingTests(unittest.TestCase):
 def setUp(self):
  self.base=ROOT/'cases/r97_short0358';self.s=c.read(self.base/'SPEC.json');self.g=c.read(self.base/'inputs/CONTROL_RUNTIME_GATE.json');self.m=c.read(self.base/'INPUTS.json');self.r=c.read(self.base/'tracks/source/REPORT.json')
 def gate(self):c.validate_gate(self.s,self.g)
 def reuse(self):c.validate_reuse(self.s,self.m,self.r,c.sha(self.base/'tracks/source/REPORT.json'),c.sha(self.base/'tracks/source/tracks.npz'))
 def test_actual_gate_accepts(self):self.gate()
 def test_per_run_geometry_keys(self):
  self.g['runs']={'native':{'valid_frames':self.g.pop('valid_frames'),'evaluation_crop_xywh':self.g.pop('evaluation_crop_xywh')}}
  self.s['gate'].update(valid_frame_keys=['runs','native','valid_frames'],crop_keys=['runs','native','evaluation_crop_xywh'])
  self.gate()
 def test_per_run_geometry_rejects_wrong_valid(self):
  self.g['runs']={'native':{'valid_frames':104,'evaluation_crop_xywh':self.g.pop('evaluation_crop_xywh')}};self.g.pop('valid_frames')
  self.s['gate'].update(valid_frame_keys=['runs','native','valid_frames'],crop_keys=['runs','native','evaluation_crop_xywh'])
  with self.assertRaises(ValueError):self.gate()
 def test_failed_gate_rejected(self):
  self.g['passed']=False
  with self.assertRaises(ValueError):self.gate()
 def test_failed_check_rejected(self):
  self.g['checks']['actual_history']=False
  with self.assertRaises(ValueError):self.gate()
 def test_wrong_target_rejected(self):
  self.g['video']['sha256']='0'*64
  with self.assertRaises(ValueError):self.gate()
 def test_wrong_run_rejected(self):
  self.g['run_id']='old_same_named_run'
  with self.assertRaises(ValueError):self.gate()
 def test_wrong_frame_count_rejected(self):
  self.g['valid_frames']=104
  with self.assertRaises(ValueError):self.gate()
 def test_wrong_crop_rejected(self):
  self.g['evaluation_crop_xywh']=[0,0,1280,720]
  with self.assertRaises(ValueError):self.gate()
 def test_actual_source_reuse_accepts(self):self.reuse()
 def test_reuse_wrong_host(self):
  self.r['admission_before_cuda']['hostname']='different'
  with self.assertRaises(ValueError):self.reuse()
 def test_reuse_wrong_torch(self):
  self.r['torch_version']='different'
  with self.assertRaises(ValueError):self.reuse()
 def test_reuse_wrong_grid(self):
  self.r['tracker']['grid_size']=11
  with self.assertRaises(ValueError):self.reuse()
 def test_reuse_wrong_sampling(self):
  self.r['score_frame_indices'][1]=2
  with self.assertRaises(ValueError):self.reuse()
 def test_reuse_wrong_pixels(self):
  self.r['decoded_frame_md5'][1]='0'*32
  with self.assertRaises(ValueError):self.reuse()
 def test_reuse_wrong_file_bytes(self):
  with self.assertRaises(ValueError):c.validate_reuse(self.s,self.m,self.r,'0'*64,c.sha(self.base/'tracks/source/tracks.npz'))
 def test_runtime_exact_parent_bytes(self):c.verify_runtime()
 def test_reject_path_traversal(self):
  with self.assertRaises(ValueError):c.case_root('../elsewhere')
 def test_import_no_torch(self):self.assertNotIn('torch',sys.modules)
if __name__=='__main__':unittest.main()
