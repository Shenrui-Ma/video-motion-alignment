import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'analysis/postrun'))
import r107_contract as c, parent_evidence as e, execution_gate as g
class ParentContract(unittest.TestCase):
 def test_single_actual_graph_valid(self):
  jobs,order=c.registry();self.assertEqual(len(order),1)
  for run in order:c.validate_job(run)
 def test_frozen_numeric_files(self):
  rows=c.read(ROOT/'configs/runtime_kernel_hashes.json');self.assertEqual(len(rows),6)
  for p,r in rows.items():self.assertEqual(c.sha(ROOT/p),r['parent_sha256'])
 def test_valid_frame_bins(self):
  jobs,order=c.registry();self.assertEqual([c.routing_layout(jobs[x]['case'])['latent_interval_half_open'][1] for x in order],[43])
 def test_parent_conditions_only_renamed_provenance(self):
  for source in c.SOURCES:
   old=c.read(ROOT/'design'/source/'PARENT_CONDITIONING.json');new=copy.deepcopy(old);new['run_id']='new'
   for k in ('source_run_id','source_manifest','source_manifest_sha256'):new['pair_snapshot'][k]='new'
   self.assertTrue(e.comparable_conditions(new,old));e.validate_parent_condition(new,source)
 def test_condition_scientific_fields_rejected(self):
  old=c.read(ROOT/'design/long_0174/PARENT_CONDITIONING.json')
  for key in ('prompt','input_video','conditioning_embedding','token_tags','packed_layout','native_vae_calls'):
   new=copy.deepcopy(old);new[key]=None;self.assertFalse(e.comparable_conditions(new,old))
 def test_gate_only_creation_time_may_change(self):
  old=c.read(ROOT/'design/long_0174/PARENT_ACTUAL_GATE.json');new=copy.deepcopy(old);new['created_unix']+=1
  self.assertTrue(e.compare_parent_gate(new,old));new['runs']['native']['video']['sha256']='changed';self.assertFalse(e.compare_parent_gate(new,old))
 def test_gate_failed_rejected(self):
  old=c.read(ROOT/'design/long_0174/PARENT_ACTUAL_GATE.json');new=copy.deepcopy(old);new['passed']=False;self.assertFalse(e.compare_parent_gate(new,old))
 def test_single_admission(self):
  _,order=c.registry()
  with patch.object(g,'approval',return_value={'allowed_runs':order[:1]}):
   self.assertTrue(g.admitted_job(order[0]))
 def test_unregistered_run_rejected(self):
  with self.assertRaises(ValueError):g.admitted_job('invented')
 def test_original_graph_science_delta(self):
  jobs,order=c.registry()
  for run in order:
   case=jobs[run]['case'];old=c.read(ROOT/case['parent_graph']);new=c.read(ROOT/'configs/graphs'/f'{run}.json')
   for node in old:
    if node not in ('5','6','14','50','51','52'):self.assertEqual(old[node],new[node])
   self.assertEqual(old['5']['inputs']['prompt'],new['5']['inputs']['prompt'])
   self.assertEqual(new['50']['inputs']['step_start'],6);self.assertEqual(new['50']['inputs']['step_end'],15)
 def test_submit_checks_only_registered_forced_parent(self):
  import job
  binding=c.validate_job(c.run_id('long_0174'))
  with patch('parent_evidence.verify_parent',return_value={'passed':True}) as verify:
   job.require_native_generation(binding,{})
   verify.assert_called_once_with(job.RUN,source='long_0174',include_snapshots=False)
  wrong=dict(binding,arm='extended')
  with self.assertRaises(ValueError):job.require_native_generation(wrong,{})
class PrefixGate(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  try:import torch;import verify_pair
  except ImportError:raise unittest.SkipTest('CPU torch required for tensor prefix tests')
  cls.torch=torch;cls.module=verify_pair
 def test_prefix_exact_six_predictions(self):
  t=self.torch;seen=[]
  def fake(folder,record,run,shapes):
   i=record['index'];seen.append((str(folder),i));return {'video':t.tensor([i]),'audio':t.tensor([i]),'metadata':{'step_zero_based':i,'model_call_one_based':i+1}},{'sha256':str(i)}
  m={'captures':[{'index':i} for i in range(20)]}
  with patch.object(self.module,'checked_snapshot',side_effect=fake):rows=self.module.compare_prefix(Path('new'),m,'new',Path('old'),m,'old')
  self.assertEqual([r['step_zero_based'] for r in rows],list(range(6)));self.assertEqual(len(seen),12);self.assertTrue(all(r['video'] and r['audio'] for r in rows))
 def test_prefix_difference_not_accepted(self):
  t=self.torch
  def fake(folder,record,run,shapes):
   i=record['index'];return {'video':t.tensor([i+(str(folder)=='new' and i==5)]),'audio':t.tensor([i]),'metadata':{'step_zero_based':i,'model_call_one_based':i+1}},{'sha256':str(i)}
  m={'captures':[{'index':i} for i in range(20)]}
  with patch.object(self.module,'checked_snapshot',side_effect=fake):rows=self.module.compare_prefix(Path('new'),m,'new',Path('old'),m,'old')
  self.assertFalse(rows[-1]['video'])
 def test_semantically_identical_gate_preserves_creation_time(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'gate.json';g.atomic(p,{'created_unix':1,'passed':True,'runs':{}})
   out=self.module.persist_result(p,{'created_unix':2,'passed':True,'runs':{}});self.assertEqual(out['created_unix'],1)
if __name__=='__main__':unittest.main()
