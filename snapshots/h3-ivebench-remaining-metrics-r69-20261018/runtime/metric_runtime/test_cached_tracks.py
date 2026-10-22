import json,tempfile,unittest
from pathlib import Path
import numpy as np
from ive_mf_adapter import COMMIT,SELECTION_SHA,WEIGHT_SHA,sha
from score_cached_tracks import TRACKER,score

class CacheBindingTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  for method in ['source','native']:
   p=self.root/method;p.mkdir();tracks=np.zeros((1,6,100,2),dtype=np.float32)
   tracks[0,:,:,0]=np.arange(6,dtype=np.float32)[:,None]
   tracks[0,:,:,1]=(np.arange(6,dtype=np.float32)**2)[:,None]
   np.savez(p/'tracks.npz',tracks=tracks,visibility=np.ones((1,6,100),dtype=bool))
   r={'passed':True,'official_commit':COMMIT,'checkpoint_sha256':WEIGHT_SHA,'selection_sha256':SELECTION_SHA,'tracker':TRACKER,'effective_frame_count':6,'score_frame_indices':list(range(6)),'tracks_sha256':sha(p/'tracks.npz'),'pair_id':'fixture','method':method,'source_prepared_sha256':'same_prepared','source_score_sha256':'same_score'}
   (p/'REPORT.json').write_text(json.dumps(r))
 def tearDown(self):self.temp.cleanup()
 def test_roundtrip_identical_official_tracks_score_one(self):
  r=score(self.root/'source',self.root/'native');self.assertAlmostEqual(r['motion_fidelity'],1);self.assertFalse(r['cuda_initialized'])
 def test_pair_or_input_mismatch_rejected(self):
  p=self.root/'native/REPORT.json';r=json.loads(p.read_text());r['source_prepared_sha256']='different';p.write_text(json.dumps(r))
  with self.assertRaisesRegex(ValueError,'source_prepared_sha256'):score(self.root/'source',self.root/'native')
 def test_altered_track_bytes_rejected(self):
  with (self.root/'native/tracks.npz').open('ab') as f:f.write(b'changed')
  with self.assertRaisesRegex(ValueError,'tensor file changed'):score(self.root/'source',self.root/'native')

if __name__=='__main__':unittest.main()
