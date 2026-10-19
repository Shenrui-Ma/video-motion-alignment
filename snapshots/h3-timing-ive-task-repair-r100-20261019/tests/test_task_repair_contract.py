import ast,copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r100_contract as c,input_contract as inp
class TaskRepairContract(unittest.TestCase):
 def test_two_registered_user_failed_tasks(self):
  jobs,order=c.registry();self.assertEqual(c.SOURCES,('short_0114','short_0392'));self.assertEqual(len(order),4)
  self.assertEqual([jobs[x]['source_id'] for x in order],['short_0114']*2+['short_0392']*2)
  self.assertEqual([(jobs[x]['case']['geometry']['frames'],jobs[x]['case']['valid_frame_count']) for x in order],[(107,105)]*2+[(73,57)]*2)
 def test_0114_prompt_exact_original_r91_and_graph_science(self):
  old=ROOT/'source_snapshot/r91_parent';self.assertEqual(c.sha(ROOT/'configs/prompts/short_0114.txt'),c.sha(old/'design/short_0114_P1_candidate.txt'))
  for arm in ('native','forced'):
   run=f'r100_short_0114_seed2026101701_{arm}';g=c.read(ROOT/'configs/graphs'/(run+'.json'));b=c.read(old/'configs/graphs'/f'r91_short_0114_seed2026101701_{arm}.json')
   # Only storage roots and identifiers differ; every numeric/model/prompt field is tested.
   oldroot='/data5/researcher/h3_runs/timing_ive_object_control_r91_20261018';newroot=c.read(ROOT/'configs/runtime.json')['remote_root']
   expected=json.loads(json.dumps(b).replace(oldroot,newroot).replace('r91_short_0114','r100_short_0114'))
   self.assertEqual(g,expected)
 def test_six_numerical_modules_exact_and_original_parent_seals(self):
  for rel,row in c.read(ROOT/'configs/runtime_kernel_hashes.json').items():self.assertEqual(c.sha(ROOT/rel),row['current_sha256']);self.assertEqual(row['parent_sha256'],row['current_sha256']);self.assertTrue(row['byte_equal'])
  for folder in ['r91_parent','r92_parent']:
   parent=ROOT/'source_snapshot'/folder;seal=c.read(parent/'deploy_manifest.json')
   for file in parent.rglob('*'):
    if file.is_file() and file.name!='deploy_manifest.json':self.assertEqual(c.sha(file),seal['files'][str(file.relative_to(parent))]['sha256'])
 def test_graph_pair_only_attention_mode_and_run_identity(self):
  jobs,order=c.registry()
  for n,f in zip(order[::2],order[1::2]):
   a=c.read(ROOT/'configs/graphs'/(n+'.json'));b=c.read(ROOT/'configs/graphs'/(f+'.json'));b=json.loads(json.dumps(b).replace(f,n));b['50']['inputs']['mode']='native';self.assertEqual(a,b)
 def test_source_file_bytes_provenance_and_all_mapped_pixels(self):
  rows=c.read(ROOT/'design/INPUT_PLAN.json')['pairs']
  for row in rows:
   s=row['pair_id'];p=c.read(ROOT/'inputs'/(s+'_provenance.json'));self.assertEqual(c.sha(ROOT/'inputs'/(s+'_original.mp4')),row['source']['sha256']);self.assertEqual(c.sha(ROOT/'inputs'/(s+'_video.mp4')),p['video_sha256']);self.assertEqual(p['input_frame_md5'],[p['original_transformed_frame_md5'][i] for i in p['input_to_original_frame']]);self.assertEqual(p['evaluate_indices'],list(range(c.SOURCE_LENGTHS[s][1])))
 def test_actual_physical_mapping_and_padding(self):
  for row in c.read(ROOT/'design/INPUT_PLAN.json')['pairs']:
   s=row['pair_id'];a=row['clip'];t,n=c.SOURCE_LENGTHS[s];mapping=inp.clip_nearest_map(row['source']['actual_pts_rational'],a['start_frame'],a['end_frame_inclusive'],n);self.assertEqual(inp.clip_valid_count(a['start_pts_rational'],a['end_exclusive_rational']),n);self.assertEqual(mapping+[a['end_frame_inclusive']]*(t-n),row['input_protocol']['input_to_original_frame'])
 def test_shapes_match_actual_pinned_code(self):
  p=ROOT/'source_snapshot/nodes_minimax_h3.py';nodes=[n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in {'align_frame_count','normalize_frame_count','video_latent_t','temporal_shape'}];e={'FPS':24,'AUDIO_LATENT_FPS':40};exec(compile(ast.Module(body=nodes,type_ignores=[]),'official','exec'),e)
  for s,(t,n) in c.SOURCE_LENGTHS.items():self.assertEqual(e['temporal_shape'](t),(t,c.latent_shapes({'source_id':s})['video'][2],c.latent_shapes({'source_id':s})['audio'][-1]))
 def test_tie_earlier_and_time_coverage(self):self.assertEqual(inp.clip_nearest_map(['0','1/12'],0,1,2),[0,0])
 def test_full_six_section_prompt_and_official_task(self):
  for sid in c.SOURCES:
   p=(ROOT/'configs/prompts'/(sid+'.txt')).read_text()
   for text in ['subject_definitions:','summary:','retention_analysis:','detailed_description:','overall_soundscape:','non_diegetic_music:','<Subject 1>','<Subject 2>','<Video 1>','[Shot 1]','[video editing]']:self.assertIn(text,p)
   self.assertEqual(p.count('Requested edit:'),1)
  p=(ROOT/'configs/prompts/short_0392.txt').read_text();self.assertIn('Remove the ornate fireplace',p);self.assertIn('entire ornate fireplace',p);self.assertIn('hand-gesture sequence',p);self.assertIn('original timing',p)
 def test_fixed_runtime_and_no_launch(self):
  r=c.read(ROOT/'configs/runtime.json');self.assertEqual((r['gpu_uuid'],r['expected_gpu_index'],r['port']),('GPU-REDACTED',0,8564));self.assertEqual(r['host'],'H3_SERVER_A');self.assertEqual(r['uid'],1016);self.assertEqual((r['memory_mode'],r['reserve_vram']),('normal',8));self.assertFalse(c.read(ROOT/'configs/admission.json')['ready_for_launch']);self.assertFalse((ROOT/'processes/service.json').exists())
 def test_prompt_mutation_rejected(self):
  old=c.read
  def changed(p):
   x=old(p)
   if Path(p).name=='scientific_contract.json':x['cases'][0]['prompt']+=' new action'
   return x
  with patch.object(c,'read',side_effect=changed):
   with self.assertRaisesRegex(ValueError,'prompt'):c.registry()
 def test_route_scope_mutation_rejected(self):
  old=c.read
  def changed(p):
   x=old(p)
   if Path(p).name=='r100_short_0392_seed2026101701_forced.json':x['50']['inputs']['end_frame']=72
   return x
  with patch.object(c,'read',side_effect=changed):
   with self.assertRaisesRegex(ValueError,'graph numerical'):c.registry()
if __name__=='__main__':unittest.main()
