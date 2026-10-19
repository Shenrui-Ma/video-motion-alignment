import copy,hashlib,importlib.util,json,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r97_contract as c
from parent_evidence import compare_parent_gate,comparable_conditions
spec=importlib.util.spec_from_file_location('control_runner',ROOT/'audit/root_run_control.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class ScheduleControl(unittest.TestCase):
 def clone(self):
  d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup);r=Path(d.name)
  for f in ('configs','design'):shutil.copytree(ROOT/f,r/f)
  return r
 def test_single_extension_contract(self):
  jobs,order=c.registry();self.assertEqual(order,[c.RUN_ID]);self.assertEqual(jobs[c.RUN_ID]['arm'],'extended');self.assertEqual(c.routing_layout(jobs[c.RUN_ID]['case'])['latent_interval_half_open'],[0,32])
 def test_only_step_end_is_scientific_graph_change(self):
  a=c.read(ROOT/'design/R89_ACTUAL/forced_graph.json');b=c.read(ROOT/'configs/graphs'/(c.RUN_ID+'.json'))
  diff={(n,k) for n in a for k,v in a[n]['inputs'].items() if b[n]['inputs'].get(k)!=v}
  allowed={('5','run_id'),('5','audit_dir'),('6','audit_dir'),('6','run_id'),('6','pair_id'),('50','audit_dir'),('50','run_id'),('50','step_end'),('51','source_audit_dir'),('51','source_run_id'),('51','run_id'),('52','output_dir'),('52','run_id'),('14','filename_prefix')}
  self.assertEqual(diff,allowed);self.assertEqual(a['50']['inputs']['step_end'],15);self.assertEqual(b['50']['inputs']['step_end'],20)
 def test_graph_unregistered_changes_refused(self):
  for node,key,val in [('5','prompt','changed'),('50','alpha',.5),('50','step_start',0),('50','end_frame',106),('6','noise_seed',1),('9','sigmas','1,0')]:
   r=self.clone();p=r/'configs/graphs'/(c.RUN_ID+'.json');j=c.read(p);j[node]['inputs'][key]=val;p.write_text(json.dumps(j))
   with self.assertRaisesRegex(ValueError,'graph differs'):c.registry(r)
 def test_exact_numeric_six(self):
  k=c.read(ROOT/'configs/runtime_kernel_hashes.json');self.assertEqual(len(k),6)
  for path,row in k.items():self.assertEqual(c.sha(ROOT/path),row['parent_sha256'])
 def test_source_prompt_and_queue_are_frozen(self):
  r=self.clone();p=r/'configs/prompts/short_0358.txt';p.write_text(p.read_text().rstrip())
  with self.assertRaisesRegex(ValueError,'text differs'):c.registry(r)
  r=self.clone();p=r/'configs/queue.json';j=c.read(p);j['finalize']=False;p.write_text(json.dumps(j))
  with self.assertRaisesRegex(ValueError,'finalize'):c.registry(r)
 def test_gate_allows_only_creation_timestamp(self):
  a=c.read(ROOT/'design/R89_ACTUAL/PAIR_RUNTIME_GATE.json');b=copy.deepcopy(a);b['created_unix']+=1;self.assertTrue(compare_parent_gate(b,a))
  for change in ('video','check','extra'):
   b=copy.deepcopy(a)
   if change=='video':b['runs']['forced']['video']['sha256']='different'
   elif change=='check':b['checks']['actual_clean_conditions_equal']=False
   else:b['extra_field']=1
   self.assertFalse(compare_parent_gate(b,a))
 def test_condition_only_known_provenance_renames_allowed(self):
  p=ROOT/'design/R89_ACTUAL/audit/r89_short_0358_seed2026101701_forced_conditioning.json';a=c.read(p);b=copy.deepcopy(a);b['run_id']='new'
  for key in ('source_run_id','source_manifest','source_manifest_sha256'):b['pair_snapshot'][key]='new'
  self.assertTrue(comparable_conditions(b,a))
  for key in ('prompt','input_video','conditioning_embedding','packed_layout','native_vae_calls','token_tags'):
   x=copy.deepcopy(b);x[key]='changed';self.assertFalse(comparable_conditions(x,a),key)
  b['pair_snapshot']['actual']['references'][0]['clean_latent']['sha256']='changed';self.assertFalse(comparable_conditions(b,a))
 def test_noise_copy_is_exact_and_rejects_changed_parent(self):
  d=tempfile.TemporaryDirectory();self.addCleanup(d.cleanup);base=Path(d.name);r=base/'new';old=base/'old'
  for p in (r/'audit',r/'configs',old/'audit'):p.mkdir(parents=True)
  content=b'actualAV';source=old/'audit/noise.pt';source.write_bytes(content)
  (r/'configs/parent_bindings.json').write_text(json.dumps({'parent_root':str(old),'noise_cache_relative':'audit/noise.pt','noise_cache_sha256':hashlib.sha256(content).hexdigest()}))
  with patch.object(runner,'ROOT',r):a=runner.prepare_original_noise();b=runner.prepare_original_noise()
  self.assertEqual(a,b);self.assertEqual(Path(a['destination']).read_bytes(),content)
  source.write_bytes(b'changed')
  with patch.object(runner,'ROOT',r),self.assertRaisesRegex(ValueError,'original R89'):runner.prepare_original_noise()
if __name__=='__main__':unittest.main()
