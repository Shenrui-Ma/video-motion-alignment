import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('rcpu',Path(__file__).with_name('remote_consume.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
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
  self.put(f'audit/router/{n}.json',{});self.put(f'audit/x0/{n}/manifest.json',{'status':'complete','captures':[{'file':'x0_step005.pt'}],'final_sampler_result':{'file':'sampler_final.pt'}})
  self.put(f'audit/x0/{n}/x0_step005.pt',{});self.put(f'audit/x0/{n}/sampler_final.pt',{});self.put('output/'+out['filename'],{})
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
if __name__=='__main__':unittest.main()
