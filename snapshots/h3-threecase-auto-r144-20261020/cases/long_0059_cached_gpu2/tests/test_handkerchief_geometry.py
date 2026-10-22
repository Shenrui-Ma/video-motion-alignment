import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "extensions")]
from H3AutomaticWindowRouter.geometry import Geometry
from observer_import import t


class HandkerchiefGeometry(unittest.TestCase):
    def test_original_158_geometry_excludes_all_14_padding_frames(self):
        case = json.loads((ROOT / "configs/protocol.json").read_text())["cases"][0]
        geometry = Geometry.from_case(case)
        self.assertEqual(geometry.latent_bins, 47)
        self.assertEqual(geometry.stream_shapes, ((1, 24, 47, 46, 82), (1, 32, 2, 263)))
        self.assertEqual(geometry.domain_record["excluded_padding_frames"], list(range(144, 158)))
        windows = list(geometry.windows())
        self.assertEqual(len(windows), 62)
        self.assertIn([128, 143], windows)
        self.assertIn([112, 143], windows)
        self.assertTrue(all(end < 144 for _, end in windows))

    def test_whole_frame_selection_retains_original_source_people(self):
        raw = json.loads((ROOT / "configs/source.raw.pose.json").read_text())
        selected = json.loads((ROOT / "configs/source.pose.json").read_text())
        self.assertEqual(raw, selected)
        self.assertTrue(all(len(row["persons"]) == 1 and row["selected_person"] == 0
                            for row in selected["frames"][:144]))

    def test_158_capacity_is_explicit_unmeasured_and_requires_root_binding(self):
        profile = json.loads((ROOT / "configs/decoder_memory_profile.json").read_text())
        self.assertEqual(profile["geometry"]["frames"], 158)
        self.assertFalse(profile["measured_capacity"])
        approval = {"root_approved": True,
                    "decoder_profile_sha256": t.sha(ROOT / "configs/decoder_memory_profile.json"),
                    "runtime_sha256": t.sha(ROOT / "configs/runtime.json")}
        with patch.object(t, "read_json", side_effect=[profile, approval]):
            self.assertEqual(t.decoder_memory_profile()["required_free_bytes"], 16 * 1024**3)
        with patch.object(t, "read_json", side_effect=[profile, dict(approval, root_approved=False)]):
            with self.assertRaises(ValueError):
                t.decoder_memory_profile()


if __name__ == "__main__":
    unittest.main()
