import ast,json,tempfile,unittest
from pathlib import Path
from contract import *
from one_phase import readiness
from outcome import regions_for

class IntakeTests(unittest.TestCase):
 def test_stability_and_terminal(self):
  self.assertEqual(readiness({'status':'pending'},None,1,60),('pending',None))
  self.assertEqual(readiness({'status':'producer_failed'},None,1,60)[0],'producer_failed')
  a={'status':'success_files_present','token':'a'};mode,state=readiness(a,None,1,60);self.assertEqual(mode,'stabilizing');self.assertEqual(readiness(a,state,60,60)[0],'stabilizing');self.assertEqual(readiness(a,state,61,60)[0],'ready');self.assertEqual(readiness(dict(a,token='b'),state,62,60)[0],'stabilizing')
 def test_scope_and_phases(self):
  p=read(HERE/'PROTOCOL.json');self.assertEqual(p['cases'][0]['windows'],[[0,31],[32,63],[64,95],[96,127],[125,140]]);self.assertEqual(p['fixed_visual_frames'],[0,24,48,72,96,120,140]);self.assertEqual(p['fixed_clip_inclusive'],[0,140]);self.assertEqual(p['thresholds'],[.3,.5]);self.assertEqual(p['scan_rows'],186)
  self.assertFalse(read(HERE/'BINDING.template.json')['approved_for_consumer_start']);self.assertFalse(read(HERE/'AUTO_PARENT_BINDING.template.json')['approved']);self.assertEqual(PHASES,('pose','compare','media'))
 def test_regions_keep_all_windows_and_actual_union(self):
  d=regions_for({'rows':[{'chosen':'full','decision':{'physical_intervals':[[44,59]],'latent_bins':[13,14,15,16,17]}}]});self.assertEqual(len([k for k in d if k.startswith('scan_')]),62);self.assertEqual(d['primary_64_95'],list(range(64,96)));self.assertEqual(d['actual_Auto_physical_union'],list(range(44,60)));self.assertEqual(len(d['full_0_140']),141)
 def test_partial_phase_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   arc=Path(d);phase_folder(arc,'pose').mkdir(parents=True)
   with self.assertRaises(FileNotFoundError):validate_phase(arc,'pose')
 def test_phase_extra_or_tampered_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   arc=Path(d);folder=phase_folder(arc,'pose');folder.mkdir(parents=True);(folder/'value.txt').write_text('ok');seal_phase(arc,'pose',{});validate_phase(arc,'pose');(folder/'value.txt').write_text('bad')
   with self.assertRaises(ValueError):validate_phase(arc,'pose')
 def test_parent_missing_never_substituted(self):
  with self.assertRaises(ValueError):validate_auto_parent({'approved':False},read(HERE/'PROTOCOL.json'))
 def test_path_rejection(self):
  with tempfile.TemporaryDirectory() as d:
   for path in ('../escape','/tmp/escape'):
    with self.assertRaises(ValueError):safe(Path(d),path)

class ParentTests(unittest.TestCase):
 def fixture(self,root):
  (root/'configs').mkdir();(root/'configs/source.pose.json').write_text('{}');(root/'output').mkdir();(root/'output/auto_00001_.mp4').write_bytes(b'video');(root/'final/pose').mkdir(parents=True)
  save(root/'final/pose/f.pose.json',{'video':{'sha256':sha(root/'output/auto_00001_.mp4')}})
  inv={'deploy_manifest.json':{'sha256':'auto-manifest'},'configs/source.pose.json':{'sha256':sha(root/'configs/source.pose.json')},'output/auto_00001_.mp4':{'sha256':sha(root/'output/auto_00001_.mp4')}};save(root/'FILE_INVENTORY.json',inv);save(root/'RUN_GATE.json',{'passed':True,'run_id':'auto','file_inventory_sha256':sha(root/'FILE_INVENTORY.json'),'additional_checks':{'clean_condition_exact':True,'two_stream_noise_actual_exact':True}});save(root/'CPU_COMPLETE.json',{'passed':True,'run_id':'auto'});save(root/'DECISION_LEDGER.json',{});save(root/'DERIVED_FILES.json',{r:sha(root/r) for r in ('CPU_COMPLETE.json','DECISION_LEDGER.json','final/pose/f.pose.json')})
  b={'approved':True,'parent_root':str(root),'run_id':'auto','required_files':{r:sha(root/r) for r in ('RUN_GATE.json','CPU_COMPLETE.json','FILE_INVENTORY.json','DERIVED_FILES.json','DECISION_LEDGER.json')},'pose_relative':'final/pose/f.pose.json','pose_sha256':sha(root/'final/pose/f.pose.json'),'video_relative':'output/auto_00001_.mp4','video_sha256':sha(root/'output/auto_00001_.mp4')};p={'auto_producer_manifest_sha256':'auto-manifest','auto_parent_root':str(root),'auto_parent_run':'auto','source_pose_sha256':sha(root/'configs/source.pose.json')};return b,p
 def test_actual_parent_pass_and_video_tamper(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);b,p=self.fixture(root);validate_auto_parent(b,p);(root/'output/auto_00001_.mp4').write_bytes(b'changed')
   with self.assertRaises(ValueError):validate_auto_parent(b,p)
 def test_wrong_run_wrong_source_missing_anchor(self):
  for variant in ('run','source','anchor'):
   with tempfile.TemporaryDirectory() as d:
    root=Path(d);b,p=self.fixture(root)
    if variant=='run':b['run_id']='native'
    elif variant=='source':p['source_pose_sha256']='wrong'
    else:b['required_files'].pop('CPU_COMPLETE.json')
    with self.assertRaises(ValueError):validate_auto_parent(b,p)
 def test_failed_parent_rejected_even_rehashed(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);b,p=self.fixture(root);save(root/'CPU_COMPLETE.json',{'passed':False,'run_id':'auto'});b['required_files']['CPU_COMPLETE.json']=sha(root/'CPU_COMPLETE.json')
   with self.assertRaises(ValueError):validate_auto_parent(b,p)

class FrozenHelperTests(unittest.TestCase):
 def test_reused_function_source_is_exact(self):
  p=read(HERE/'PROTOCOL.json')
  for dest,info in p['freeze_helper_reuse'].items():
   source=Path(info['source']);self.assertEqual(sha(source),info['source_sha256']);a=source.read_text();b=(HERE/dest).read_text();af={n.name:ast.get_source_segment(a,n) for n in ast.parse(a).body if isinstance(n,ast.FunctionDef)};bf={n.name:ast.get_source_segment(b,n) for n in ast.parse(b).body if isinstance(n,ast.FunctionDef)}
   for name in info['functions']:self.assertEqual(af[name],bf[name])
 def test_status_does_not_call_full_inventory(self):
  src=(HERE/'remote_consume.py').read_text();fn=next(n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name=='status');text=ast.get_source_segment(src,fn)
  self.assertNotIn('verify_source_archive',text);self.assertNotIn('all_files=True',text);self.assertNotIn('validate_delivery',text)

class DeliveryTests(unittest.TestCase):
 def fixture(self,arc):
  (arc/'data.pt').write_bytes(b'actual');save(arc/'FILE_INVENTORY.json',{'data.pt':{'sha256':sha(arc/'data.pt'),'bytes':6}})
  for name in ('RUN_GATE.json','RUNTIME_GATE.json','ADMIN_ADMISSION_AT_ARCHIVE.json'):save(arc/name,{})
  (arc/'verify.log').write_text('PASS')
 def test_initial_and_local_nonpt_delivery(self):
  with tempfile.TemporaryDirectory() as d:
   arc=Path(d);self.fixture(arc);validate_delivery(arc);(arc/'data.pt').unlink();validate_delivery(arc,local=True)
   with self.assertRaises(ValueError):validate_delivery(arc)
 def test_unregistered_media_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   arc=Path(d);self.fixture(arc);(arc/'extra.mp4').write_bytes(b'bad')
   with self.assertRaises(ValueError):validate_delivery(arc)
 def test_phase_complete_and_extra_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   arc=Path(d);self.fixture(arc);f=phase_folder(arc,'pose');f.mkdir(parents=True);save(f/'pose.json',{});seal_phase(arc,'pose',{});validate_delivery(arc);save(f/'extra.json',{})
   with self.assertRaises(ValueError):validate_delivery(arc)

if __name__=='__main__':unittest.main()
