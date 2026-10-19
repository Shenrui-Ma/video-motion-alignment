import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import run_tracks
import score_pair


class RuntimeBindings(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.tracks = self.root / "tracks.pt"
        self.tracks.write_bytes(b"test tracks")
        self.report = {
            "passed": True, "tracks_sha256": score_pair.sha(self.tracks),
            "timebase": {"frames": [{"best_effort_timestamp_time": str(i / 8)} for i in range(49)]},
            "checkpoint_sha256": score_pair.CHECKPOINT_SHA,
            "metric_functions_sha256": score_pair.sha(score_pair.ROOT / "METRIC_FUNCTIONS.json"),
            "vendor_manifest_sha256": score_pair.sha(score_pair.ROOT / "VENDOR.json"),
            "grid_size": 55, "mask": None, "tracks_dtype": "torch.float32",
            "case": json.loads((run_tracks.ROOT / "SOURCE_INPUTS.json").read_text())["inputs"][0],
            "manifest_sha256": run_tracks.sha(run_tracks.ROOT / "SOURCE_INPUTS.json")}
        self.tensor = SimpleNamespace(shape=(3025, 49, 2), dtype="float32")
        self.torch = SimpleNamespace(float32="float32", load=lambda *a, **k: {"tracks": self.tensor})

    def read(self):
        (self.root / "REPORT.json").write_text(json.dumps(self.report))
        return score_pair.read_tracks(self.root, self.torch)

    def test_valid_report(self):
        self.assertIs(self.read()[0], self.tensor)

    def test_wrong_reference_with_correct_pair_id_rejected(self):
        self.report["case"]["sha256"] = "another source video"
        with self.assertRaises(ValueError):
            self.read()

    def test_nonfinite_pts_rejected_by_both_readers(self):
        for invalid in ("nan", "inf", "-inf"):
            with self.subTest(invalid=invalid):
                self.report["timebase"]["frames"][4]["best_effort_timestamp_time"] = invalid
                with self.assertRaises(ValueError):
                    self.read()
                response = SimpleNamespace(stdout=json.dumps(self.report["timebase"]))
                with patch.object(run_tracks.subprocess, "run", return_value=response), self.assertRaises(ValueError):
                    run_tracks.check_timebase(self.tracks)

    def test_old_setup_rejected(self):
        for name in ("checkpoint_sha256", "metric_functions_sha256", "vendor_manifest_sha256"):
            original = self.report[name]
            self.report[name] = "old"
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.read()
            self.report[name] = original

    def test_tensor_shape_and_dtype_rejected(self):
        self.tensor.shape = (3025, 158, 2)
        with self.assertRaises(ValueError):
            self.read()
        self.tensor.shape, self.tensor.dtype = (3025, 49, 2), "float16"
        with self.assertRaises(ValueError):
            self.read()

    def generated(self):
        video, full = self.root / "release.mp4", self.root / "full.mp4"
        video.write_bytes(b"release49")
        full.write_bytes(b"full158")
        source = json.loads((run_tracks.ROOT / "SOURCE_INPUTS.json").read_text())["inputs"][0]
        metric = {"official_pair_id": source["id"], "edited49": str(video), "edited49_sha256": run_tracks.sha(video),
                  "full_output_indices": list(range(0, 147, 3)), "physical_seconds": [i / 8 for i in range(49)],
                  "padding_evaluated": False, "full158_output": str(full), "full158_output_sha256": run_tracks.sha(full),
                  "original_source_sha256": source["sha256"]}
        mapping = {"destination": str(video), "destination_sha256": run_tracks.sha(video),
                   "source": str(full), "source_sha256": run_tracks.sha(full), "input_indices": metric["full_output_indices"],
                   "physical_seconds": metric["physical_seconds"], "terminal_padding_excluded": True,
                   "decoded_frame_md5_equal": True}
        item = {"id": source["id"], "sha256": run_tracks.sha(video), "generation_binding": {}}
        for name, value in (("metric_inputs", metric), ("release_mapping", mapping)):
            path = self.root / (name + ".json")
            path.write_text(json.dumps(value))
            item["generation_binding"][name] = {"file": str(path), "sha256": run_tracks.sha(path)}
        return item, video, full

    def test_generated_actual_parent_and_mapping(self):
        item, video, _ = self.generated()
        self.assertIn("full158_sha256", run_tracks.validate_generated_binding(item, video))

    def test_changed_full_parent_rejected(self):
        item, video, full = self.generated()
        full.write_bytes(b"changed full")
        with self.assertRaises(ValueError):
            run_tracks.validate_generated_binding(item, video)

    def test_self_reported_indices_without_receipts_rejected(self):
        with self.assertRaises(KeyError):
            run_tracks.validate_generated_binding({"generation_frame_indices": list(range(0, 147, 3))}, self.tracks)

    def test_rehashed_wrong_mapping_rejected(self):
        item, video, _ = self.generated()
        path = Path(item["generation_binding"]["release_mapping"]["file"])
        mapping = json.loads(path.read_text())
        mapping["input_indices"][1] = 4
        path.write_text(json.dumps(mapping))
        item["generation_binding"]["release_mapping"]["sha256"] = run_tracks.sha(path)
        with self.assertRaises(ValueError):
            run_tracks.validate_generated_binding(item, video)


if __name__ == "__main__":
    unittest.main()
