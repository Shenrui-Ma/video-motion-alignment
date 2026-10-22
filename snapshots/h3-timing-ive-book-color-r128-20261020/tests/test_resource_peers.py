import sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import service,resource_gate

class PeerAdmissionTests(unittest.TestCase):
 def check(self,rows,own,allowed):
  identities={pid:{'uid':1004,'start_ticks':str(pid),'cmdline_sha256':str(pid)} for pid in own}
  admission={'permitted_compute_processes':[{'pid':pid,'identity':identities[pid]} for pid in allowed]}
  with patch.object(resource_gate,'admission_document',return_value=admission),patch.object(service.os,'getuid',return_value=1004),patch.object(service,'proc_uid',side_effect=lambda pid:1004 if pid in own else 9999),patch.object(service,'external_identity',side_effect=lambda pid:identities[pid]):
   return service.check_admission(admission,rows,{'queue_running':[],'queue_pending':[]})
 def test_registered_peer_and_foreign_on_three_other_cards_allowed(self):
  rows=[{'gpu_uuid':'GPU-peer1','pid':10}]+[{'gpu_uuid':f'GPU-foreign{i}','pid':100+i} for i in range(3)]+[{'gpu_uuid':service.GPU,'pid':200}]
  self.check(rows,{10},{10})
 def test_second_registered_peer_creating_third_own_card_rejected(self):
  with self.assertRaises(resource_gate.ResourceUnavailable):self.check([{'gpu_uuid':'GPU-peer1','pid':10},{'gpu_uuid':'GPU-peer2','pid':11}],{10,11},{10,11})
 def test_unregistered_own_peer_rejected(self):
  with self.assertRaisesRegex(RuntimeError,'Unexpected own compute'):self.check([{'gpu_uuid':'GPU-peer1','pid':10}],{10},set())
 def test_peer_same_generation_required(self):
  admission={'permitted_compute_processes':[{'pid':10,'identity':{'uid':1004,'start_ticks':'old'}}]}
  with patch.object(resource_gate,'admission_document',return_value=admission),patch.object(service.os,'getuid',return_value=1004),patch.object(service,'proc_uid',return_value=1004),patch.object(service,'external_identity',return_value={'uid':1004,'start_ticks':'new'}):
   with self.assertRaisesRegex(RuntimeError,'Unexpected own compute'):service.check_admission(admission,[{'gpu_uuid':'GPU-peer1','pid':10}],{'queue_running':[],'queue_pending':[]})

