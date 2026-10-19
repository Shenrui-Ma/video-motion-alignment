import importlib.util,json,shutil,sys,tempfile,unittest
from pathlib import Path
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('r26remote',P/'remote_consume.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
spec=importlib.util.spec_from_file_location('r26scan',P/'scan_native.py');scan=importlib.util.module_from_spec(spec);spec.loader.exec_module(scan)
class Contract(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.old=m.BASE;m.BASE=self.base;self.addCleanup(setattr,m,'BASE',self.old);self.root=self.base/'a';self.root.mkdir();self.run='r26_source_40372_seed2026101701_native'
  self.put('deploy_manifest.json',{'files':{}});self.owner={'pid':999999999,'identity':{'uid':1016,'start_ticks':'1','cmdline':'fake'}};self.put('processes/service.json',self.owner)
  self.binding=self.base/'binding.json';self.binding.write_text(json.dumps({'lanes':{'a':{'remote_root':str(self.root),'service_pid':self.owner['pid'],'service_identity':self.owner['identity'],'external_identity':{},'manifest_file':'deploy_manifest.json','manifest_sha256':m.sha(self.root/'deploy_manifest.json'),'runs':[self.run]}}}))
  (self.root/'scripts').mkdir();shutil.copyfile(P.parents[1]/'scripts/r26_contract.py',self.root/'scripts/r26_contract.py')
 def put(self,rel,d):
  p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d));return p
 def case(self,cid):return {'case_id':'source_'+cid,'source_id':cid,'video':cid+'.mp4','portrait':'p.jpg','provenance':cid+'.json','video_sha256':'a'*64,'portrait_sha256':'b'*64,'provenance_sha256':'c'*64,'primary_window_inclusive':[0,140],'prompt':'test prompt','new_to_study_attestation':True}
 def complete(self):
  n=self.run;c=self.case('40372');self.put('configs/job_registry.json',{'case':c,'jobs':{n:{'seed':2026101701,'arm':'native','graph_sha256':'d'*64}}});self.put('configs/queue.json',{'jobs':[n],'finalize':False});self.put('configs/native_screen.json',{'prompt':'test prompt','portrait_sha256':'b'*64,'source_ids':['40372'],'seed':2026101701,'arm':'native','capture_indices':list(range(20)),'append_after_seal':False})
  self.put('configs/native_material_manifest.json',{});self.put('configs/native_source_selection_manifest.json',{});self.fixture_output(n,c)
 def fixture_output(self,n,c):
  out={'filename':n+'_00001_.mp4','subfolder':'','type':'output'}
  self.put(f'logs/{n}_history.json',{'status':{'completed':True,'status_str':'success'},'outputs':{'14':{'images':[out]}}});self.put(f'logs/{n}_job.json',{'status':'success'});self.put(f'configs/graphs/{n}.json',{});self.put('configs/runtime.json',{})
  for k in ('video','portrait','provenance'):self.put('inputs/'+c[k],{})
  self.put(f'audit/{n}_conditioning.json',{});self.put(f'audit/{n}_noise.json',{'pair_id':'pair_'+n});self.put(f'audit/pair_{n}_noise.pt',{});self.put(f'audit/r26_{c["case_id"]}_shared_conditioning.json',{})
  self.put(f'audit/router/{n}.json',{});self.put(f'audit/x0/{n}/manifest.json',{'status':'complete','captures':[{'file':f'x0_step{i:03d}.pt'} for i in range(20)],'final_sampler_result':{'file':'sampler_final.pt'}})
  for f in [f'x0_step{i:03d}.pt' for i in range(20)]+['sampler_final.pt']:self.put(f'audit/x0/{n}/'+f,{})
  self.put('output/'+out['filename'],{})
 def test_pending_no_cleanup(self):self.assertEqual(m.snapshot('a',self.binding)['runs'][self.run]['status'],'pending')
 def test_ready_with_live_sibling(self):
  self.complete();self.put('logs/controller_state.json',{'status':'pending_or_running','current':'sibling'});x=m.snapshot('a',self.binding);self.assertEqual(x['runs'][self.run]['status'],'success_files_present');self.assertFalse(x['batch_ready'])
 def test_batch_ready_exact_completed(self):
  self.complete();self.put('logs/controller_state.json',{'status':'resident_hold','current':None,'completed':[self.run]});self.assertTrue(m.snapshot('a',self.binding)['batch_ready'])
 def test_batch_not_ready_incomplete_order(self):
  self.complete();self.put('logs/controller_state.json',{'status':'resident_hold','current':None,'completed':[]});self.assertFalse(m.snapshot('a',self.binding)['batch_ready'])
 def test_inventory_excludes_sibling(self):
  self.complete();self.put('output/sibling.mp4',{});self.assertFalse(any('sibling' in str(p) for p in m.inventory(self.root,self.run)))
 def test_continuation_uses_its_own_source(self):
  self.complete();n='r26_source_51304_seed2026101701_native';c=self.case('51304');p=self.put('configs/approved_continuations/second.json',{'root_approved':True,'case':c,'jobs':{n:{'seed':2026101701,'arm':'native','graph_sha256':'e'*64}}});self.put('configs/queue.json',{'jobs':[self.run,n],'finalize':False,'approved_continuations':[{'file':str(p.relative_to(self.root)),'sha256':m.sha(p)}]});screen=m.read(self.root/'configs/native_screen.json');screen['source_ids'].append('51304');self.put('configs/native_screen.json',screen);self.fixture_output(n,c);files=[str(p.relative_to(self.root)) for p in m.inventory(self.root,n)];self.assertIn('inputs/51304.mp4',files);self.assertNotIn('inputs/40372.mp4',files);self.assertIn('audit/r26_source_51304_shared_conditioning.json',files)
 def test_mutation_changes_token(self):
  self.complete();a=m.snapshot('a',self.binding)['runs'][self.run]['stability_token'];self.put(f'audit/router/{self.run}.json',{'new':1});self.assertNotEqual(a,m.snapshot('a',self.binding)['runs'][self.run]['stability_token'])
 def test_wrong_output_reject(self):
  self.complete();h=m.read(self.root/f'logs/{self.run}_history.json');h['outputs']['14']['images'][0]['filename']='other.mp4'
  with self.assertRaises(ValueError):m.output_file(self.root,h,self.run)
 def test_replaced_service(self):
  self.put('processes/service.json',{'pid':1,'identity':self.owner['identity']})
  with self.assertRaises(ValueError):m.snapshot('a',self.binding)
 def test_escape_blob(self):
  self.complete();self.put('audit/r26_source_40372_shared_conditioning.json',{'tensor_file':'../../outside.pt','shape':[1],'dtype':'x','sha256':'h'})
  with self.assertRaises(ValueError):m.inventory(self.root,self.run)
 def test_symlink(self):
  p=self.base/'outside';p.write_text('x');(self.root/'bad').symlink_to(p)
  with self.assertRaises(ValueError):m.safe(self.root,'bad')
 def test_producer_error(self):
  self.complete();self.put(f'logs/{self.run}_history.json',{'status':{'completed':True,'status_str':'error'}});self.assertEqual(m.snapshot('a',self.binding)['runs'][self.run]['status'],'failed')
 def test_unknown_missing(self):
  self.put(f'logs/{self.run}_job.json',{'status':'unknown_missing'});self.assertEqual(m.snapshot('a',self.binding)['runs'][self.run]['status'],'failed')
 def test_uncertain(self):
  self.put(f'logs/{self.run}_job.json',{'status':'submission_uncertain'});self.assertEqual(m.snapshot('a',self.binding)['runs'][self.run]['status'],'failed')
 def test_terminal_unsubmitted(self):
  self.put('logs/controller_state.json',{'status':'failed'});x=m.snapshot('a',self.binding);self.assertEqual(x['runs'][self.run]['status'],'failed');self.assertTrue(x['producer_terminal'])
 def test_exact_cleanup_terminal(self):
  self.put('processes/cleanup.json',{'service_record':self.owner,'process_absent':True,'own_compute_absent':True});self.assertEqual(m.snapshot('a',self.binding)['runs'][self.run]['status'],'failed')
 def test_stale_cleanup_ignored(self):
  self.put('processes/cleanup.json',{'service_record':{'pid':1},'process_absent':True,'own_compute_absent':True});self.assertEqual(m.snapshot('a',self.binding)['runs'][self.run]['status'],'pending')
 def test_extra_pt(self):
  self.complete();self.put(f'audit/x0/{self.run}/extra.pt',{})
  with self.assertRaisesRegex(ValueError,'original run PT directory'):m.inventory(self.root,self.run)
 def test_missing_pt(self):
  self.complete();(self.root/f'audit/x0/{self.run}/x0_step010.pt').unlink()
  with self.assertRaisesRegex(ValueError,'original run PT directory'):m.inventory(self.root,self.run)
 def test_incomplete_manifest(self):
  self.complete();p=self.root/f'audit/x0/{self.run}/manifest.json';d=m.read(p);d['captures']=d['captures'][:1];self.put(str(p.relative_to(self.root)),d)
  with self.assertRaisesRegex(ValueError,'original manifest PT inventory'):m.inventory(self.root,self.run)
class Scan(unittest.TestCase):
 def test_window_count(self):
  w=list(scan.windows(140));self.assertEqual(len(w),62);self.assertIn([125,140],w);self.assertIn([109,140],w);self.assertEqual(len(w)*len(scan.FEATURES),186)
 def test_threshold_rule(self):
  for ls,expected in [([3,5],'delayed_candidate'),([-3,-5],'advanced_candidate'),([2,-2],'unknown'),([1,-1],'aligned'),([3,6],'unknown'),([None,4],'unknown'),([2,3],'unknown')]:self.assertEqual(scan.classify(ls),expected)
 def test_compact_preserves49points(self):
  v=scan.compact({'reliable_lag_frames':None,'curve':[{'lag':x,'score':.1,'source_frames':[1],'per_frame_error':[2]} for x in range(-24,25)]});self.assertEqual(len(v['curve']),49);self.assertEqual(v['curve'][0],{'lag':-24,'score':.1})
if __name__=='__main__':unittest.main()
