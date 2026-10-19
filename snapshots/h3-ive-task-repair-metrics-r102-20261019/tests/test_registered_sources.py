import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common as c
class RegisteredSources(unittest.TestCase):
 def test_all_three_actual_geometry_and_provenance(self):
  self.assertEqual(c.SOURCES,('short_0263','short_0092','short_0126'))
  for source,total,valid in [('short_0263',90,74),('short_0092',73,58),('short_0126',124,109)]:
   p=c.info(source);self.assertEqual((p['geometry']['frames'],p['valid_frames']),(total,valid));self.assertEqual(p['crop_xywh'],[16,8,1280,720]);self.assertFalse(p['reference_image_used'])
   prov=c.read(c.ROOT/p['provenance']['file']);self.assertEqual(prov['evaluate_indices'],list(range(valid)));self.assertEqual(prov['padding_indices'],list(range(valid,total)));self.assertEqual(c.sha(p['original_media']['file']),p['original_media']['sha256'])
if __name__=='__main__':unittest.main()
