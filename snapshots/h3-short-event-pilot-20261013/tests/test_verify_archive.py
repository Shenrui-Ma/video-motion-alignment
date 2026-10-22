import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location("verify_archive", Path(__file__).resolve().parents[1] / "scripts/verify_archive.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for folder in ("configs", "inputs", "source_candidates", "logs", "audit/tensor_blobs", "outputs"):
            (self.root / folder).mkdir(parents=True)
        self.source = "01_test"
        (self.root / "inputs/01_test.mp4").write_bytes(b"source")
        original = self.root / "source_candidates/original.mp4"
        original.write_bytes(b"original")
        metadata = {"clip_id": "01_test", "source_file": str(original),
                    "source_sha256": module.file_hash(original),
                    "output_sha256": module.file_hash(self.root / "inputs/01_test.mp4")}
        self.write("inputs/01_test.json", metadata)
        self.write("inputs/source_manifest.json", {"clips": [metadata]})
        self.probe = lambda path: {"width": 32, "height": 32, "frames": 107, "fps": "24", "codec": "h264"}

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, value):
        (self.root / path).write_text(json.dumps(value))

    def tensor(self, shape, byte=0, save=True):
        count = 4
        for dim in shape:
            count *= dim
        payload = bytes([byte]) * count
        digest = hashlib.sha256(payload).hexdigest()
        info = {"shape": shape, "dtype": "torch.float32", "sha256": digest}
        if save:
            relative = "tensor_blobs/" + digest + ".pt"
            with zipfile.ZipFile(self.root / "audit" / relative, "w") as output:
                output.writestr("archive/data/0", payload)
                output.writestr("archive/data.pkl", b"NOT EXECUTABLE; verifier never unpickles")
            info["tensor_file"] = relative
        return info, payload

    def fixture(self, arm="a", benchmark=False, run_id=None):
        run = run_id or self.source + "_" + arm + "_s1" + ("_benchmark2" if benchmark else "")
        prompt = "edit" if arm == "a" else "edit and retain event"
        graph = {
            "5": {"class_type": "H3EventAuditReference", "inputs": {"run_id": run, "prompt": prompt,
                    "width": 32, "height": 32, "length": 107, "ref_video": ["22", 0]}},
            "6": {"class_type": "H3EventAuditNoise", "inputs": {"run_id": run, "pair_id": "01_test_s1", "noise_seed": 42}},
            "9": {"class_type": "ManualSigmas", "inputs": {"sigmas": ",".join(["1"] * (2 if benchmark else 20) + ["0"])}},
            "10": {"class_type": "SamplerCustomAdvanced", "inputs": {"latent_image": ["5", 1], "noise": ["6", 0], "sigmas": ["9", 0]}},
            "14": {"class_type": "SaveVideo", "inputs": {"filename_prefix": run, "video": ["10", 0]}},
            "22": {"class_type": "LoadVideo", "inputs": {"file": "01_test.mp4"}}}
        if arm == "a":
            graph["34"] = {"class_type": "SaveVideo", "inputs": {"filename_prefix": "diagnostic", "video": ["5", 2]}}
        self.write("configs/" + run + ".json", graph)
        output = run + "_00001_.mp4"
        (self.root / "outputs" / output).write_bytes(b"video")
        history = {"prompt": [1, "prompt-" + run, graph], "outputs": {"14": {"images": [{"filename": output, "subfolder": "", "type": "output"}]}},
                   "status": {"status_str": "success", "completed": True, "messages": [
                       ["execution_start", {"timestamp": 100000, "prompt_id": "prompt-" + run}],
                       ["execution_success", {"timestamp": 292368, "prompt_id": "prompt-" + run}]]}}
        self.write("logs/" + run + "_history.json", history)
        self.write("logs/" + run + "_job.json", {"prompt_id": "prompt-" + run,
                   "graph_sha256": module.file_hash(self.root / "configs" / (run + ".json")),
                   "submitted_unix": 1, "observed_unix": 99999999, "status": "success"})
        prepared, _ = self.tensor([107, 32, 32, 3])
        latent, _ = self.tensor([1, 24, 32, 2, 2], byte=1)
        sampled, _ = self.tensor([9, 32, 32, 3])
        video_noise, video_payload = self.tensor([1, 24, 32, 2, 2], byte=2, save=False)
        audio_noise, audio_payload = self.tensor([1, 32, 2, 178], byte=3, save=False)
        shapes = [video_noise["shape"], audio_noise["shape"]]
        cond = {"run_id": run, "prompt": prompt, "input_video": prepared,
                "native_vae_calls": [{"prepared_frames": prepared, "latent": latent}],
                "qwen_presentation": [{"type": "video", "sampling": {"sample_indices": [0, 12]}, "actual_sampled_frames": sampled}],
                "target_latent_shapes": shapes}
        self.write("audit/" + run + "_conditioning.json", cond)
        noise = {"run_id": run, "pair_id": "01_test_s1", "signature": {"seed": 42, "nested": True,
                 "shapes": shapes, "dtypes": ["torch.float32", "torch.float32"], "batch_index": None},
                 "actual_noise_streams": [video_noise, audio_noise], "cache_file": "/remote/audit/01_test_s1_noise.pt"}
        self.write("audit/" + run + "_noise.json", noise)
        with zipfile.ZipFile(self.root / "audit/01_test_s1_noise.pt", "w") as output_zip:
            output_zip.writestr("archive/data/0", video_payload)
            output_zip.writestr("archive/data/1", audio_payload)
        return run, graph

    def test_complete_pair_and_execution_timestamps(self):
        aid, ag = self.fixture("a")
        bid, bg = self.fixture("b")
        verifier = module.Verifier(self.root, self.probe)
        a, b = verifier.run(aid), verifier.run(bid)
        self.assertEqual(a["status"], "complete", a)
        self.assertEqual(a["execution_seconds"], 192.368)
        self.assertEqual(module.pair_validation(a, b, ag, bg)["status"], "pass")

    def test_diagnostic_branch_allowed_but_sampler_change_rejected(self):
        aid, ag = self.fixture("a")
        bid, bg = self.fixture("b")
        self.assertEqual(module.normalized_main_graph(ag, aid), module.normalized_main_graph(bg, bid))
        bg["9"]["inputs"]["sigmas"] = "1,0"
        self.assertNotEqual(module.normalized_main_graph(ag, aid), module.normalized_main_graph(bg, bid))

    def test_video_without_history_is_pending(self):
        run, _ = self.fixture()
        (self.root / "logs" / (run + "_history.json")).unlink()
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertEqual(result["status"], "pending")
        self.assertFalse(result["generated"])

    def test_missing_blob_is_not_complete(self):
        run, _ = self.fixture()
        (self.root / "audit/01_test_s1_noise.pt").unlink()
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertEqual(result["status"], "generated_pending_archive")
        self.assertFalse(result["fully_archived"])

    def test_benchmark_filename_cannot_satisfy_formal_run(self):
        run, _ = self.fixture()
        history_path = "logs/" + run + "_history.json"
        history = module.read_json(self.root / history_path)
        filename = run + "_benchmark2_00001_.mp4"
        history["outputs"]["14"]["images"][0]["filename"] = filename
        (self.root / "outputs" / filename).write_bytes(b"benchmark")
        self.write(history_path, history)
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertEqual(result["status"], "failed_validation")
        self.assertFalse(result["generated"])

    def test_noise_cache_corruption_detected(self):
        run, _ = self.fixture()
        with zipfile.ZipFile(self.root / "audit/01_test_s1_noise.pt", "w") as output:
            output.writestr("archive/data/0", b"bad")
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertTrue(any("noise raw storage" in e for e in result["errors"]))

    def test_wrong_dimensions_rejected(self):
        run, _ = self.fixture()
        probe = lambda path: dict(self.probe(path), frames=106) if "outputs" in path.parts else self.probe(path)
        result = module.Verifier(self.root, probe).run(run)
        self.assertFalse(result["generated"])

    def test_dense_and_noise_pair_mismatches_rejected(self):
        aid, ag = self.fixture("a")
        bid, bg = self.fixture("b")
        verifier = module.Verifier(self.root, self.probe)
        a, b = verifier.run(aid), verifier.run(bid)
        b["noise_streams"][0]["sha256"] = "f" * 64
        b["dense_references"][0]["latent"]["sha256"] = "e" * 64
        pair = module.pair_validation(a, b, ag, bg)
        self.assertEqual(len(pair["errors"]), 2)

    def test_status_success_without_success_event_not_complete(self):
        run, _ = self.fixture()
        path = "logs/" + run + "_history.json"
        history = module.read_json(self.root / path)
        history["status"]["messages"] = history["status"]["messages"][:1]
        self.write(path, history)
        self.assertFalse(module.Verifier(self.root, self.probe).run(run)["generated"])

    def controls_record(self, run_id, comparison):
        return {"run_id": run_id, "source_id": "01_test", "description": "bounded same-source control",
                "paired_noise_id": "01_test_s1", "comparison_to": comparison}

    def test_control_explicit_source_id_not_inferred_from_run_name(self):
        baseline, _ = self.fixture("a")
        control, _ = self.fixture("b", run_id="costume_c_s1")
        self.write("configs/controls.json", {"jobs": [self.controls_record(control, baseline)]})
        verifier = module.Verifier(self.root, self.probe)
        rows, issues = module.validate_controls(verifier, [verifier.run(baseline)])
        self.assertEqual(issues, [])
        self.assertEqual(rows[0]["status"], "complete", rows)
        self.assertEqual(rows[0]["source_id"], "01_test")
        self.assertEqual(rows[0]["kind"], "adaptive_control")
        self.assertFalse(rows[0]["independent_sample"])

    def test_control_missing_graph_is_pending(self):
        baseline, _ = self.fixture("a")
        self.write("configs/controls.json", {"jobs": [self.controls_record("01_test_noop_s1", baseline)]})
        verifier = module.Verifier(self.root, self.probe)
        rows, issues = module.validate_controls(verifier, [verifier.run(baseline)])
        self.assertEqual(issues, [])
        self.assertEqual(rows[0]["status"], "pending")
        self.assertFalse(rows[0]["generated"])
        self.assertFalse(rows[0]["fully_archived"])

    def test_control_noise_pair_declaration_must_match(self):
        baseline, _ = self.fixture("a")
        control, _ = self.fixture("b", run_id="01_test_noop_s1")
        record = self.controls_record(control, baseline)
        record["paired_noise_id"] = "wrong_pair"
        self.write("configs/controls.json", {"jobs": [record]})
        verifier = module.Verifier(self.root, self.probe)
        rows, _ = module.validate_controls(verifier, [verifier.run(baseline)])
        self.assertEqual(rows[0]["status"], "failed_validation")

    def test_control_declared_source_must_match_loadvideo(self):
        control, _ = self.fixture("b", run_id="costume_c_s1")
        result = module.Verifier(self.root, self.probe).run(control, source_id="different", kind="adaptive_control")
        self.assertTrue(any("source_id differs" in error for error in result["errors"]))
        self.assertFalse(result["generated"])

    def test_control_can_change_semantic_observations(self):
        baseline, _ = self.fixture("a")
        control, _ = self.fixture("b", run_id="01_test_fps4_s1")
        path = "audit/" + control + "_conditioning.json"
        data = module.read_json(self.root / path)
        data["qwen_presentation"][0]["sampling"]["sample_indices"] = [0, 6, 12]
        self.write(path, data)
        self.write("configs/controls.json", {"jobs": [self.controls_record(control, baseline)]})
        verifier = module.Verifier(self.root, self.probe)
        rows, _ = module.validate_controls(verifier, [verifier.run(baseline)])
        self.assertEqual(rows[0]["status"], "complete", rows)

    def test_no_controls_file_and_separate_ledgers(self):
        self.assertEqual(module.validate_controls(module.Verifier(self.root, self.probe), []), ([], []))
        baseline, _ = self.fixture("a")
        control, _ = self.fixture("b", run_id="costume_c_s1")
        self.write("configs/queue.json", {"jobs": [baseline, control]})
        self.write("configs/controls.json", {"jobs": [self.controls_record(control, baseline)]})
        report = module.verify(self.root, self.probe)
        self.assertEqual(report["summary"]["planned_primary"], 1)
        self.assertEqual(report["summary"]["planned_adaptive_controls"], 1)
        self.assertEqual(report["summary"]["successful_adaptive_controls"], 1)
        self.assertEqual(report["summary"]["benchmark_runs_excluded"], 0)
        module.write_reports(self.root, report)
        self.assertEqual(len(module.read_json(self.root / "analysis/control_ledger.json")), 1)
        self.assertEqual(len(module.read_json(self.root / "analysis/experiment_ledger.json")), 1)

    def test_control_name_that_looks_like_ab_is_still_not_primary(self):
        baseline, _ = self.fixture("a")
        control, _ = self.fixture("b", run_id="01_test_costume_a_s1")
        self.write("configs/queue.json", {"jobs": [baseline, control]})
        self.write("configs/controls.json", {"jobs": [self.controls_record(control, baseline)]})
        report = module.verify(self.root, self.probe)
        self.assertEqual(report["summary"]["planned_primary"], 1)
        self.assertEqual(report["summary"]["planned_adaptive_controls"], 1)

    def test_control_cannot_reclassify_primary_run(self):
        baseline, _ = self.fixture("a")
        self.write("configs/controls.json", {"jobs": [self.controls_record(baseline, "some_other_run")]})
        verifier = module.Verifier(self.root, self.probe)
        rows, issues = module.validate_controls(verifier, [verifier.run(baseline)])
        self.assertEqual(rows, [])
        self.assertTrue(any("duplicates" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main(verbosity=2)
