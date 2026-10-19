import json,tempfile,unittest,sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import contract as c,consume
class Tests(unittest.TestCase):
 def fixture(self,arc,complete):
  c.save(arc/'input.json',{'x':1});c.save(arc/'FILE_INVENTORY.json',{'input.json':{'sha256':c.sha(arc/'input.json')},'blob.pt':{'sha256':'remote-only'}})
  ds=['RUN_GATE.json','RUNTIME_GATE.json','verify.log','ADMIN_ADMISSION_AT_ARCHIVE.json']
  for name in ds:c.save(arc/name,{})
  if complete:
   ds+=['final/one/SUMMARY.json'];c.save(arc/'final/one/SUMMARY.json',{'result':1});c.save(arc/'CPU_COMPLETE.json',{'passed':True,'derived_outputs':ds});c.save(arc/'DERIVED_FILES.json',{n:c.sha(arc/n) for n in ds+['CPU_COMPLETE.json']})
 def test_prepared_no_start(self):
  self.assertIn("if not a.start:print('Prepared only",(c.HERE/'consume.py').read_text())
 def test_archive_and_final_local_inventory(self):
  for complete in (False,True):
   with tempfile.TemporaryDirectory() as d:self.fixture(Path(d),complete);consume.check_download(Path(d))
 def test_extra_file_and_removed_output(self):
  for mode in ('extra','removed'):
   with tempfile.TemporaryDirectory() as d:
    arc=Path(d);self.fixture(arc,True)
    if mode=='extra':c.save(arc/'stray.json',{})
    else:
     (arc/'final/one/SUMMARY.json').unlink();manifest=c.read(arc/'DERIVED_FILES.json');del manifest['final/one/SUMMARY.json'];c.save(arc/'DERIVED_FILES.json',manifest)
    with self.assertRaises(ValueError):consume.check_download(arc)
 def test_frozen_source_windows_evaluation_only(self):
  p=c.read(c.HERE/'PROTOCOL.json');self.assertEqual([r['source_id'] for r in p['cases']],['51765']);self.assertEqual([r['seed'] for r in p['cases']],[2026101701]);self.assertEqual(c.sha(c.HERE/p['source_design']['file']),p['source_design']['sha256']);self.assertTrue(p['source_design']['evaluation_only'])
  for case in p['cases']:self.assertEqual(case['windows'],[[0,31],[32,63],[64,95],[96,127],[125,140],[0,140]])
 def test_runtime_seal_unchanged(self):
  root=c.HERE.parents[1];manifest=c.read(root/'deploy_manifest.json')
  for rel,row in manifest['files'].items():self.assertEqual(c.sha(root/rel),row['sha256'])
 def test_frozen_scan_metrics_exact(self):
  r27=c.HERE.parents[2]/'h3-timing-auto-controller-r27-20261017/scripts'
  for name in ('timing_metrics.py','pairwise_gain.py','scan_current_pose.py'):self.assertEqual(c.sha(c.HERE/name),c.sha(r27/name))
 def test_playback_nonuniform_rejected(self):
  probe={'streams':[{'width':1312,'height':736,'r_frame_rate':'24/1','avg_frame_rate':'24/1','time_base':'1/12288','duration':'5.875'}],'frames':[{'best_effort_timestamp_time':str(i/24)} for i in range(141)]};self.assertTrue(c.check_playback_probe(probe)['passed']);probe['frames'][13]['best_effort_timestamp_time']='1'
  with self.assertRaises(ValueError):c.check_playback_probe(probe)
if __name__=='__main__':unittest.main()
