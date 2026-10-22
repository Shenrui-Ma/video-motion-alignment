import sys,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import remote
class BoundHost(unittest.TestCase):
 def setUp(self):self.c=remote.config();self.path=self.c['producer_remote']+'/configs/runtime.json'
 def test_json_read_uses_bound_host(self):
  with patch.object(remote.subprocess,'run',return_value=SimpleNamespace(stdout='{}'))as call:remote.read_paths([self.path])
  self.assertEqual(call.call_args.args[0][5],self.c['host']);self.assertEqual(self.c['host'],'H3_SERVER_B')
 def test_transfer_uses_bound_host(self):
  with patch.object(remote.subprocess,'run')as call:remote.fetch(self.path,'/tmp/consumer_transport_fixture.json')
  self.assertIn(self.c['host']+':'+self.path,call.call_args.args[0])
 def test_source_hash_uses_bound_host(self):
  digest='a'*64
  with patch.object(remote.subprocess,'run',return_value=SimpleNamespace(stdout=digest+'\n'))as call:remote.verify_source_bytes(self.path,digest)
  self.assertEqual(call.call_args.args[0][5],self.c['host'])
