import sys, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'audit'))
import root_run_batch as launch

class ManagedPeerRootTests(unittest.TestCase):
 def test_both_managed_directories_allow_absent_peer(self):
  with patch.object(Path,'exists',return_value=False):
   for directory in ['/data5/researcher/h3_runs','/home/researcher/h3_runs']:
    self.assertEqual(launch.live_peers([directory+'/test_peer']),[])
 def test_unmanaged_directory_rejected_before_read(self):
  with patch.object(Path,'exists',return_value=False):
   with self.assertRaisesRegex((ValueError,AssertionError),'authorized managed'):
    launch.live_peers(['/tmp/test_peer'])
 def test_self_rejected(self):
  with self.assertRaisesRegex((ValueError,AssertionError),'distinct root'):
   launch.live_peers([str(ROOT)])
