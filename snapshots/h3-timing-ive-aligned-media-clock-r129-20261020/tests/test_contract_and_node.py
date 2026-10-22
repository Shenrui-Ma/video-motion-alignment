import copy,importlib,importlib.util,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions'),str(ROOT/'analysis/postrun')]
import r129_contract as contract
import H3TemporalRouter as node
from verify_aligned import clean_condition,check_alignment
from test_alignment import fixture,alignment

class ContractTests(unittest.TestCase):
 def test_actual_graph_and_prompt_are_R122_with_one_intervention(self):
  jobs,order=contract.registry();self.assertEqual(order,[contract.RUN_ID]);self.assertEqual(jobs[order[0]]['arm'],'aligned')
  self.assertEqual(contract.read(ROOT/'configs/graphs'/f'{order[0]}.json'),contract.expected_graph(ROOT))
 def test_graph_change_outside_intervention_rejected(self):
  original=contract.read
  def changed(path):
   x=original(path)
   if Path(path).parent.name=='graphs':x['9']['inputs']['sigmas']='1,0'
   return x
  with mock.patch.object(contract,'read',side_effect=changed),self.assertRaisesRegex(ValueError,'graph differs'):contract.registry()
 def test_no_extra_forward_or_observer(self):
  from preflight import check
  self.assertTrue(check()['passed']);self.assertEqual(check()['NFE'],20)
 def test_original_position_condition_is_not_exempted(self):
  original=contract.read(ROOT/'design/r122_long_0039_shared_conditioning.json');other=copy.deepcopy(original);other['run_id']='new';other['pair_snapshot']={'arbitrary':'admin'}
  self.assertEqual(clean_condition(original),clean_condition(other));other['packed_layout']['position_ids']['sha256']='f'*64;self.assertNotEqual(clean_condition(original),clean_condition(other))
 def test_noise_is_exact_actual_file(self):
  science=contract.read(ROOT/'configs/scientific_contract.json');self.assertEqual(science['parent_noise_sha256'],'149c638af54913020b9c3f49c5625aba8a44efa3e326738834f6be9e87a1f943');self.assertIn('r122_long_0039_seed2026101701_noise.pt',science['parent_noise_file'])
 def test_alignment_gate_rejects_missing_step_or_block(self):
  meta,layout,_=fixture();_,details=alignment.aligned_positions(layout,meta)
  a={'schema':'h3-r129-aligned-media-clock-v1','run_id':contract.RUN_ID,'enabled':True,'status':'complete','completed_sampling_steps':20,'completed_calls':1000,'calls_by_block':[20]*50,'calls_by_forward':[50]*20,'rotation_table_builds':1,'first_six_prediction_equality_required':False,'layout':details}
  self.assertTrue(check_alignment(a,contract.RUN_ID,details['original_position_sha256']))
  for field,value in [('completed_calls',999),('calls_by_block',[20]*49+[19]),('calls_by_forward',[50]*19+[49]),('rotation_table_builds',20),('first_six_prediction_equality_required',True)]:
   b=copy.deepcopy(a);b[field]=value
   with self.subTest(field=field),self.assertRaises(ValueError):check_alignment(b,contract.RUN_ID,details['original_position_sha256'])

class NodeTests(unittest.TestCase):
 def setUp(self):
  meta,self.layout,_=fixture();self.meta=meta
  class Diffusion:
   patch_size=(1,2,2);latents_dim=24;blocks=[None]*50
  self.Diffusion=Diffusion;d=Diffusion()
  class Model:
   model_options={}
   def __init__(self):self.patches={}
   def get_model_object(self,name):return d
   def clone(self):return Model()
   def set_model_patch_replace(self,patch,family,kind,index):self.patches[(family,kind,index)]=patch
  self.model=Model();h3=types.ModuleType('comfy.ldm.minimax.model');h3.MiniMaxH3Model=Diffusion;h3.FRAME_PER_TOKEN=(1,4,4,4,4);h3.FRAME_RESCALE=5/3
  def attention_pytorch(*args):pass
  h3.optimized_attention=attention_pytorch;h3.rope_rotation_table=lambda x,y:x
  modules={name:types.ModuleType(name) for name in ['comfy','comfy.ldm','comfy.ldm.minimax']};modules['comfy.ldm.minimax.model']=h3
  for a,b in [('comfy','ldm'),('comfy.ldm','minimax'),('comfy.ldm.minimax','model')]:setattr(modules[a],b,modules[a+'.'+b])
  self.modules=modules;self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  graph=contract.read(ROOT/'configs/graphs'/f'{contract.RUN_ID}.json');self.kw={k:v for k,v in graph['50']['inputs'].items() if k not in ('model','positive')};self.kw['audit_dir']=self.tmp.name
 def apply(self):
  with mock.patch.dict(sys.modules,self.modules),mock.patch.object(node,'validate_run_contract'),mock.patch.object(node,'conditioning_metadata',return_value=self.meta):return node.H3AlignedMediaClock().apply(self.model,[],**self.kw)[0]
 def test_wraps_all50_native_blocks_with_one_alignment_state(self):
  result=self.apply();self.assertEqual(len(result.patches),50)
  self.assertEqual(self.model.patches,{})
  states=set()
  for i in range(50):
   patch=result.patches[('dit','double_block',i)];self.assertIsInstance(patch,node.AlignedBlockPatch);self.assertIsInstance(patch.native_patch,node.EventBlockPatch);self.assertEqual(patch.block_index,i);self.assertEqual(patch.native_patch.state.mode,'native');states.add(id(patch.alignment))
  self.assertEqual(len(states),1)
 def test_rejects_existing_dit_patch(self):
  self.model.model_options={'transformer_options':{'patches_replace':{'dit':{('double_block',6):object()}}}}
  with self.assertRaisesRegex(ValueError,'another DiT'):self.apply()
 def test_rejects_routing_on(self):
  self.kw['mode']='mass_preserve'
  with self.assertRaisesRegex(ValueError,'Native attention'):self.apply()
 def test_rejects_disabled_alignment(self):
  self.kw['enabled']=False
  with self.assertRaisesRegex(ValueError,'alignment enabled'):self.apply()

if __name__=='__main__':unittest.main()
