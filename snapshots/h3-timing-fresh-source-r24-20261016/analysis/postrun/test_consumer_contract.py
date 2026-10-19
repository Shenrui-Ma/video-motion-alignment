import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('rcpu',Path(__file__).with_name('remote_consume.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
local_spec=importlib.util.spec_from_file_location('lcpu',Path(__file__).with_name('consume.py'));local=importlib.util.module_from_spec(local_spec);local_spec.loader.exec_module(local)
class Contract(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name);self.old=m.BASE;m.BASE=self.base;self.addCleanup(setattr,m,'BASE',self.old);self.root=self.base/'a';self.root.mkdir();self.run='r24_fresh_a_seed2026101610_native'
  self.put('deploy_manifest.json',{'files':{}});self.owner={'pid':999999999,'identity':{'uid':1016,'start_ticks':'1','cmdline':'fake'}};self.put('processes/service.json',self.owner)
  self.binding=self.base/'binding.json';self.binding.write_text(json.dumps({'lanes':{'a':{'remote_root':str(self.root),'service_pid':self.owner['pid'],'service_identity':self.owner['identity'],'external_identity':{},'manifest_file':'deploy_manifest.json','manifest_sha256':m.sha(self.root/'deploy_manifest.json'),'runs':[self.run]}}}))
 def put(self,rel,d):
  p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d));return p
 def complete(self):
  n=self.run;out={'filename':n+'_00001_.mp4','subfolder':'','type':'output'}
  self.put(f'logs/{n}_history.json',{'status':{'completed':True,'status_str':'success'},'outputs':{'14':{'images':[out]}}});self.put(f'logs/{n}_job.json',{'status':'success'});self.put(f'configs/graphs/{n}.json',{})
  self.put('configs/runtime.json',{});self.put('configs/job_registry.json',{'case':{'case_id':'fresh_a','video':'v.mp4','portrait':'p.jpg','provenance':'p.json'}})
  for f in ['v.mp4','p.jpg','p.json']:self.put('inputs/'+f,{})
  self.put(f'audit/{n}_conditioning.json',{});self.put(f'audit/{n}_noise.json',{'pair_id':'pair'});self.put('audit/pair_noise.pt',{});self.put('audit/r24_fresh_a_shared_conditioning.json',{})
  self.put(f'audit/router/{n}.json',{});self.put(f'audit/x0/{n}/manifest.json',{'status':'complete','captures':[{'file':f'x0_step{i:03d}.pt'} for i in (5,10,15,19)],'final_sampler_result':{'file':'sampler_final.pt'}})
  for f in [f'x0_step{i:03d}.pt' for i in (5,10,15,19)]+['sampler_final.pt']:self.put(f'audit/x0/{n}/'+f,{})
  self.put('output/'+out['filename'],{})
 def test_pending_does_not_require_cleanup(self):self.assertEqual(m.snapshot('a',self.binding)['runs'][self.run]['status'],'pending')
 def test_complete_is_ready_while_sibling_runs_no_cleanup(self):
  self.complete();self.put('logs/controller_state.json',{'status':'pending_or_running','current':'sibling'});self.assertEqual(m.snapshot('a',self.binding)['runs'][self.run]['status'],'success_files_present')
 def test_inventory_excludes_sibling(self):
  self.complete();self.put('output/sibling_00001_.mp4',{});self.assertFalse(any('sibling' in str(p) for p in m.inventory(self.root,self.run)))
 def test_mutated_json_changes_stability_token(self):
  self.complete();a=m.snapshot('a',self.binding)['runs'][self.run]['stability_token'];self.put(f'audit/router/{self.run}.json',{'new':1});b=m.snapshot('a',self.binding)['runs'][self.run]['stability_token'];self.assertNotEqual(a,b)
 def test_output_wrong_run_rejected(self):
  self.complete();h=m.read(self.root/f'logs/{self.run}_history.json');h['outputs']['14']['images'][0]['filename']='sibling_00001_.mp4'
  with self.assertRaises(ValueError):m.output_file(self.root,h,self.run)
 def test_output_subfolder_rejected(self):
  self.complete();h=m.read(self.root/f'logs/{self.run}_history.json');h['outputs']['14']['images'][0]['subfolder']='../'
  with self.assertRaises(ValueError):m.output_file(self.root,h,self.run)
 def test_replaced_service_rejected(self):
  self.put('processes/service.json',{'pid':2,'identity':self.owner['identity']})
  with self.assertRaises(ValueError):m.snapshot('a',self.binding)
 def test_escaping_blob_rejected(self):
  self.complete();self.put('audit/r24_fresh_a_shared_conditioning.json',{'tensor_file':'../../outside.pt','shape':[1],'dtype':'f32','sha256':'x'})
  with self.assertRaises(ValueError):m.inventory(self.root,self.run)
 def test_symlink_rejected(self):
  p=self.base/'outside';p.write_text('x');(self.root/'bad').symlink_to(p)
  with self.assertRaises(ValueError):m.safe(self.root,'bad')
 def test_error_is_not_completion(self):
  self.complete();self.put(f'logs/{self.run}_history.json',{'status':{'completed':True,'status_str':'error'}});self.assertEqual(m.snapshot('a',self.binding)['runs'][self.run]['status'],'failed')
 def test_unknown_missing_without_history_is_terminal_failure(self):
  self.put(f'logs/{self.run}_job.json',{'status':'unknown_missing'});self.assertEqual(m.snapshot('a',self.binding)['runs'][self.run]['status'],'failed')
 def test_uncertain_without_history_is_terminal_failure(self):
  self.put(f'logs/{self.run}_job.json',{'status':'submission_uncertain'});self.assertEqual(m.snapshot('a',self.binding)['runs'][self.run]['status'],'failed')
 def test_controller_failed_unsubmitted_is_not_pending(self):
  self.put('logs/controller_state.json',{'status':'failed'});r=m.snapshot('a',self.binding)['runs'][self.run];self.assertEqual(r['status'],'failed');self.assertEqual(r['reason'],'unsubmitted_after_terminal')
 def test_exact_cleanup_unsubmitted_is_not_pending(self):
  self.put('processes/cleanup.json',{'service_record':self.owner,'process_absent':True,'own_compute_absent':True});self.assertEqual(m.snapshot('a',self.binding)['runs'][self.run]['status'],'failed')
 def test_stale_cleanup_does_not_end_current_generation(self):
  self.put('processes/cleanup.json',{'service_record':{'pid':1},'process_absent':True,'own_compute_absent':True});self.assertEqual(m.snapshot('a',self.binding)['runs'][self.run]['status'],'pending')
 def test_success_consumable_even_after_sibling_failure(self):
  self.complete();self.put('logs/controller_state.json',{'status':'failed','current':'sibling'});self.assertEqual(m.snapshot('a',self.binding)['runs'][self.run]['status'],'success_files_present')
 def test_original_extra_pt_rejected(self):
  self.complete();self.put(f'audit/x0/{self.run}/extra.pt',{})
  with self.assertRaisesRegex(ValueError,'original run PT directory'):m.inventory(self.root,self.run)
 def test_original_missing_pt_rejected(self):
  self.complete();(self.root/f'audit/x0/{self.run}/x0_step010.pt').unlink()
  with self.assertRaisesRegex(ValueError,'original run PT directory'):m.inventory(self.root,self.run)
 def test_manifest_subset_cannot_hide_actual_pt(self):
  self.complete();p=self.root/f'audit/x0/{self.run}/manifest.json';d=m.read(p);d['captures']=d['captures'][:1];p.write_text(json.dumps(d))
  with self.assertRaisesRegex(ValueError,'original manifest PT inventory'):m.inventory(self.root,self.run)
 def pair_fixture(self):
  d=self.base/'pair';d.mkdir();expected={'case':'fresh_a','seed':2026101610,'members':[self.run],'checks':{'prefix':True},'source_pose_sha256':'s','archive_inventory_sha256':{'n':'h'}}
  m.save(d/'PAIR_COMPLETE.json',{'passed':True,**expected});m.save(d/'common.json',{'value':1});m.save(d/'PAIR_FILES.json',{p.name:m.sha(p) for p in d.iterdir()});return d,expected
 def test_existing_pair_recovers_after_transport_failure(self):
  d,e=self.pair_fixture();self.assertTrue(m.completed_pair(d,e)['passed'])
 def test_existing_pair_wrong_members_rejected(self):
  d,e=self.pair_fixture();e['members']=['other']
  with self.assertRaisesRegex(ValueError,'binding/gates'):m.completed_pair(d,e)
 def test_existing_pair_changed_output_rejected(self):
  d,e=self.pair_fixture();(d/'common.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'bytes changed'):m.completed_pair(d,e)
 def test_existing_pair_missing_output_rejected(self):
  d,e=self.pair_fixture();(d/'common.json').unlink()
  with self.assertRaisesRegex(ValueError,'inventory changed'):m.completed_pair(d,e)
 def test_existing_pair_extra_output_rejected(self):
  d,e=self.pair_fixture();(d/'extra.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'inventory changed'):m.completed_pair(d,e)
 def test_local_pair_download_verifies(self):
  d,e=self.pair_fixture();local.verify_pair_download(d)
 def test_local_pair_download_changed_bytes_rejected(self):
  d,e=self.pair_fixture();(d/'common.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'SHA/path'):local.verify_pair_download(d)
if __name__=='__main__':unittest.main()
