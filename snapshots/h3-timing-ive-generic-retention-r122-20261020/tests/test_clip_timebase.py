import sys,unittest
from fractions import Fraction as F
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from input_contract import clip_nearest_map,clip_valid_count,read,SOURCES,LENGTHS

class ClipTimebase(unittest.TestCase):
 def test_nonzero_origin_is_removed_once(self):
  pts=[str(F(i,24)) for i in range(100)]
  self.assertEqual(clip_nearest_map(pts,24,71,48),list(range(24,72)))
 def test_tie_earlier_and_no_outside_clip(self):
  self.assertEqual(clip_nearest_map(['0','1/12','1/6','1/4'],1,2,3),[1,1,2])
 def test_exact_six_seconds_excludes_boundary(self):
  self.assertEqual(clip_valid_count('3/2','15/2'),144)
  self.assertEqual(clip_valid_count('9/25','159/25'),144)
 def test_ntsc_not_rounded_to_integer_fps(self):
  self.assertEqual(clip_valid_count('0','1001/250'),97)
  self.assertEqual(clip_valid_count('7007/1600','83083/8000'),145)
 def test_mapping_and_valid_padding_boundary_all_sources(self):
  rows=read(ROOT/'design/INPUT_PLAN.json')['pairs']
  self.assertEqual([r['pair_id'] for r in rows],list(SOURCES))
  for row,(t,n) in zip(rows,LENGTHS):
   clip=row['clip'];a=clip['start_frame'];b=clip['end_frame_inclusive'];pts=list(map(F,row['source']['actual_pts_rational']));start=F(clip['start_pts_rational']);end=F(clip['end_exclusive_rational'])
   self.assertEqual(pts[a],start);self.assertEqual(pts[b+1] if b+1<len(pts) else pts[b]+1/F(row['source']['fps_rational']),end)
   self.assertEqual(n,clip_valid_count(start,end));self.assertLess(start+F(n-1,24),end);self.assertGreaterEqual(start+F(n,24),end)
   mapping=clip_nearest_map(pts,a,b,n);self.assertEqual(mapping[0],a);self.assertEqual(mapping[-1],b)
   self.assertEqual(row['input_protocol']['input_to_original_frame'],mapping+[b]*(t-n))
 def test_reversed_and_nonmonotonic_rejected(self):
  for args in [(['0','1'],1,0,3),(['0','0'],0,1,2)]:
   with self.assertRaises(ValueError):clip_nearest_map(*args)

if __name__=='__main__':unittest.main()
