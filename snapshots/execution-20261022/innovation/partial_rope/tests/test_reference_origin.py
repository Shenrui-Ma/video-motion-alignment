"""CPU checks for runtime coordinate-derived phase compensation."""
import copy
import json
import tempfile
import unittest
from types import SimpleNamespace

import torch
from H3PartialRoPE.adapter import H3PartialRoPE, PartialPhaseState
from H3PartialRoPE.core import PartialTemporalRotation


def fixture():
    metadata = {'text_len': 1, 'refs': [
        dict(kind='image', index=0, frame_rows=1, latent_t=1, latent_h=2, latent_w=2, ref_audio_t=0),
        dict(kind='video', index=1, frame_rows=1, latent_t=2, latent_h=2, latent_w=2, ref_audio_t=0)]}
    layout = SimpleNamespace(signature=(1,2,2,2,0), seq_len=6,
        segments=[(0,1,'text'),(1,2,'ref_img'),(2,4,'ref_img'),(4,4,'audio'),(4,6,'video')],
        position_ids=torch.tensor([[0,0,0],[1,0,0],[2,0,0],[2+5/3,0,0],
            [2+25/3,0,0],[2+30/3,0,0]], dtype=torch.float64))
    return metadata, layout


class ReferenceOriginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.metadata, self.layout = fixture()

    def tearDown(self):
        self.temp.cleanup()

    def state(self, mode='reference_origin', delta=0):
        rotation = PartialTemporalRotation(torch.linspace(.9,.01,16), delta, [0]*8+[1]*8)
        return PartialPhaseState(self.metadata, rotation, enabled=True, alpha=.25,
            schedule='all', start_frame=0, end_frame=4, block_start=0, block_end=50,
            run_id='test', audit_dir=self.temp.name, runtime_source_hashes={}, delta_mode=mode)

    def test_actual_origins_set_negative_five_frames(self):
        state = self.state()
        self.assertFalse(state.audit['delta_resolved'])
        state.plan_for(self.layout)
        self.assertAlmostEqual(state.rotation.delta_frames, -5)
        self.assertAlmostEqual(state.rotation.delta_rope, -25/3)
        self.assertEqual(state.audit['delta_derivation']['validated_temporal_bins'], 2)
        state.write()
        audit = json.loads(state.path.read_text())
        self.assertTrue(audit['delta_resolved'])
        self.assertAlmostEqual(audit['rotation']['delta_physical_frames'], -5)
        state.forward_index = 0
        self.assertTrue(state.selected(0))
        self.assertEqual(state.rotation.metadata()['selected_pair_indices'], list(range(8,16)))

    def test_nonzero_window_uses_origins_without_prefix_bias(self):
        state = self.state()
        state.start_frame, state.end_frame = 1, 4
        plan = state.plan_for(self.layout)
        self.assertEqual(plan['latent_interval_half_open'], [1,2])
        self.assertAlmostEqual(state.rotation.delta_frames, -5)

    def test_explicit_default_retains_existing_delta(self):
        state = self.state('explicit', -12)
        state.plan_for(self.layout)
        self.assertEqual(state.rotation.delta_frames, -12)
        self.assertEqual(H3PartialRoPE.INPUT_TYPES()['optional']['delta_mode'][1]['default'], 'explicit')

    def test_equal_geometry_new_layout_revalidated(self):
        state = self.state()
        first = state.plan_for(self.layout)
        self.assertEqual(state.plan_for(copy.deepcopy(self.layout)), first)
        self.assertAlmostEqual(state.rotation.delta_frames, -5)

    def test_wrong_temporal_spacing_rejected(self):
        state = self.state()
        self.layout.position_ids[5,0] += .1
        with self.assertRaisesRegex(ValueError, '5/3'):
            state.plan_for(self.layout)

    def test_nan_temporal_coordinate_rejected(self):
        state = self.state()
        self.layout.position_ids[3,0] = float('nan')
        with self.assertRaises(ValueError):
            state.plan_for(self.layout)

    def test_empty_layout_rejected(self):
        state = self.state()
        self.layout.position_ids = torch.empty(0,3)
        with self.assertRaises(ValueError):
            state.plan_for(self.layout)

    def test_wrong_origin_rejected(self):
        state = self.state()
        self.layout.position_ids[4:,0] += 1
        with self.assertRaisesRegex(ValueError, 'coordinate mismatch'):
            state.plan_for(self.layout)

    def test_invalid_mode_rejected(self):
        with self.assertRaisesRegex(ValueError, 'delta_mode'):
            self.state('unknown')


if __name__ == '__main__':
    unittest.main()
