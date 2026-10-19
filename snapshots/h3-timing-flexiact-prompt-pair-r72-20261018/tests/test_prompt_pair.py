import copy,json,os,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r72_contract as c,preflight,execution_gate as g,service,resource_gate
class Contracts(unittest.TestCase):
 def test_static_contract(self):
  r=preflight.check();self.assertTrue(r['passed']);self.assertEqual(r['sources'],2);self.assertEqual(r['route_steps'],[])
 def test_graph_only_prompt_science_diff(self):
  jobs,order=c.registry();a,b=[c.read(ROOT/'configs/graphs'/(n+'.json')) for n in order[:2]]
  self.assertNotEqual(a['5']['inputs']['prompt'],b['5']['inputs']['prompt'])
  self.assertNotEqual(a['5']['inputs']['run_id'],b['5']['inputs']['run_id'])
  self.assertEqual(a['6']['inputs']['pair_id'],b['6']['inputs']['pair_id'])
  for n in ('5','6','50','51','52'):a[n]['inputs']['run_id']=b[n]['inputs']['run_id']='RUN'
  a['51']['inputs']['source_run_id']=b['51']['inputs']['source_run_id']='SOURCE'
  a['14']['inputs']['filename_prefix']=b['14']['inputs']['filename_prefix']='RUN'
  a['5']['inputs']['prompt']=b['5']['inputs']['prompt']='PROMPT'
  self.assertEqual(a,b)
 def test_p1_verbatim_template_and_roles(self):
  for pair in c.PAIR_KEYS:
   d=next(x for x in c.definitions() if x['pair_key']==pair);prompts=c.prompt_values(pair=pair)
   self.assertEqual(prompts['p1'],(ROOT/'design/P1_TEMPLATE.txt').read_text().format(**d['p1_fields']))
   for token in ('subject_definitions:','summary:','retention_analysis:','detailed_description:','overall_soundscape:','non_diegetic_music:','[reference generation]','<Picture 1>','<Video 1>'):self.assertIn(token,prompts['p1'])
   self.assertIn('appearance and the scene come from <Picture 1>',prompts['p1'])
 def test_noise_shared_within_pair_text_cache_separate(self):
  jobs,order=c.registry();graphs=[c.read(ROOT/'configs/graphs'/(n+'.json')) for n in order]
  self.assertEqual(len({g['5']['inputs']['run_id'] for g in graphs}),4)
  self.assertEqual(graphs[0]['6']['inputs']['pair_id'],graphs[1]['6']['inputs']['pair_id'])
  self.assertEqual(graphs[2]['6']['inputs']['pair_id'],graphs[3]['6']['inputs']['pair_id'])
  self.assertNotEqual(graphs[0]['6']['inputs']['pair_id'],graphs[2]['6']['inputs']['pair_id'])
 def test_changed_prompt_refused(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);shutil.copytree(ROOT/'configs',root/'configs');shutil.copytree(ROOT/'design',root/'design')
   p=root/'configs/prompts/fitness__game_man_5_p1.txt';p.write_text(p.read_text()+' Hold the arms higher.')
   with self.assertRaisesRegex(ValueError,'frozen prompt changed'):c.registry(root)
 def test_changed_seed_refused(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);shutil.copytree(ROOT/'configs',root/'configs');shutil.copytree(ROOT/'design',root/'design')
   p=root/'configs/scientific_contract.json';v=c.read(p);v['cases'][1]['seed']+=1;p.write_text(json.dumps(v))
   with self.assertRaisesRegex(ValueError,'pair/seed'):c.registry(root)
 def test_six_numerical_files_match_frozen_parent_hashes(self):
  rows=c.read(ROOT/'configs/runtime_kernel_hashes.json');self.assertEqual(len(rows),6)
  for name,row in rows.items():
   self.assertEqual(c.sha(ROOT/name),row['current_sha256'],name);self.assertEqual(row['current_sha256'],row['parent_sha256'],name);self.assertTrue(row['byte_equal'])
 def test_gate_requires_actual_root_approval_and40gib(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'configs').mkdir();p=root/'configs/runtime.json';p.write_text(json.dumps({'gpu_uuid':'GPU-test'}));order=['p0','p1','next_p0','next_p1']
   with patch.object(g,'registry',return_value=({},order)):
    with self.assertRaises(FileNotFoundError):g.admitted_job('p0',root)
    a={'schema':'r72-first-pair-capacity-trial-v1','root_approved':True,'runtime_profile_sha256':c.sha(p),'main_gpu_uuid':'GPU-test','allowed_runs':order[:2],'required_free_bytes':40*1024**3,'reserve_vram_gib':8,'capacity_status':'ACTUAL_FULL_TRAJECTORY_PENDING'}
    g.atomic(root/'audit/ROOT_FIRST_PAIR_APPROVAL.json',a);self.assertTrue(g.admitted_job('p0',root));self.assertTrue(g.admitted_job('p1',root));self.assertFalse(g.admitted_job('next_p0',root))
    a['required_free_bytes']-=1;g.atomic(root/'audit/ROOT_FIRST_PAIR_APPROVAL.json',a)
    with self.assertRaisesRegex(ValueError,'headroom'):g.approval(root)
 def test_continuation_bound_to_actual_first_pair_gate(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'configs').mkdir();runtime=root/'configs/runtime.json';runtime.write_text('{}');order=['a','b','c','d'];digest=c.sha(runtime)
   gate=root/'analysis/postrun/fitness__game_man_5/PAIR_RUNTIME_GATE.json'
   a={'allowed_runs':order[:2],'runtime_profile_sha256':digest}
   with patch.object(g,'approval',return_value=a),patch.object(g,'registry',return_value=({},order)):
    self.assertFalse(g.admitted_job('c',root))
    g.atomic(gate,{'passed':True,'runtime_profile_sha256':digest,'source_id':'fitness__game_man_5'})
    receipt={'root_approved':True,'schema':'r72-continue-after-first-pair-v1','runtime_profile_sha256':digest,'pair_gate_sha256':c.sha(gate),'allowed_runs':order[2:]}
    g.atomic(root/'audit/CONTINUE_AFTER_FIRST_PAIR.json',receipt);self.assertTrue(g.admitted_job('d',root))
    g.atomic(gate,{'passed':False,'runtime_profile_sha256':digest,'source_id':'fitness__game_man_5'})
    with self.assertRaisesRegex(ValueError,'evidence changed'):g.admitted_job('c',root)
    receipt['pair_gate_sha256']=c.sha(gate);g.atomic(root/'audit/CONTINUE_AFTER_FIRST_PAIR.json',receipt)
    with self.assertRaisesRegex(ValueError,'evidence incomplete'):g.admitted_job('c',root)
 def test_reference_count_and_image_bytes_bound(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   for name in ('configs','design','inputs'):shutil.copytree(ROOT/name,root/name)
   jobs,order=c.registry(root);p=root/'inputs'/jobs[order[0]]['case']['portrait'];p.write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'input changed: portrait'):c.validate_job(order[0],root)
   p=root/'configs/scientific_contract.json';v=c.read(p);v['cases'][0]['reference_image_count']=0;p.write_text(json.dumps(v))
   with self.assertRaisesRegex(ValueError,'reference/input'):c.registry(root)
 def test_foreign_three_cards_not_counted_as_own_cap(self):
  uid=os.getuid();peer={'uid':uid,'start_ticks':'42','cmdline_sha256':'peer'};rows=[{'gpu_uuid':'GPU-other'+str(i),'pid':i} for i in range(1,4)]+[{'gpu_uuid':'GPU-peer','pid':4}]
  a={'permitted_compute_processes':[{'pid':4,'identity':peer}]}
  with patch.object(resource_gate,'admission_document'),patch.object(service,'proc_uid',side_effect=lambda p:uid if p==4 else uid+1),patch.object(service,'external_identity',return_value=peer):
   service.check_admission(a,rows,{'queue_running':[],'queue_pending':[]})
 def test_unregistered_own_peer_refused(self):
  with patch.object(resource_gate,'admission_document'),patch.object(service,'proc_uid',return_value=os.getuid()),patch.object(service,'external_identity',return_value={'uid':os.getuid()}):
   with self.assertRaisesRegex(RuntimeError,'Unexpected own'):service.check_admission({'permitted_compute_processes':[]},[{'gpu_uuid':'GPU-peer','pid':4}],{'queue_running':[],'queue_pending':[]})
if __name__=='__main__':unittest.main()
