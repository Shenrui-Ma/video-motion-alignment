import copy
import json
from pathlib import Path
import tempfile
import types
import unittest

import run_pair as runner


class BindingTests(unittest.TestCase):
    def test_exact_denominator_and_order(self):
        records = [{"pair_id": pair, "method": method} for pair in runner.CONTRACT["pair_order"]
                   for method in runner.CONTRACT["methods"]]
        runner.validate_manifest(records)
        for bad in (records[:-1], records + [records[0]], list(reversed(records))):
            with self.assertRaises(ValueError):
                runner.validate_manifest(bad)

    def test_video_pose_association(self):
        raw = {"schema": "h3_cpu_pose_v1", "provenance": copy.deepcopy(runner.CONTRACT["pose_provenance"]),
               "joint_order": runner.CONTRACT["joint_order"], "extraction": {"start": 0, "end": None, "stride": 1},
               "video": {"path": "/example/full158.mp4", "sha256": "expected", "fps": 24,
                         "container_frame_count": 158, "width": 1152, "height": 768},
               "frames": [{"frame": i, "selected_person": None, "persons": []} for i in range(158)]}
        runner.validate_pose(raw, "/example/full158.mp4", "expected")
        modifications = [lambda x: x["video"].update(sha256="other"),
                         lambda x: x["video"].update(fps=8),
                         lambda x: x["provenance"].update(script_sha256="changed"),
                         lambda x: x["frames"][0].update(selected_person=-1),
                         lambda x: x["frames"].pop()]
        for change in modifications:
            bad = copy.deepcopy(raw)
            change(bad)
            with self.assertRaises(ValueError):
                runner.validate_pose(bad, "/example/full158.mp4", "expected")

    def test_modified_asset_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "asset.json"
            path.write_text("before")
            digest = runner.sha(path)
            runner.artifact(path, digest)
            path.write_text("after")
            with self.assertRaises(ValueError):
                runner.artifact(path, digest)

    def test_snapshot_binds_the_bytes_actually_read(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest.json"
            path.write_text('{"generation":1}')
            captured = runner.snapshot(path)
            path.write_text('{"generation":2}')
            self.assertEqual(captured["content"], {"generation": 1})
            self.assertNotEqual(captured["sha256"], runner.sha(path))

    def test_wrong_producer_and_pending_rejected_before_metric(self):
        with tempfile.TemporaryDirectory() as temp:
            metric = Path(temp) / "METRIC_INPUTS.json"
            metric.write_text(json.dumps({"run_id": "r49_source_chest_seed2026101701_native",
                                         "official_pair_id": "human/chest/000"}))
            mapping = Path(temp) / "mapping.json"
            mapping.write_text("{}")
            record = {"status": "complete", "pair_id": "human/chest/000", "method": "automatic",
                      "metric_inputs_path": str(metric), "metric_inputs_sha256": runner.sha(metric),
                      "release49_mapping_path": str(mapping), "release49_mapping_sha256": runner.sha(mapping)}
            with self.assertRaisesRegex(ValueError, "Wrong producer"):
                runner.generated_pose(record, "human/chest/000", "automatic", types.SimpleNamespace())
            record["status"] = "pending"
            with self.assertRaisesRegex(ValueError, "pending"):
                runner.generated_pose(record, "human/chest/000", "automatic", types.SimpleNamespace())


if __name__ == "__main__":
    unittest.main()
