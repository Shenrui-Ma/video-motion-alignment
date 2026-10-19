import copy,json,tempfile,unittest,subprocess,sys
from pathlib import Path
from contract import *
class ParentTests(unittest.TestCase):
 def fixture(self,root):
  (root/'configs').mkdir();(root/'configs/source.pose.json').write_text('{}');(root/'output').mkdir();(root/'output/auto_00001_.mp4').write_bytes(b'video');(root/'final/pose').mkdir(parents=True)
  save(root/'final/pose/f.pose.json',{'video':{'sha256':sha(root/'output/auto_00001_.mp4')}})
  inv={'configs/source.pose.json':{'sha256':sha(root/'configs/source.pose.json')},'output/auto_00001_.mp4':{'sha256':sha(root/'output/auto_00001_.mp4')}};save(root/'FILE_INVENTORY.json',inv)
  save(root/'RUN_GATE.json',{'passed':True,'run_id':'auto','file_inventory_sha256':sha(root/'FILE_INVENTORY.json'),'additional_checks':{'clean_condition_exact':True,'two_stream_noise_actual_exact':True}})
  save(root/'CPU_COMPLETE.json',{'passed':True,'run_id':'auto'});save(root/'DECISION_LEDGER.json',{'NFE':20,'Euler_updates':20,'active_indices':[],'rows':[{'chosen':'native'} for _ in range(20)]})
  save(root/'RUNTIME_GATE.json',{'status':'pass','cases':[{'run':'auto','NFE':20,'mask':[],'all_OFF_final_exact':True}]})
  save(root/'final/FINAL_SUMMARY.json',{'pose_sha256':sha(root/'final/pose/f.pose.json'),'video_sha256':sha(root/'output/auto_00001_.mp4')})
  save(root/'DERIVED_FILES.json',{r:sha(root/r) for r in ('CPU_COMPLETE.json','DECISION_LEDGER.json','final/pose/f.pose.json','final/FINAL_SUMMARY.json')})
  b={'approved':True,'parent_root':str(root),'run_id':'auto','required_files':{r:sha(root/r) for r in ('RUN_GATE.json','CPU_COMPLETE.json','FILE_INVENTORY.json','DERIVED_FILES.json','DECISION_LEDGER.json','RUNTIME_GATE.json','final/FINAL_SUMMARY.json')},'pose_relative':'final/pose/f.pose.json','pose_sha256':sha(root/'final/pose/f.pose.json'),'video_relative':'output/auto_00001_.mp4','video_sha256':sha(root/'output/auto_00001_.mp4')}
  p={'auto_parent_root':str(root),'auto_parent_run':'auto','source_pose_sha256':sha(root/'configs/source.pose.json'),'parent_anchor_inventory_sha256':sha(root/'FILE_INVENTORY.json'),'parent_pinned_evidence':{'configs/source.pose.json':sha(root/'configs/source.pose.json')}};return b,p
 def test_actual_completed_allOFF_and_tamper(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);b,p=self.fixture(r);validate_auto_parent(b,p);(r/'output/auto_00001_.mp4').write_bytes(b'wrong')
   with self.assertRaises(ValueError):validate_auto_parent(b,p)
 def test_changed_ON_even_rehashed_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);b,p=self.fixture(r);x=read(r/'DECISION_LEDGER.json');x['active_indices']=[4];save(r/'DECISION_LEDGER.json',x);b['required_files']['DECISION_LEDGER.json']=sha(r/'DECISION_LEDGER.json');derived=read(r/'DERIVED_FILES.json');derived['DECISION_LEDGER.json']=sha(r/'DECISION_LEDGER.json');save(r/'DERIVED_FILES.json',derived);b['required_files']['DERIVED_FILES.json']=sha(r/'DERIVED_FILES.json')
   with self.assertRaises(ValueError):validate_auto_parent(b,p)
 def test_wrong_seed_parent_graph_pin_or_anchor_rejected(self):
  for which in ('run','graph','anchor'):
   with tempfile.TemporaryDirectory() as d:
    r=Path(d);b,p=self.fixture(r)
    if which=='run':b['run_id']='bad1311'
    elif which=='graph':p['parent_pinned_evidence']['configs/source.pose.json']='wrong'
    else:b['required_files'].pop('RUNTIME_GATE.json')
    with self.assertRaises(ValueError):validate_auto_parent(b,p)
 def test_fresh_process_all_imports_and_default_safe_entry(self):
  code='import contract,evaluate_helpers,consume,one_phase,remote_consume,outcome,bind_auto_parent,timing_metrics,scan_current_pose,physical_tolerance,pairwise_gain'
  p=subprocess.run([sys.executable,'-c',code],cwd=HERE,capture_output=True,text=True,timeout=15);self.assertEqual(p.returncode,0,p.stderr)
  p=subprocess.run([sys.executable,str(HERE/'one_phase.py')],capture_output=True,text=True,timeout=15);self.assertEqual(p.returncode,0,p.stderr);self.assertIn('Prepared only',p.stdout)
if __name__=='__main__':unittest.main()
