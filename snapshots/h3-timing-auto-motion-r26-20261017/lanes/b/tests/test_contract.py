import copy,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import bind_cases,r26_contract as c,preflight

def fixture(folder,source_id='40372'):
 folder=Path(folder)
 for name in ('v.mp4','p.jpg','proof.json'):(folder/name).write_bytes(name.encode())
 return {'lane':'a','case_id':'source_'+source_id,'source_id':source_id,'video_file':str(folder/'v.mp4'),'video_sha256':c.sha(folder/'v.mp4'),'portrait_file':str(folder/'p.jpg'),'portrait_sha256':c.sha(folder/'p.jpg'),'source_provenance_file':str(folder/'proof.json'),'provenance_sha256':c.sha(folder/'proof.json'),'prompt':'Replace the dancer with the reference person; preserve the source movement.','primary_window_inclusive':[0,140],'new_to_study_attestation':True}
def module(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class ContractTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.base=Path(self.t.name);self.root=self.base/'lane';
  with patch.object(bind_cases,'video_probe',return_value={'nb_read_frames':'141','avg_frame_rate':'24/1','width':1312,'height':736}):bind_cases.bind_case(fixture(self.base),self.root)
  self.jobs,self.order=c.registry(self.root)
 def tearDown(self):self.t.cleanup()
 def write(self,rel,v):bind_cases.write(self.root/rel,v)
 def test_native_graph_seed_no_action_window(self):
  self.assertEqual(preflight.check(self.root)['planned_NFE'],20)
  for run in self.order:
   row=c.validate_job(run,self.root);g=c.read(self.root/'configs/graphs'/f'{run}.json')
   self.assertEqual(g['6']['inputs']['noise_seed'],row['seed']);self.assertEqual([g['50']['inputs']['start_frame'],g['50']['inputs']['end_frame']],[0,140])
  self.assertEqual(len(self.order),1)
  self.assertEqual(c.SEEDS,(2026101701,));self.assertEqual(c.ARMS,('native',))
  science=c.read(self.root/'configs/scientific_contract.json');self.assertEqual(science['captures'],list(range(20)))
 def test_actual_remote_root_matches_authorized_deployment(self):
  self.assertEqual(str(c.REMOTE_BASE),'/data5/researcher/h3_runs/timing_auto_motion_r26_20261017')
  rt=c.read(self.root/'configs/runtime.json');self.assertEqual(rt['remote_root'],str(c.REMOTE_BASE/'a'))
 def test_sealed_source_order_and_prompt(self):
  case=self.jobs[self.order[0]]['case'];f={'source_ids':['40372'],'seed':2026101701,'arm':'native','capture_indices':list(range(20)),'append_after_seal':False,'prompt':case['prompt'],'portrait_sha256':case['portrait_sha256']};self.write('configs/native_screen.json',f);c.registry(self.root)
  f['source_ids']=['51317'];self.write('configs/native_screen.json',f)
  with self.assertRaises(ValueError):c.registry(self.root)
  f['source_ids']=['40372'];f['prompt']='changed';self.write('configs/native_screen.json',f)
  with self.assertRaises(ValueError):c.registry(self.root)
 def test_graph_mutation_rejected(self):
  p=self.root/'configs/graphs'/f'{self.order[0]}.json';g=c.read(p);g['6']['inputs']['noise_seed']+=1;bind_cases.write(p,g)
  with self.assertRaises(ValueError):c.validate_job(self.order[0],self.root)
 def test_asset_mutation_rejected(self):
  row=self.jobs[self.order[0]];(self.root/'inputs'/row['case']['video']).write_bytes(b'changed')
  with self.assertRaises(ValueError):c.validate_job(self.order[0],self.root)
 def test_unregistered_run(self):
  with self.assertRaises(ValueError):c.validate_job('r20_s07_native',self.root)
 def test_reorder_and_partial_rejected(self):
  q=c.read(self.root/'configs/queue.json');q['jobs']=[];self.write('configs/queue.json',q)
  with self.assertRaises(ValueError):c.registry(self.root)
 def test_unapproved_continuation_rejected(self):
  q=c.read(self.root/'configs/queue.json');q['approved_continuations']=[{'file':'../outside','sha256':'0'*64}];self.write('configs/queue.json',q)
  with self.assertRaises(ValueError):c.registry(self.root)
 def test_bound_continuation(self):
  batch=c.read(self.root/'configs/job_registry.json');batch['case']['case_id']='source_51304';batch['case']['source_id']='51304';batch['root_approved']=True
  batch['jobs']={c.run_name(batch['case'],s,a):dict(seed=s,arm=a,graph_sha256='0'*64) for s in c.SEEDS for a in c.ARMS}
  rel='configs/approved_continuations/beta.json';self.write(rel,batch);q=c.read(self.root/'configs/queue.json');q['approved_continuations']=[dict(file=rel,sha256=c.sha(self.root/rel))];q['jobs']+=list(batch['jobs']);self.write('configs/queue.json',q)
  self.assertEqual(len(c.registry(self.root)[1]),2)
  batch['root_approved']=False;self.write(rel,batch)
  with self.assertRaises(ValueError):c.registry(self.root)
 def test_admission_defaults_closed(self):
  with self.assertRaises(ValueError):preflight.check(self.root,live=True)
 def test_no_overwrite_or_unbound_source(self):
  with self.assertRaises(FileExistsError):bind_cases.bind_case(fixture(self.base),self.root)
  s=fixture(self.base);s['new_to_study_attestation']=False
  with self.assertRaises(ValueError):bind_cases.bind_case(s,self.base/'bad')
 def test_retention_and_cleanup_identity(self):
  svc=module('r26_test_service',self.root/'scripts/service.py')
  self.assertNotIn('--cache-none',svc.command())
  with self.assertRaises(ValueError):svc.command(True)
  ident={'uid':svc.os.getuid(),'start_ticks':'12','cmdline':f'{svc.CORE}/main.py {svc.RUN}'};rec={'pid':111,'identity':ident,'gpu_uuid':svc.GPU,'port':svc.PORT}
  (self.root/'processes').mkdir();self.write('processes/service.json',rec)
  with patch.object(svc,'current_identity',return_value=dict(ident,start_ticks='13')),patch.object(svc.os,'kill') as kill:
   with self.assertRaises(RuntimeError):svc.stop()
   kill.assert_not_called()
  with patch.object(svc,'current_identity',side_effect=[ident,ident,None,None]),patch.object(svc,'wait_absent',return_value=True),patch.object(svc,'compute_processes',return_value=[]),patch.object(svc.os,'kill') as kill:
   self.assertTrue(svc.stop()['own_compute_absent']);kill.assert_called_once_with(111,svc.signal.SIGTERM)
 def test_loader_input_copy_and_corruption(self):
  c.prepare_loader_inputs(self.order[0],self.root);case=self.jobs[self.order[0]]['case'];p=self.root/'input'/case['video'];self.assertEqual(c.sha(p),case['video_sha256']);p.write_bytes(b'corrupt')
  with self.assertRaises(ValueError):c.prepare_loader_inputs(self.order[0],self.root)
 def test_stale_controller_cannot_stop_new_registry(self):
  svc=module('r26_test_generation',self.root/'scripts/service.py');(self.root/'processes').mkdir();new={'pid':222,'identity':{'uid':0,'start_ticks':'2'}};self.write('processes/service.json',new)
  with patch.object(svc.os,'kill') as kill:
   with self.assertRaises(RuntimeError):svc.stop(expected_record={'pid':111,'identity':{'uid':0,'start_ticks':'1'}})
   kill.assert_not_called()
 def test_controller_idle_and_prefix(self):
  svc=module('r26_test_service2',self.root/'scripts/service.py')
  with patch.dict(sys.modules,{'service':svc}):
   job=module('r26_test_job',self.root/'scripts/job.py')
   with patch.dict(sys.modules,{'job':job}):queue=module('r26_test_queue',self.root/'scripts/run_queue.py')
  self.assertEqual(queue.idle_action({'finalize':False},1799,1800),'resident_hold');self.assertEqual(queue.idle_action({'finalize':False},1800,1800),'bounded_idle_expired');self.assertEqual(queue.idle_action({'finalize':True},0,1800),'final_close')
  self.assertEqual(queue.remaining(self.order,self.order[:2]),self.order[2:])
  with self.assertRaises(ValueError):queue.remaining(self.order,['bad'])
  policy=c.read(self.root/'configs/scientific_contract.json')['continuous'];self.assertEqual(policy['max_service_seconds'],43200)
if __name__=='__main__':unittest.main()
