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
  p=read(HERE/'PROTOCOL.json');self.assertEqual(p['cases'][0]['windows'],[[50,65],[69,81],[80,92],[99,111]]);self.assertEqual(p['fixed_visual_frames'],[0,55,86,105,140]);self.assertEqual(p['fixed_clip_inclusive'],[42,82]);self.assertEqual(p['thresholds'],[.3,.5]);self.assertEqual(p['scan_rows'],186)
  self.assertFalse(read(HERE/'BINDING.template.json')['approved_for_consumer_start']);self.assertFalse(read(HERE/'AUTO_PARENT_BINDING.template.json')['approved']);self.assertEqual(PHASES,('pose','compare','media'))
 def test_regions_keep_all_windows_and_actual_union(self):
  d=regions_for({'rows':[{'chosen':'full','decision':{'physical_intervals':[[44,59]],'latent_bins':[13,14,15,16,17]}}]});self.assertEqual(len([k for k in d if k.startswith('scan_')]),62);self.assertEqual(d['fixed_50_65'],list(range(50,66)));self.assertEqual(d['actual_Auto_physical_union'],list(range(44,60)));self.assertEqual(len(d['full_0_140']),141)
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
