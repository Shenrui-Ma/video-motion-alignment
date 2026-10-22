import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common as c
from consume import valid_attempt
import test_contract
class Host41(unittest.TestCase):
 def test_uid_and_host(self):
  cfg=c.verify_static();runtime=c.read(c.ROOT/'configs/producer_runtime.json')
  self.assertEqual((cfg['host'],runtime['uid']),('H3_SERVER_B',1004))
 def test_host41_attempt_allowed(self):
  self.assertTrue(valid_attempt('host41_oxygen_seeds_attempt1'))
 def test_unsafe_attempt_rejected(self):
  for value in ['host41_../x','x;rm','../../root_','root_hello/world']: self.assertFalse(valid_attempt(value))
 def test_old_host_uid_rejected(self):
  fixture=test_contract.Contract();fixture.setUp();fixture.owner['identity']['uid']=1016
  with self.assertRaises(ValueError): c.verify_release(fixture.aggregate,fixture.complete,fixture.release,fixture.started,fixture.cleanup,'fixture',fixture.cfg)
