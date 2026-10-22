import sys,unittest,copy
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'extensions')]
from fixtures import MODEL,CANONICAL
from H3TemporalRouter.alignment import aligned_positions
from H3TemporalRouter.layout import validate_layout
import r132_contract as contract
class ImagePhase(unittest.TestCase):
 def make(self):
  refs=[{'kind':'image','index':0,'latent_t':1,'latent_h':76,'latent_w':50,'latent_shape':[1,24,1,76,50],'frame_rows':950,'ref_audio_t':0},{'kind':'video','index':1,'latent_t':42,'latent_h':46,'latent_w':82,'latent_shape':[1,24,42,46,82],'frame_rows':943,'ref_audio_t':0}]
  meta={'text_len':6960,'context_shape':[1,6960,5120],'refs':refs}
  return meta,MODEL['PackedLayout'](6960,42,46,82,235,refs=refs)
 def test_image_prefix_actual_grid_and_positions_preserved(self):
  meta,layout=self.make();before=layout.position_ids.clone();derived,audit=aligned_positions(layout,meta)
  canonical=CANONICAL['PackedLayout'](6960,42,46,82,235,refs=meta['refs'])
  self.assertTrue(torch.equal(layout.position_ids,before));self.assertTrue(torch.equal(derived,canonical.position_ids))
  self.assertEqual(audit['reference_origin'],6961.);self.assertAlmostEqual(audit['target_time_displacement'],-235.)
  self.assertTrue(torch.equal(derived[:47516],before[:47516]))
 def test_original_physical_window_and_image_exclusion(self):
  meta,layout=self.make();plan=validate_layout(meta,layout,50,65)
  self.assertEqual(plan['latent_interval_half_open'],[14,20]);self.assertEqual(plan['reference_image_segments'],[[6960,7910]])
  self.assertEqual(plan['key_interval_half_open'],[7910+14*943,7910+20*943]);self.assertEqual(plan['pixel_interval_inclusive'],[50,65])
  self.assertEqual(contract.routing_layout(contract.science()['cases'][0])['latent_interval_half_open'],[14,20])
 def test_changed_video_origin_rejected(self):
  meta,layout=self.make();layout.position_ids[7910:47516,0]+=1
  with self.assertRaises(ValueError):aligned_positions(layout,meta)
if __name__=='__main__':unittest.main()
