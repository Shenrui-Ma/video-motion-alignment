import ast,copy,gzip,hashlib,importlib.util,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
# Policy imports do not initialize the Comfy node or CUDA.
package=types.ModuleType('H3AutomaticWindowRouter');package.__path__=[str(ROOT/'extensions/H3AutomaticWindowRouter')];sys.modules.setdefault('H3AutomaticWindowRouter',package)
from H3AutomaticWindowRouter.geometry import Geometry
from H3AutomaticWindowRouter.selector import Controller
from arm_features import features
import centered_eligibility as h
import r86_contract as c
G=Geometry(1312,736,107,24,98)
def load(p):return json.loads(Path(p).read_text())
def arrays(source,target,g=G):return {(name,q):features(raw,g,q) for name,raw in [('source',source),('target',target)] for q in (.3,.5)}
def row(feature='left_arm_direction',window=(44,59),lag=15,gain=.7717598078189633):
 return {'window':list(window),'feature':feature,'baseline':'delayed_candidate' if lag>0 else 'advanced_candidate','status':'measured','min_gain':gain,'comparison':{str(q):{'proposal_lag':lag,'null_comparisons':[{'null_cost':1.,'proposal_cost':1.-gain} for _ in range(5)]} for q in (.3,.5)}}
class Centered(unittest.TestCase):
 def test_costs_and_compare_AST_equal_reviewed_helpers(self):
  for name,oldfile,new in [('costs','diagnose.py','costs'),('at','check_centered_support.py','at'),('compare','check_centered_support.py','compare')]:
   a=next(x for x in ast.parse((ROOT/'design'/oldfile).read_text().replace('d.costs','costs')).body if isinstance(x,ast.FunctionDef) and x.name==name)
   b=next(x for x in ast.parse((ROOT/'scripts/centered_eligibility.py').read_text()).body if isinstance(x,ast.FunctionDef) and x.name==new)
   self.assertEqual(ast.dump(a),ast.dump(b))
 def test_constant_offset_removed(self):
  a=np.arange(32,dtype=float).reshape(16,1,2)/10;w=np.ones((16,1));z=h.costs(a,a+np.array([.5,-.4]),w)
  self.assertGreater(z['weighted_direction_error'],.6);self.assertLess(z['centered_direction_error'],1e-14)
 def test_static_motion_has_no_centered_gain(self):
  a=np.zeros((30,4,2));b=a+.4;c=np.ones((30,4));z=h.compare((a,c),(b,c),[4,19],'left',5,.5)
  self.assertEqual(z['status'],'measured');self.assertEqual(z['min_centered_gain'],0.)
 def test_each_null_uses_its_own_common_support(self):
  rng=np.random.default_rng(3);a=rng.normal(size=(24,4,2));b=rng.normal(size=(24,4,2));c=np.ones((24,4));b[2,0]=np.nan
  z=h.compare((a,c),(b,c),[4,19],'left',3,.5)
  self.assertNotEqual(z['null_comparisons'][0]['coverage'],z['null_comparisons'][-1]['coverage'])
  x=z['null_comparisons'][0];t=np.arange(4,20);s,sc=h.at((a,c),t,[0,1]);p,pc=h.at((b,c),t+3,[0,1]);n,nc=h.at((b,c),t-2,[0,1]);v=np.isfinite(s).all(-1)&np.isfinite(p).all(-1)&np.isfinite(n).all(-1);w=np.where(v,np.minimum(np.minimum(sc,pc),nc),0)
  self.assertEqual(x['centered_proposal_cost'],h.costs(s,p,w)['centered_direction_error'])
 def test_insufficient_boundary_and_visibility_unknown(self):
  a=np.zeros((20,4,2));c=np.ones((20,4));self.assertEqual(h.compare((a,c),(a,c),[4,19],'left',12,.5)['status'],'unknown')
  a[:]=np.nan;self.assertEqual(h.compare((a,c),(a,c),[4,19],'left',3,.5)['status'],'unknown')
 def test_padding_excluded_by_existing_feature_domain(self):
  raw=load(ROOT/'tests/fixtures/centered/source.pose.json');changed=copy.deepcopy(raw)
  for f in changed['frames'][98:]:f['selected_person']=None
  a,b=arrays(raw,raw),arrays(changed,changed)
  for k in a:self.assertEqual(a[k]['arm_direction'].shape[0],98);np.testing.assert_equal(a[k]['arm_direction'],b[k]['arm_direction'])
 def test_actual_selected_candidates_1_3_4_kept_10_removed(self):
  source=load(ROOT/'tests/fixtures/centered/source.pose.json')
  specs=[(1,[44,59],'left_arm_direction',15,.7717598078189633,.5361359408618508,True),(3,[44,59],'right_arm_direction',14,.9211009775663938,.8321868441194711,True),(4,[40,55],'right_arm_direction',12,.9175034033404228,.886772827936381,True),(10,[4,19],'left_arm_direction',21,.5116731856735194,-2.5924554078163595,False)]
  for i,w,f,lag,gain,expected,accept in specs:
   obs={'windows':[row(f,w,lag,gain)]};before=copy.deepcopy(obs);a=arrays(source,load(ROOT/f'tests/fixtures/centered/index{i:02d}.pose.json'));result=h.apply(obs,a);d=result['centered_eligibility']['candidates'][0]
   self.assertAlmostEqual(d['centered_min_gain'],expected,places=12);self.assertEqual(d['accepted'],accept);self.assertEqual(obs,before);self.assertEqual(h.unfiltered(result),obs)
   if accept:self.assertEqual(result['windows'],obs['windows'])
 def test_strict_threshold_and_both_confidences(self):
  obs={'windows':[row()]};a={('source',q):{'arm_direction':None,'arm_conf':None} for q in (.3,.5)};a.update({('target',q):a['source',q] for q in (.3,.5)})
  for gain in (.5,.50000001):
   out={'status':'measured','min_raw_gain':obs['windows'][0]['min_gain'],'min_centered_gain':gain,'null_comparisons':[]}
   with patch.object(h,'compare',return_value=out):result=h.apply(obs,a)
   self.assertEqual(result['centered_eligibility']['candidates'][0]['accepted'],gain>.5)
  good={'status':'measured','min_raw_gain':obs['windows'][0]['min_gain'],'min_centered_gain':.9,'null_comparisons':[]};bad=dict(good,min_centered_gain=.4)
  with patch.object(h,'compare',side_effect=[good,bad]):self.assertEqual(h.apply(obs,a)['windows'][0]['status'],'unknown')
 def test_raw_gain_mismatch_is_error(self):
  a={('source',q):{'arm_direction':None,'arm_conf':None} for q in (.3,.5)};a.update({('target',q):a['source',q] for q in (.3,.5)})
  with patch.object(h,'compare',return_value={'status':'measured','min_raw_gain':.6,'min_centered_gain':.9}),self.assertRaises(ValueError):h.apply({'windows':[row()]},a)
 def test_original_controller_all20_actual_R81(self):
  old=load(ROOT/'design/R81_PARITY.json');c0=Controller(G,arm='visible_only');seen=[]
  for i in range(20):
   with gzip.open(ROOT/f'tests/fixtures/r81/step{i:03d}.json.gz','rt') as f:o=json.load(f)
   m={'status':'complete','physical_index':i,'request_sha256':'a'*64,'response_sha256':'b'*64,'observer':o};d=c0.select(i,m);expected=old['results']['visible_only'][i]
   self.assertEqual({k:d[k] for k in expected},expected);seen.append(i) if d['chosen_full'] else None
  self.assertEqual(seen,old['ON_indices']['visible_only'])
 def test_controller_and_attention_byte_identity(self):
  inherited=load(ROOT/'audit/INHERITANCE.json')['unchanged_numerics']
  for folder in ['automatic_window_policy.py','delayed_window_policy.py','selector.py','core.py','dynamic_support.py','geometry.py']:
   rel='extensions/H3AutomaticWindowRouter/'+folder;self.assertIn(rel,inherited);self.assertEqual(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest(),inherited[rel]['sha256'])
 def test_registry_actual_graph(self):
  jobs,order=c.registry();self.assertEqual(order,['r142_short_0252_seed2026101703_visible_only']);g=c.expected_graph();self.assertEqual(g['51']['inputs']['source_run_id'],g['5']['inputs']['run_id']);self.assertEqual(g['6']['inputs']['pair_id'],'r113_short_0252_seed2026101703')
 def test_full_rerun_and_predecessor_required(self):
  self.assertTrue(load(ROOT/'design/R142_PLAN.json')['full_rerun']);self.assertFalse((ROOT/'extensions/H3AutomaticWindowRouter/resume_state.py').exists());self.assertIn('predecessor_check()', (ROOT/'scripts/root_run_online.py').read_text())

 def test_actual_snapshot_node_graph_identifiers_and_tensors(self):
  import torch
  from H3PairAudit import H3PairConditionSnapshot, _tensor_info
  graph=c.expected_graph(); args=graph['51']['inputs']; emb=torch.arange(6,dtype=torch.float32).reshape(1,2,3);tags=torch.tensor([0,1]);ref=torch.arange(96,dtype=torch.float32).reshape(1,24,1,2,2)
  video=torch.zeros((1,24,2,2,2));audio=torch.zeros((1,32,2,3));pos=torch.arange(12,dtype=torch.float32).reshape(4,3)
  class Layout:
   def __init__(self,*a,**kw):self.seq_len=4;self.segments=[('text',0,2),('video',2,4)];self.position_ids=pos
  module=types.ModuleType('comfy.ldm.minimax.model');module.PackedLayout=Layout
  modules={name:types.ModuleType(name) for name in ['comfy','comfy.ldm','comfy.ldm.minimax']};modules['comfy.ldm.minimax.model']=module
  positive=[[emb,{'minimax_token_tags':tags,'minimax_refs':[{'kind':'video','latent':ref,'latent_t':1,'latent_h':2,'latent_w':2}]}]]
  target={'samples':types.SimpleNamespace(unbind=lambda:(video,audio))}
  common={'schema':'h3-event-audit-v1','run_id':args['source_run_id'],'conditioning_embedding':_tensor_info(emb),'token_tags':_tensor_info(tags),'native_vae_calls':[{'latent':_tensor_info(ref)}],'target_latent_shapes':[list(video.shape),list(audio.shape)],'packed_layout':{'seq_len':4,'segments':[['text',0,2],['video',2,4]],'position_ids':_tensor_info(pos)}}
  with tempfile.TemporaryDirectory() as d,patch.dict(sys.modules,modules),patch.object(c,'audit_dir',return_value=Path(d)):
   (Path(d)/(args['source_run_id']+'_conditioning.json')).write_text(json.dumps(common))
   out=H3PairConditionSnapshot().snapshot(positive,target,d,args['source_run_id'],args['run_id'])
   self.assertIs(out[0],positive);self.assertIs(out[1],target)
   manifest=load(Path(d)/(args['run_id']+'_conditioning.json'));self.assertTrue(manifest['pair_snapshot']['verified']);self.assertEqual(manifest['run_id'],args['run_id'])
   with self.assertRaisesRegex(ValueError,'source-conditioning identity'):H3PairConditionSnapshot().snapshot(positive,target,d,'r123_short_0252_shared',args['run_id'])
   with self.assertRaises(ValueError):H3PairConditionSnapshot().snapshot(positive,target,d,args['source_run_id'],'r133_short_0252_seed2026101703_visible_only')
   changed=copy.deepcopy(positive);changed[0][0]=emb+1
   with self.assertRaisesRegex(ValueError,'embedding'):H3PairConditionSnapshot().snapshot(changed,target,d,args['source_run_id'],args['run_id'])


 def test_actual_scan_all_rows_matches_root_replay(self):
  from scan_current_pose import observe
  expected={x['index']:x for x in load(ROOT/'design/offline_replay/RESULT.json')['rows']}
  for index in (1,3,4,10):
   obs=observe(ROOT/'tests/fixtures/centered/source.pose.json',ROOT/f'tests/fixtures/centered/index{index:02d}.pose.json',index,G)
   got=obs['centered_eligibility'];old=expected[index]
   self.assertEqual(got['accepted'],old['accepted_count']);self.assertEqual(got['rejected'],old['rejected_count'])
   for actual,prior in zip(got['candidates'],old['candidates']):
    for key in ['window','feature','lags','original_min_gain','centered_min_gain','accepted']:self.assertEqual(actual[key],prior[key])
 def test_historical_gate_diagnostics_do_not_weaken_same_run(self):
  core=(ROOT/'extensions/H3AutomaticWindowRouter/core.py').read_text()
  self.assertIn('condition_after != s.initial_condition',core);self.assertIn('readout.tensor_signature(x) != input_sig',core)
  self.assertIn('global_rng_unchanged',core)
  text=(ROOT/'scripts/verify_decisions.py').read_text();self.assertIn("row['same_input'] == native['same_input']",text)
  self.assertIn("actual_initial_AV_noise_exact",text)
 def test_all_extension_run_ids_resolve_actual_registry(self):
  for p in (ROOT/'extensions').rglob('*.py'):
   self.assertNotIn('r133_',p.read_text(),str(p));self.assertNotIn('r123_',p.read_text(),str(p))
  graph=c.expected_graph()
  for nid in ['6','51','52']:self.assertEqual(graph[nid]['inputs']['run_id'],c.RUN)
  self.assertEqual(graph['50']['inputs']['run_id'],c.RUN)

if __name__=='__main__':unittest.main()
