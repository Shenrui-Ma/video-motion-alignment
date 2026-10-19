import ast,copy,json,shutil,sys,tempfile,unittest
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r91_contract as c,input_contract as inp,execution_gate as gate
class Inputs(unittest.TestCase):
 def test_root_candidate_prompt_bytes_and_both_arms(self):
  jobs,order=c.registry();proposal={x['source_id']:x for x in c.read(ROOT/'design/PROPOSAL.json')['items']}
  self.assertEqual(len(order),4)
  for n,f in zip(order[::2],order[1::2]):
   a=jobs[n]['case'];b=jobs[f]['case'];sid=a['source_id'];self.assertEqual(a['prompt'],b['prompt']);self.assertEqual(c.sha(ROOT/'configs/prompts'/(sid+'.txt')),proposal[sid]['prompt_sha256']);self.assertIn(proposal[sid]['official_task']['edit_prompt'],a['prompt'])
 def test_actual_root_rational_mapping_and_padding(self):
  original={x['source_id']:x for x in c.read(ROOT/'design/INPUT_PLAN.json')['cases']}
  for row in c.read(ROOT/'design/EXECUTION_INPUT_PLAN.json')['pairs']:
   sid=row['source_id'];clip=row['clip'];ip=row['input_protocol'];pts=row['source']['actual_pts_rational'];valid=ip['effective_frame_count'];total=ip['h3_frame_count']
   self.assertEqual(inp.clip_valid_count(clip['start_pts_rational'],clip['end_exclusive_rational']),valid)
   mapping=inp.clip_nearest_map(pts,clip['start_frame'],clip['end_frame_inclusive'],valid)+[clip['end_frame_inclusive']]*(total-valid)
   self.assertEqual(mapping,original[sid]['input_to_original_frame']);self.assertEqual(mapping,ip['input_to_original_frame']);self.assertTrue(all(x<original[sid]['clip_original_frame_interval_half_open'][1] for x in mapping))
 def test_tie_goes_to_earlier_original_frame(self):self.assertEqual(inp.clip_nearest_map(['0','1/12'],0,1,2),[0,0])
 def test_shapes_match_pinned_official_function(self):
  source=ast.parse((ROOT/'source_snapshot/nodes_minimax_h3.py').read_text());names={'align_frame_count','video_latent_t','temporal_shape'}
  # Actual helper name comes from the pinned source; include all functions called by temporal_shape.
  funcs=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in names|{'normalize_frame_count'}]
  env={'FPS':24,'AUDIO_LATENT_FPS':40}
  exec(compile(ast.Module(body=funcs,type_ignores=[]),'official temporal helpers','exec'),env)
  for sid,(total,valid) in c.SOURCE_LENGTHS.items():
   frames,t,a=env['temporal_shape'](total);self.assertEqual(frames,total);self.assertEqual((t,a),(c.latent_shapes({'source_id':sid})['video'][2],c.latent_shapes({'source_id':sid})['audio'][-1]))
 def test_pure_padding_bins_native_and_shared_boundary_explicit(self):
  a=c.routing_layout({'source_id':'short_0114'});b=c.routing_layout({'source_id':'long_0039'})
  self.assertEqual(a['latent_interval_half_open'],[0,32]);self.assertEqual(a['position_bin_coverage_inclusive'],[0,106]);self.assertEqual(a['pure_pad_bins'],[])
  self.assertEqual(b['latent_interval_half_open'],[0,43]);self.assertEqual(b['position_bin_coverage_inclusive'],[0,144]);self.assertEqual(b['pure_pad_bins'],[43,44,45,46])
 def test_original_lfs_proof_matches_all_source_bytes(self):
  proof=c.read(ROOT/'configs/source_selection/OFFICIAL_SOURCE_RECEIPTS.json')
  for sid in c.SOURCES:
   d=proof[sid];oid=d['official_file']['lfs']['oid'] if sid=='short_0114' else d['download']['official_lfs']['oid'];self.assertEqual(c.sha(ROOT/'inputs'/(sid+'_original.mp4')),oid)
 def test_generated_h264_pixel_md5_mapping_exact(self):
  for sid in c.SOURCES:
   p=c.read(ROOT/'inputs'/(sid+'_provenance.json'));self.assertTrue(p['decoded_pixel_mapping_exact']);self.assertEqual(p['input_frame_md5'],[p['original_transformed_frame_md5'][i] for i in p['input_to_original_frame']]);self.assertEqual(p['evaluate_indices'],list(range(c.SOURCE_LENGTHS[sid][1])))
class StableReviewedGate(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.path=Path(self.t.name)/'PAIR_RUNTIME_GATE.json';self.original={'passed':True,'created_unix':1,'runs':{'native':{'video':{'sha256':'abc'}}},'checks':{'prefix':True}}
 def test_first_persist_and_reverify_only_timestamp_preserves_raw_bytes(self):
  gate.persist_pair_gate(self.path,self.original);before=self.path.read_bytes();changed=copy.deepcopy(self.original);changed['created_unix']=999;got=gate.persist_pair_gate(self.path,changed)
  self.assertEqual(self.path.read_bytes(),before);self.assertEqual(got,self.original)
 def test_any_nested_or_added_content_change_refuses_overwrite(self):
  gate.persist_pair_gate(self.path,self.original);before=self.path.read_bytes()
  for change in ('video','nested_timestamp','failed','extra'):
   d=copy.deepcopy(self.original)
   if change=='video':d['runs']['native']['video']['sha256']='bad'
   elif change=='nested_timestamp':d['runs']['native']['created_unix']=1
   elif change=='failed':d['passed']=False
   else:d['extra']='unexpected'
   with self.assertRaisesRegex(ValueError,'evidence changed'):gate.persist_pair_gate(self.path,d)
   self.assertEqual(self.path.read_bytes(),before)
if __name__=='__main__':unittest.main()
