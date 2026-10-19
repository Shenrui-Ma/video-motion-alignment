import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import contract as c,remote_consume as rc,scan_current_pose as scan
class SourceCacheTests(unittest.TestCase):
 def fixture(self,root):
  video=root/'source.mp4';video.write_bytes(b'current source');folder=root/'source_pose';folder.mkdir();pose=folder/'source.pose.json';c.save(pose,{'video':{'sha256':c.sha(video)}});c.save(folder/'SOURCE_FILES.json',{'source.pose.json':c.sha(pose)});return video,folder,pose
 def test_reuse_bound_source_without_model(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);video,folder,pose=self.fixture(root)
   with patch.object(rc,'ARC',root),patch.object(scan,'valid_pose',side_effect=c.read),patch.object(rc.subprocess,'run') as run:self.assertEqual(rc.source_pose(video),pose);run.assert_not_called()
 def test_source_changed_even_self_consistent_cache_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);video,folder,pose=self.fixture(root);c.save(pose,{'video':{'sha256':'wrong'}});c.save(folder/'SOURCE_FILES.json',{'source.pose.json':c.sha(pose)})
   with patch.object(rc,'ARC',root),patch.object(scan,'valid_pose',side_effect=c.read),self.assertRaises(ValueError):rc.source_pose(video)
 def test_extra_source_file_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);video,folder,pose=self.fixture(root);(folder/'extra').write_text('x')
   with patch.object(rc,'ARC',root),self.assertRaises(ValueError):rc.source_pose(video)
 def test_partial_source_never_silently_reruns(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);video=root/'source.mp4';video.write_bytes(b'x');(root/'source_pose').mkdir()
   with patch.object(rc,'ARC',root),patch.object(rc.subprocess,'run') as run,self.assertRaises(ValueError):rc.source_pose(video)
   run.assert_not_called()
if __name__=='__main__':unittest.main()
