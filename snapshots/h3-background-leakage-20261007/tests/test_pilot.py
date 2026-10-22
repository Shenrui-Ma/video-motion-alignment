import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('analyze_video', ROOT / 'scripts/analyze_video.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class PilotTests(unittest.TestCase):
    def test_aligned_workflow_covers_history_and_published_tail(self):
        graph = json.loads((ROOT / 'configs/aligned_continuation_original.json').read_text())
        legacy = json.loads((ROOT / 'configs/continuation_seg2_original.json').read_text())
        self.assertEqual(graph['136']['inputs']['length'], 192)
        self.assertEqual(int(graph['153']['inputs']['context_length'])
                         + graph['154']['inputs']['visible_frames'], 192)
        self.assertEqual(graph['155']['inputs']['visible_frames'], 170)
        self.assertEqual(graph['129'], legacy['129'])
        self.assertEqual(graph['137'], legacy['137'])
        self.assertEqual(graph['150'], legacy['150'])
        self.assertNotIn('<Audio 1>', graph['136']['inputs']['prompt'])
        self.assertNotIn('ref_video_audios.ref_video_audio_0', graph['136']['inputs'])

    def test_continuation_pair_keeps_history_and_timing_fixed(self):
        original = json.loads((ROOT / 'configs/continuation_seg2_original.json').read_text())
        neutral = json.loads((ROOT / 'configs/continuation_seg2_neutral.json').read_text())
        self.assertEqual(original['136']['inputs']['length'], 192)
        self.assertEqual(original['153']['inputs']['context_length'], '22')
        self.assertEqual(original['153']['inputs']['audio_context_length'], 24)
        self.assertEqual(original['154']['inputs']['visible_frames'], 158)
        self.assertEqual(original['154']['inputs']['trim_frames'], ['153', 1])
        for graph in (original, neutral):
            graph['137']['inputs']['image'] = 'REFERENCE'
            graph['92']['inputs']['filename_prefix'] = 'VIDEO_OUTPUT'
            graph['155']['inputs']['filename_prefix'] = 'LATENT_OUTPUT'
        self.assertEqual(original, neutral)

    def test_historical_replay_preserves_requested_length_and_audio(self):
        historical = json.loads((ROOT / 'configs/historical_independent_part1b.json').read_text())
        original = json.loads((ROOT / 'configs/replay_part1b_original.json').read_text())
        neutral = json.loads((ROOT / 'configs/replay_part1b_neutral.json').read_text())
        self.assertEqual(original['136']['inputs']['length'], 164)
        self.assertEqual(original['136']['inputs']['ref_video_audios.ref_video_audio_0'], ['139', 1])
        for graph in (historical, original, neutral):
            graph['137']['inputs']['image'] = 'REFERENCE'
            graph['92']['inputs']['filename_prefix'] = 'OUTPUT'
            graph['138']['inputs']['file'] = 'SOURCE'
        self.assertEqual(historical, original)
        self.assertEqual(original, neutral)

    def test_paired_graph_keeps_sampling_and_geometry_fixed(self):
        original = json.loads((ROOT / 'configs/fresh_seg2_original.json').read_text())
        neutral = json.loads((ROOT / 'configs/fresh_seg2_neutral.json').read_text())
        self.assertNotIn('ref_video_audios.ref_video_audio_0', original['136']['inputs'])
        for graph in (original, neutral):
            graph['137']['inputs']['image'] = 'REFERENCE'
            graph['92']['inputs']['filename_prefix'] = 'OUTPUT'
        self.assertEqual(original, neutral)

    def test_proxy_detects_cyan_vs_dark_and_ignores_center(self):
        frames = np.zeros((2, analysis.HEIGHT, analysis.WIDTH, 3), dtype=np.uint8)
        frames[0] = [30, 180, 190]
        frames[0, :, 130:254] = 0
        frames[1, :, 130:254] = [30, 180, 190]
        sky, dark = analysis.scene_proxies(frames)
        np.testing.assert_allclose(sky, [1, 0])
        np.testing.assert_allclose(dark, [0, 1])

    def test_warm_roof_is_not_cyan(self):
        frame = np.full((1, analysis.HEIGHT, analysis.WIDTH, 3), [160, 100, 40], dtype=np.uint8)
        sky, dark = analysis.scene_proxies(frame)
        self.assertEqual(float(sky[0]), 0)
        self.assertEqual(float(dark[0]), 0)


if __name__ == '__main__':
    unittest.main()
