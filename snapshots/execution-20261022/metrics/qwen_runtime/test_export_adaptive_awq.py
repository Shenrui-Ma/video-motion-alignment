import unittest
from export_adaptive_awq import validate_score
class ScoreExportTest(unittest.TestCase):
 def setUp(self):
  self.job={'id':'x','task_id':'task','method':'native','sha256':'abc','valid_frames':10,'crop_xywh':[0,0,10,10]}
  self.prepared={'sha256':'abc','frames':10,'crop_xywh':[0,0,10,10]}
  self.record={'source_file':'/result.json','source_sha256':'rawsha','value':{'status':'done','job_id':'x','task_id':'task','method':'native','score':5.0,'evaluator':{'configuration_id':'actual-awq'}}}
 def test_valid(self):
  x=validate_score(self.record,self.job,self.prepared,'abc');self.assertEqual(x['status'],'done');self.assertEqual(x['configuration_id'],'actual-awq');self.assertEqual(x['original_result_file_sha256'],'rawsha')
 def test_input_mismatch(self):
  self.assertEqual(validate_score(self.record,self.job,self.prepared,'different')['status'],'invalid_input')
 def test_prepared_mismatch(self):
  self.prepared['sha256']='different';self.assertIsNone(validate_score(self.record,self.job,self.prepared)['score'])
 def test_wrong_mapping(self):
  self.record['value']['method']='other';self.assertEqual(validate_score(self.record,self.job,self.prepared)['status'],'invalid_input')
 def test_pending(self):
  self.record['value']['status']='pending';self.assertEqual(validate_score(self.record,self.job,self.prepared),{'status':'pending','reason':'pending'})
 def test_nonfinite(self):
  self.record['value']['score']=float('nan');self.assertEqual(validate_score(self.record,self.job,self.prepared)['status'],'invalid_input')
class PlanExportTest(unittest.TestCase):
 def test_new_cohorts_and_shared_controls(self):
  import tempfile,json
  from pathlib import Path
  from unittest.mock import patch
  import export_adaptive_awq as export
  with tempfile.TemporaryDirectory() as tmp:
   e=Path(tmp);b=e/'innovation/adaptive_strength_20261023/batch'
   for folder in ['', 'anchor_pilots','field_extension_two','role5_pilots','uniform_pilots']:
    p=b/folder/'jobs.json';p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({'jobs':[{'id':folder or 'original','metadata':{'task_id':'short_0358','method':folder or 'original','comparison_outputs':{'native':{'sha256':'a'},'global_weak':{'sha256':'b'}}}}]}))
   with patch.object(export,'E',e):rows=export.planned_rows()
   self.assertEqual(len(rows),7)
   self.assertEqual(len({r['job_id'] for r in rows}),7)
   self.assertTrue({'field_extension_two','role5_pilots','uniform_pilots'}<={r['job_id'] for r in rows})
if __name__=='__main__':unittest.main()
