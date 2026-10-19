import ast, importlib.util, json, os, sys, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import r114_contract as c
spec=importlib.util.spec_from_file_location('r114_wrapper_for_test',ROOT/'audit/root_run_batch.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class Derivation(unittest.TestCase):
 def test_exact_selected_inputs_prompts_and_unchanged_original_events(self):
  parent=ROOT/'source_snapshot/r93'
  for rel,key in [('design/INPUT_PLAN.json','pairs'),('design/PROPOSAL.json','cases'),('design/REFERENCE_EVENT_REVIEW_PLAN.json','items'),('PREPARED_INPUTS_MANIFEST.json','pairs')]:
   old={x.get('source_id',x.get('pair_id')):x for x in c.read(parent/rel)[key]}
   now=c.read(ROOT/rel)[key]
   self.assertEqual([x.get('source_id',x.get('pair_id')) for x in now],list(c.SOURCES))
   self.assertEqual(now,[old[s] for s in c.SOURCES])
  bindings=c.read(ROOT/'audit/INHERITED_BYTE_BINDINGS.json')
  for name,row in bindings['inputs'].items():self.assertTrue(row['equal']);self.assertEqual(c.sha(ROOT/'inputs'/name),row['parent_sha256'])
  for source,digest in bindings['prompts'].items():self.assertEqual(c.sha(ROOT/'configs/prompts'/(source+'.txt')),digest)
 def test_registry_exact_three_and_not_queued_existing_sources(self):
  self.assertEqual(c.SOURCES,('long_0081','long_0059','long_0163'));jobs,order=c.registry(ROOT)
  self.assertEqual(len(order),6);self.assertFalse(any('short_0370' in x or 'short_0203' in x for x in order))
  self.assertFalse(c.read(ROOT/'configs/admission.json')['ready_for_launch'])
 def test_peer_function_exact_reviewed_r104(self):
  def fn(p):return ast.dump(next(x for x in ast.parse(p.read_text()).body if isinstance(x,ast.FunctionDef) and x.name=='live_peers'),include_attributes=False)
  self.assertEqual(fn(ROOT/'audit/root_run_batch.py'),fn(ROOT/'source_snapshot/r104/root_run_batch.py'))

class PeerOwnership(unittest.TestCase):
 def fixtures(self,root):
  identity={'uid':os.getuid(),'start_ticks':'123','cmdline':str(root/'scripts/service_entry.py')}
  owner={'pid':321,'identity':identity,'gpu_uuid':'GPU-peer','port':8999}
  runtime={'remote_root':str(root),'gpu_uuid':'GPU-peer','port':8999}
  return identity,owner,runtime
 def test_cross_data_home_parent_allowed_when_identity_is_exact(self):
  current=Path('/home/researcher/h3_runs/current');peer=Path('/data5/researcher/h3_runs/peer');identity,owner,runtime=self.fixtures(peer)
  with patch.object(runner,'ROOT',current),patch.object(Path,'exists',return_value=True),patch.object(runner,'read',side_effect=lambda p:owner if p.name=='service.json' else runtime),patch.object(runner.service,'current_identity',return_value=identity),patch.object(runner.service,'external_identity',return_value=identity):
   self.assertEqual(runner.live_peers([str(peer)])[0]['owner'],owner)
 def test_unmanaged_peer_rejected(self):
  with patch.object(runner,'ROOT',Path('/home/researcher/h3_runs/current')):
   with self.assertRaisesRegex(ValueError,'authorized managed'):runner.live_peers(['/tmp/unmanaged/peer'])
 def test_reused_peer_identity_rejected(self):
  current=Path('/home/researcher/h3_runs/current');peer=Path('/data5/researcher/h3_runs/peer');identity,owner,runtime=self.fixtures(peer)
  with patch.object(runner,'ROOT',current),patch.object(Path,'exists',return_value=True),patch.object(runner,'read',return_value=owner),patch.object(runner.service,'current_identity',return_value={**identity,'start_ticks':'124'}):
   with self.assertRaisesRegex(ValueError,'generation changed'):runner.live_peers([str(peer)])

if __name__=='__main__':unittest.main()
