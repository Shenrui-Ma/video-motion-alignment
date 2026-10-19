import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import spatial_smoke_gate as s
class SmokeEvidence(unittest.TestCase):
 def values(self):
  case={'passed':True,'checks':{'native':True},'actual_shape':False}
  actual=dict(case,actual_shape=True,shape=[1,56,96281,128],plan={'reference_video_segment':[7113,51434],'query_interval_half_open':[51960,92509],'latent_interval_half_open':[0,43],'frame_rows':943,'seq_len':96281})
  return {'schema':'r111-spatial-marginal-smoke-v1','passed':True,'torch':'2.11.0+cu130','cuda':'13.0','core_sha256':'digest','script_sha256':'digest','cases':[copy.deepcopy(case),copy.deepcopy(case),actual]}, {'passed':True,'process_absent':True,'CUDA_allocation_absent':True,'exit_code':0,'result_sha256':'digest','owner':{'uid':1004},'gpu_uuid':'testGPU'}
 def verify(self,r,release):
  def read(p):
   if p.name=='GPU_SMOKE_RESULT.json':return r
   if p.name=='GPU_SMOKE_RELEASE.json':return release
   if p.name=='runtime.json':return {'gpu_uuid':'testGPU'}
   raise AssertionError(p)
  with patch.object(s,'read',side_effect=read),patch.object(s,'sha',return_value='digest'):return s.verify(ROOT)
 def test_actual_matching_result_admitted(self):self.assertTrue(self.verify(*self.values())['passed'])
 def test_shape_padding_or_steps_cannot_drift(self):
  for key,value in [('shape',[1,56,87592,128]),('plan',{'reference_video_segment':[3,35]})]:
   a,b=self.values();a['cases'][2][key]=value
   with self.assertRaises(ValueError):self.verify(a,b)
 def test_runtime_and_code_must_match(self):
  for key in ('torch','cuda','core_sha256','script_sha256'):
   a,b=self.values();a[key]='changed'
   with self.assertRaises(ValueError):self.verify(a,b)
 def test_actual_test_failures_rejected(self):
  for i in range(3):
   a,b=self.values();a['cases'][i]['checks']['native']=False
   with self.assertRaises(ValueError):self.verify(a,b)
 def test_release_must_bind_actual_result(self):
  for key,value in [('process_absent',False),('CUDA_allocation_absent',False),('exit_code',1),('result_sha256','changed'),('gpu_uuid','different')]:
   a,b=self.values();b[key]=value
   with self.assertRaises(ValueError):self.verify(a,b)
 def test_one_new_graph_operator_only(self):
  a=json.loads((ROOT/'design/R107_GRAPH.json').read_text());b=json.loads((ROOT/'configs/graphs/r111_long_0174_seed2026101701_forced.json').read_text())
  # Rename task namespace only; values outside these provenance fields stay exact.
  for node,key in [('5','run_id'),('6','run_id'),('6','pair_id'),('14','filename_prefix'),('50','run_id'),('51','run_id'),('51','source_run_id'),('52','run_id'),('5','audit_dir'),('6','audit_dir'),('50','audit_dir'),('51','source_audit_dir'),('52','output_dir')]:
   b[node]['inputs'][key]=a[node]['inputs'][key]
  self.assertEqual(a['50']['inputs']['mode'],'mass_preserve');self.assertEqual(b['50']['inputs']['mode'],'spatial_marginal')
  b['50']['inputs']['mode']=a['50']['inputs']['mode'];self.assertEqual(a,b)
if __name__=='__main__':unittest.main()
