import copy,hashlib,json,math,sys,tempfile,unittest,uuid
from pathlib import Path
import torch
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'scripts'),str(R/'extensions')]
from H3StaticWindowRouter.static_plan import StaticPlan
from H3StaticWindowRouter.dynamic_support import make_gain
from H3StaticWindowRouter.dependencies import router,readout
from H3StaticWindowRouter.pair_gate import actual_prefix,canonical_condition
from r39_contract import expected_graph,validate_job,RUN_ID

def dense(q,k,v):
 l=q@k.transpose(-1,-2)/math.sqrt(q.shape[-1]);return l.softmax(-1)@v,l.logsumexp(-1).float()
class StaticTests(unittest.TestCase):
 def test_exact_static_order_budget_and_no_observation(self):
  c=StaticPlan();ds=[c.select(i) for i in range(20)];self.assertEqual([i for i,v in enumerate(ds) if v['chosen_full']],[2,4,5,6]);self.assertEqual(ds[4]['latent_bins'],list(range(42)));self.assertTrue(all(not v['online_observation'] for v in ds));self.assertEqual(sum(len(v['latent_bins'])*943*50 for v in ds),7921200)
  with self.assertRaises(ValueError):c.select(19)
  with self.assertRaises(ValueError):StaticPlan().select(1)
 def test_dense_oracle_both_locations_and_zero(self):
  q=torch.sin(torch.arange(1*2*84*3,dtype=torch.float64).reshape(1,2,84,3)/23);k=torch.cos(q);v=q.sin();before=[x.clone() for x in (q,k,v)];rng=torch.get_rng_state().clone();plan={'seq_len':84,'frame_rows':1,'latent_interval_half_open':[0,42],'query_interval_half_open':[42,84],'reference_video_segment':[0,42]}
  native,_=dense(q,k,v);native=native.transpose(1,2).reshape(1,84,6)
  for bins in ([],list(range(13,18)),list(range(42))):
   out=router.route_attention(q,k,v,2,plan,mode='mass_preserve',query_gain=make_gain(bins,(1,1)),attention=dense)
   selected=[42+b for b in bins];other=[i for i in range(84) if i not in selected];self.assertTrue(torch.equal(out[:,other],native[:,other]))
   expected=native.clone();prob=(q@k.transpose(-1,-2)/math.sqrt(3)).softmax(-1)
   for b in bins:
    i=42+b;m=prob[:,:,i,:42].sum(-1,keepdim=True);ref=(prob[:,:,i,:42].unsqueeze(-1)*v[:,:,:42]).sum(-2)/m;aligned=v[:,:,b];correction=m*(aligned-ref);row=native[:,i].reshape(1,2,3);expected[:,i]=(row+correction).reshape(1,6)
   self.assertTrue(torch.allclose(out,expected,atol=2e-7,rtol=2e-6))
  self.assertTrue(torch.equal(rng,torch.get_rng_state()));self.assertTrue(all(torch.equal(a,b) for a,b in zip(before,(q,k,v))))
 def test_invalid_bin_mask_rejected(self):
  for value in ([23,23],[24,23],[-1],[42],[23.0]):
   with self.assertRaises(ValueError):make_gain(value)
 def test_only_two_consistent_UUID_leaves_ignored(self):
  a={'original':{'positive':[{'uuid':str(uuid.uuid4()),'x':1}]},'processed':{'positive':[{'uuid':'','x':2}]}};a['processed']['positive'][0]['uuid']=a['original']['positive'][0]['uuid'];b=copy.deepcopy(a);u=str(uuid.uuid4());b['original']['positive'][0]['uuid']=u;b['processed']['positive'][0]['uuid']=u;self.assertEqual(canonical_condition(a),canonical_condition(b));b['processed']['positive'][0]['x']=3;self.assertNotEqual(canonical_condition(a),canonical_condition(b));b['original']['positive'][0]['uuid']=str(uuid.uuid4())
  with self.assertRaises(ValueError):canonical_condition(b)
 def test_actual_graph_and_actual_parent_tree_binding(self):
  validate_job(RUN_ID);g=json.loads((R/'configs/graphs'/f'{RUN_ID}.json').read_text());self.assertEqual(g,expected_graph());self.assertEqual(g['50']['class_type'],'H3StaticWindowRouter');self.assertEqual(g['6']['inputs']['noise_seed'],2026101701)
  tree=json.loads((R/'configs/parent_counterfactual.json').read_text())['counterfactual']['conditioning']['tree'];self.assertEqual(canonical_condition(tree),canonical_condition(copy.deepcopy(tree)))
  from H3StaticWindowRouter import transport
  transport.bindings()
 def test_prefix_tensor_and_metadata_corruptions(self):
  from H3StaticWindowRouter.pair_gate import FIELDS
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);a=torch.zeros((1,24,42,46,82));b=torch.ones((1,32,2,235))/4;sig=[readout.tensor_signature(v) for v in (a,b)];raw=[readout.tensor_signature(a),readout.tensor_signature(b*4)]
   row={'physical_index':2,'branch':'native','nfe_index':2,'seed':2026101701,'sigma':.99,'sigma_next':.98,'normalized_stream_signatures':sig,'raw_stream_signatures':raw,'condition_sha256':'condition','reference_sha256':'reference','same_input':{'sha256':'state'}}
   old=d/'old.pt';now=d/'now.pt';value={'video':a,'audio':b,'metadata':{k:row[k] for k in FIELDS}};torch.save(value,old);torch.save(value,now)
   row['file_sha256']=hashlib.sha256(old.read_bytes()).hexdigest();expected={'index':2,'path':str(old),'file_sha256':row['file_sha256'],'branch_record':copy.deepcopy(row)}
   self.assertTrue(actual_prefix(row,expected,now)['actual_tensor_equal'])
   for key,val in [('branch','full'),('physical_index',3),('seed',1),('nfe_index',5),('same_input',{'sha256':'other'})]:
    bad=copy.deepcopy(row);bad[key]=val
    with self.assertRaises(ValueError):actual_prefix(bad,expected,now)
   bad=copy.deepcopy(value);bad['audio']=bad['audio']*4;torch.save(bad,now)
   with self.assertRaises(ValueError):actual_prefix(row,expected,now)
   torch.save(value,now);e=copy.deepcopy(expected);e['file_sha256']='wrong'
   with self.assertRaises(ValueError):actual_prefix(row,e,now)
class TransactionNegativeTests(unittest.TestCase):
 def test_failed_native_transaction_is_not_silently_integrated(self):
  from unittest.mock import patch
  from counterfactual_support import execute
  from H3StaticWindowRouter.core import Config,State
  import H3StaticWindowRouter.core as c
  class TinyConfig(Config):
   @property
   def shapes(self):return ((1,24,42,2,2),(1,32,2,3))
  class Gate:
   def begin(self,*a):pass
   def branch(self,*a):pass
   def decision(self,*a):pass
   def finish(self,*a):pass
  for failure in ('double_forward','rng','timestep_mutation','grid_mutation','input_mutation','condition_mutation','wrong_sigma','duplicate_prediction','duplicate_callback'):
   with self.subTest(failure=failure),tempfile.TemporaryDirectory() as d:
    cfg=TinyConfig('negative',d);state=State({'refs':[]},torch.zeros(cfg.shapes[0]),cfg);state.pair_gate=Gate()
    state.plan_for=lambda _:{'seq_len':84,'frame_rows':1,'latent_interval_half_open':[0,42],'query_interval_half_open':[42,84],'reference_video_segment':[0,42]}
    with patch.object(c,'make_gain',lambda bins:make_gain(bins,(1,1))):
     with self.assertRaises(ValueError):execute(state,fail=failure)
    self.assertEqual(state.audit['status'],'failed');self.assertTrue(state.finished)
 def test_extra_full_at_wrong_index_is_rejected(self):
  from H3StaticWindowRouter.core import Config,State
  class TinyConfig(Config):
   @property
   def shapes(self):return ((1,24,42,2,2),(1,32,2,3))
  with tempfile.TemporaryDirectory() as d:
   cfg=TinyConfig('authorization',d);state=State({'refs':[]},torch.zeros(cfg.shapes[0]),cfg);state.entered=True;state.callback_count=3
   state.transaction={'physical_index':3,'branches':[{'branch':'native'}],'decision':{'chosen_full':True}}
   state.active_bins=list(range(42));state.query_gain=make_gain(state.active_bins,(1,1))
   with self.assertRaises(ValueError):state.authorize(3,'full')
if __name__=='__main__':unittest.main()
