import copy,json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import recovery_contract as r
import service
class RecoveryQueue(unittest.TestCase):
 def test_exact_four_and_external_chest(self):
  p=r.plan();self.assertEqual(len(p['new_runs']),4);self.assertEqual(p['planned_denominator'],5);self.assertEqual(p['external_chest']['run_id'],'r50_source_chest_seed2026101701_auto');r.queue()
 def test_chest_cannot_reenter_new_queue(self):
  original=r.read
  def altered(p):
   v=original(p)
   if Path(p).name=='execution_plan.json':v['new_runs'].insert(0,v['external_chest']['run_id'])
   return v
  with patch.object(r,'read',side_effect=altered),self.assertRaisesRegex(ValueError,'four execution'):r.plan()
 def test_order_change_rejected(self):
  original=r.read
  def altered(p):
   v=original(p)
   if Path(p).name=='execution_plan.json':v['new_runs'].reverse()
   return v
  with patch.object(r,'read',side_effect=altered),self.assertRaisesRegex(ValueError,'order'):r.plan()
 def test_low_memory_snapshot_serializable_then_recovery(self):
  from observer_import import t
  import subprocess
  state={'time':0};clock=lambda:state['time']
  def sleep(seconds):state['time']+=seconds
  results=iter([subprocess.CompletedProcess([],0,service.GPU+', 100, 1, 0, 40\n',''),subprocess.CompletedProcess([],0,service.GPU+', 100, 100, 0, 40\n','')])
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'logs').mkdir()
   with patch.object(service,'RUN',root),patch.object(service,'main_memory_profile',return_value={'required_free_bytes':2*1024**2,'profile_sha256':'x'}),patch.object(service,'compute_processes',return_value=[]),patch.object(service,'check_admission'),patch.object(service.subprocess,'run',side_effect=lambda *a,**k:next(results)):
    result=service.gpu_readiness({}, {},clock=clock,sleep=sleep)
   rows=[json.loads(x) for x in (root/'logs/service_resource_admission.jsonl').read_text().splitlines()]
   self.assertEqual([x['status'] for x in rows],['waiting','admitted']);self.assertEqual(result['status'],'admitted')
if __name__=='__main__':unittest.main()
