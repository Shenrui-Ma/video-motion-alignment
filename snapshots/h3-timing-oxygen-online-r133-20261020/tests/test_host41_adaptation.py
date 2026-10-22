import copy,hashlib,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from observer_import import t
import service,r86_contract as c
class Host41(unittest.TestCase):
 def setUp(self):
  self.rt=json.loads((ROOT/'configs/runtime.json').read_text());self.p=self.rt['preserved_user_service'];self.row={'pid':self.p['pid'],'gpu_uuid':self.rt['preserved_user_service_gpu']}
 def test_preserved_exact_only(self):
  self.assertTrue(t.preserved_user_process(self.row,self.p))
  self.assertFalse(t.preserved_user_process(dict(self.row,pid=123),dict(self.p,pid=123)))
 def test_reused_preserved_pid_rejected(self):
  for key,value in [('start_ticks',1),('uid',1),('cmdline_sha256','x')]:
   with self.assertRaises(ValueError):t.preserved_user_process(self.row,dict(self.p,**{key:value}))
 def test_preserved_wrong_card_rejected(self):
  with self.assertRaises(ValueError):t.preserved_user_process(dict(self.row,gpu_uuid=t.MAIN_UUID),self.p)
 def test_preserved_registry_rejects_extra_peer(self):
  row={'pid':self.p['pid'],'identity':{k:str(v) if k=='start_ticks' else v for k,v in self.p.items() if k!='pid'}}
  self.assertTrue(t.validate_preserved_registry([row]))
  for bad in ([],[row,row]):
   with self.assertRaises(ValueError):t.validate_preserved_registry(bad)
 def test_three_physical_cards_two_research(self):
  main={'pid':10,'uid':1004,'start_ticks':5,'cmdline_sha256':'main'}
  rows=[self.row,{'pid':10,'gpu_uuid':t.MAIN_UUID}];ids={10:main,self.p['pid']:self.p}
  gpu={'uuid':t.DECODER_UUID,'memory_free_mib':48000}
  with patch.object(t.os,'getuid',return_value=1004):
   result=t.validate_resource_capacity(t.DECODER_UUID,gpu,rows,16*1024**3,parent=main,lookup=ids.get)
  self.assertEqual(result['planned_owned_GPUs'],sorted([t.MAIN_UUID,t.DECODER_UUID]))
 def test_third_research_card_rejected(self):
  main={'pid':10,'uid':1004,'start_ticks':5,'cmdline_sha256':'main'};peer=dict(main,pid=11)
  rows=[self.row,{'pid':10,'gpu_uuid':t.MAIN_UUID},{'pid':11,'gpu_uuid':'another'}];ids={10:main,11:peer,self.p['pid']:self.p}
  with patch.object(t.os,'getuid',return_value=1004),self.assertRaises(t.ResourceUnavailable):t.validate_resource_capacity(t.DECODER_UUID,{'uuid':t.DECODER_UUID,'memory_free_mib':48000},rows,16*1024**3,parent=main,lookup=ids.get)
 def test_actual_node_whitelisted_and_readiness_guarded(self):
  args=service.command();self.assertIn('H3AutomaticWindowRouter',args)
  text=(ROOT/'scripts/root_run_online.py').read_text();self.assertIn("'H3AutomaticWindowRouter' in nodes",text);self.assertIn('CGROUP_PRE_GO.json',text)
 def test_r113_actual_noise_preserved(self):
  self.assertEqual(c.expected_graph()['6']['inputs']['pair_id'],'r113_short_0252_seed2026101703')
  self.assertIn('r113_short_0252_seed2026101703_noise.pt',(ROOT/'scripts/verify_parent_payloads.py').read_text())
 def test_frozen_numerics_and_first_on_prefix(self):
  old=json.loads((ROOT/'audit/INHERITANCE.json').read_text())['unchanged_numerics']
  for rel in ('extensions/H3AutomaticWindowRouter/core.py','extensions/H3AutomaticWindowRouter/pair_gate.py','extensions/H3AutomaticWindowRouter/selector.py','extensions/H3AutomaticWindowRouter/automatic_window_policy.py','extensions/H3AutomaticWindowRouter/delayed_window_policy.py','extensions/H3TemporalRouter/core.py','scripts/scan_current_pose.py','scripts/decode_live_child.py'):
   self.assertEqual(hashlib.sha256((ROOT/rel).read_bytes()).hexdigest(),old[rel]['source_sha256'],rel)
 def test_actual_parent_source_condition_id(self):
  graph=c.expected_graph();self.assertEqual(graph['51']['inputs']['source_run_id'],'r113_short_0252_shared')
  self.assertIn("'r113_'+row['case']['source_id']+'_shared'",(ROOT/'extensions/H3PairAudit/__init__.py').read_text())
 def test_protocol_hash_bound(self):self.assertEqual(t.PROTOCOL_SHA,hashlib.sha256((ROOT/'configs/protocol.json').read_bytes()).hexdigest())
if __name__=='__main__':unittest.main()
