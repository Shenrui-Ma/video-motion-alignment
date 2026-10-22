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
                    "output_sha256": module.file_hash(self.root / "inputs/01_test.mp4"),
                    "output_frames": 107, "output_fps": 24, "width": 32, "height": 32}
        self.write("inputs/01_test.json", metadata)
        self.write("inputs/source_manifest.json", {"clips": [metadata]})
        self.geometry = {"width": 32, "height": 32, "frames": 107, "fps": "24", "codec": "h264"}
        self.probe = lambda path: self.geometry.copy()

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

    def metadata(self, **updates):
        metadata = module.read_json(self.root / "inputs/01_test.json")
        metadata.update(updates)
        self.write("inputs/01_test.json", metadata)
        self.write("inputs/source_manifest.json", {"clips": [metadata]})

    def update_graph(self, run, graph):
        self.write("configs/" + run + ".json", graph)
        history = module.read_json(self.root / "logs" / (run + "_history.json"))
        history["prompt"][2] = graph
        self.write("logs/" + run + "_history.json", history)
        job = module.read_json(self.root / "logs" / (run + "_job.json"))
        job["graph_sha256"] = module.file_hash(self.root / "configs" / (run + ".json"))
        self.write("logs/" + run + "_job.json", job)

    def fixture(self, arm="a", benchmark=False, run_id=None, frames=107, reference_image=False, width=32, height=32):
        self.geometry.update(frames=frames, width=width, height=height)
        self.metadata(output_frames=frames, width=width, height=height)
        video_time = (frames - 5) // 17 * 5 + 2
        run = run_id or self.source + "_" + arm + "_s1" + ("_benchmark2" if benchmark else "")
        prompt = "edit" if arm == "a" else "edit and retain event"
        graph = {
            "5": {"class_type": "H3EventAuditReference", "inputs": {"run_id": run, "prompt": prompt,
                    "width": width, "height": height, "length": frames, "ref_video": ["22", 0]}},
            "6": {"class_type": "H3EventAuditNoise", "inputs": {"run_id": run, "pair_id": "01_test_s1", "noise_seed": 42}},
            "9": {"class_type": "ManualSigmas", "inputs": {"sigmas": ",".join(["1"] * (2 if benchmark else 20) + ["0"])}},
            "10": {"class_type": "SamplerCustomAdvanced", "inputs": {"latent_image": ["5", 1], "noise": ["6", 0], "sigmas": ["9", 0]}},
            "14": {"class_type": "SaveVideo", "inputs": {"filename_prefix": run, "video": ["10", 0]}},
            "22": {"class_type": "LoadVideo", "inputs": {"file": "01_test.mp4"}}}
        if arm == "a":
            graph["34"] = {"class_type": "SaveVideo", "inputs": {"filename_prefix": "diagnostic", "video": ["5", 2]}}
        if reference_image:
            image_path = self.root / "inputs/character.png"
            image_path.write_bytes(b"reference-image")
            self.metadata(reference_image={"file": image_path.name, "sha256": module.file_hash(image_path)})
            graph["23"] = {"class_type": "LoadImage", "inputs": {"image": image_path.name}}
            graph["5"]["inputs"]["ref_image"] = ["23", 0]
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
        prepared, _ = self.tensor([frames, height, width, 3])
        latent, _ = self.tensor([1, 24, video_time, height // 16, width // 16], byte=1)
        sampled, _ = self.tensor([9, height, width, 3])
        video_noise, video_payload = self.tensor([1, 24, video_time, height // 16, width // 16], byte=2, save=False)
        audio_noise, audio_payload = self.tensor([1, 32, 2, round(frames / 24 * 40)], byte=3, save=False)
        shapes = [video_noise["shape"], audio_noise["shape"]]
        cond = {"run_id": run, "prompt": prompt, "input_video": prepared,
                "native_vae_calls": [{"prepared_frames": prepared, "latent": latent}],
                "qwen_presentation": [{"type": "video", "sampling": {"sample_indices": [0, 12]}, "actual_sampled_frames": sampled}],
                "target_latent_shapes": shapes}
        if reference_image:
            pixels, _ = self.tensor([1, 32, 32, 3], byte=4)
            image_latent, _ = self.tensor([1, 24, 1, 2, 2], byte=5)
            cond["native_vae_calls"].insert(0, {"prepared_frames": pixels, "latent": image_latent})
            qwen_pixels, _ = self.tensor([1, 32, 32, 3], byte=4, save=False)
            cond["qwen_presentation"].insert(0, {"type": "image", "data": {"tensor": qwen_pixels}})
        self.write("audit/" + run + "_conditioning.json", cond)
        noise = {"run_id": run, "pair_id": "01_test_s1", "signature": {"seed": 42, "nested": True,
                 "shapes": shapes, "dtypes": ["torch.float32", "torch.float32"], "batch_index": None},
                 "actual_noise_streams": [video_noise, audio_noise], "cache_file": "/remote/audit/01_test_s1_noise.pt"}
        self.write("audit/" + run + "_noise.json", noise)
        with zipfile.ZipFile(self.root / "audit/01_test_s1_noise.pt", "w") as output_zip:
            output_zip.writestr("archive/data/0", video_payload)
            output_zip.writestr("archive/data/1", audio_payload)
        return run, graph

    def test_all_legal_extended_frame_counts_derive_av_geometry(self):
        for frames in (107, 124, 141, 158):
            with self.subTest(frames=frames):
                run, _ = self.fixture(frames=frames)
                result = module.Verifier(self.root, self.probe).run(run)
                self.assertEqual(result["status"], "complete", result)
                self.assertEqual(result["expected_frames"], frames)
                self.assertEqual(result["noise_streams"][0]["shape"][2], (frames - 5) // 17 * 5 + 2)
                self.assertEqual(result["noise_streams"][1]["shape"][-1], round(frames / 24 * 40))

    def test_illegal_frame_grid_is_rejected_even_when_all_shapes_agree(self):
        run, _ = self.fixture(frames=140)
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertEqual(result["status"], "failed_validation")
        self.assertIn("source output_frames must be on the H3 17k+5 frame grid", result["errors"])

    def test_variable_dimensions_must_match_source_metadata(self):
        run, graph = self.fixture(frames=141, width=64, height=96)
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertEqual(result["status"], "complete", result)
        self.assertEqual(result["noise_streams"][0]["shape"], [1, 24, 42, 6, 4])
        graph["5"]["inputs"]["width"] = 96
        self.update_graph(run, graph)
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertIn("graph/source metadata dimensions must match and be multiples of 32", result["errors"])

    def test_graph_off_by_one_length_is_rejected(self):
        run, graph = self.fixture(frames=141)
        graph["5"]["inputs"]["length"] = 140
        self.update_graph(run, graph)
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertIn("graph frame count differs from source metadata output_frames", result["errors"])

    def test_longer_source_cannot_reuse_107_frame_noise(self):
        run, _ = self.fixture()
        old_noise = module.read_json(self.root / "audit" / (run + "_noise.json"))
        self.fixture(frames=141)
        self.write("audit/" + run + "_noise.json", old_noise)
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertIn("noise shapes do not match source-frame H3 AV geometry", result["errors"])

    def test_source_manifest_geometry_mismatch_is_rejected(self):
        run, _ = self.fixture(frames=141)
        manifest = module.read_json(self.root / "inputs/source_manifest.json")
        manifest["clips"][0]["output_frames"] = 107
        self.write("inputs/source_manifest.json", manifest)
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertIn("per-source metadata differs from source_manifest", result["errors"])

    def test_complete_reference_image_pair(self):
        aid, ag = self.fixture("a", frames=141, reference_image=True)
        bid, bg = self.fixture("b", frames=141, reference_image=True)
        verifier = module.Verifier(self.root, self.probe)
        a, b = verifier.run(aid), verifier.run(bid)
        self.assertEqual(a["status"], "complete", a)
        self.assertEqual(b["status"], "complete", b)
        self.assertEqual(module.pair_validation(a, b, ag, bg)["status"], "pass")
        self.assertEqual(a["reference_image"]["file"], "character.png")

    def test_missing_reference_image_prevents_complete_archive(self):
        run, _ = self.fixture(reference_image=True)
        (self.root / "inputs/character.png").unlink()
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertFalse(result["fully_archived"])
        self.assertIn("inputs/character.png", result["missing"])

    def test_changed_reference_image_is_rejected(self):
        run, _ = self.fixture(reference_image=True)
        (self.root / "inputs/character.png").write_bytes(b"different-character")
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertIn("reference image file SHA256 mismatch", result["errors"])

    def test_image_loader_must_match_metadata_and_be_unique(self):
        run, graph = self.fixture(reference_image=True)
        graph["23"]["inputs"]["image"] = "different.png"
        self.update_graph(run, graph)
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertIn("ref_image must have exactly one LoadImage ancestor matching metadata", result["errors"])
        graph["23"]["inputs"]["image"] = "character.png"
        graph["24"] = copy.deepcopy(graph["23"])
        graph["25"] = {"class_type": "ImageBatch", "inputs": {"a": ["23", 0], "b": ["24", 0]}}
        graph["5"]["inputs"]["ref_image"] = ["25", 0]
        self.update_graph(run, graph)
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertIn("ref_image must have exactly one LoadImage ancestor matching metadata", result["errors"])

    def test_image_metadata_without_graph_connection_is_rejected(self):
        run, graph = self.fixture(reference_image=True)
        del graph["5"]["inputs"]["ref_image"]
        self.update_graph(run, graph)
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertIn("reference image metadata requires a connected ref_image graph input", result["errors"])

    def test_image_runtime_evidence_cannot_be_omitted(self):
        run, _ = self.fixture(reference_image=True)
        path = "audit/" + run + "_conditioning.json"
        condition = module.read_json(self.root / path)
        condition["qwen_presentation"] = [p for p in condition["qwen_presentation"] if p["type"] != "image"]
        self.write(path, condition)
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertIn("reference image dense/Qwen evidence count mismatch", result["errors"])

    def test_pair_image_qwen_tensor_mismatch_is_rejected(self):
        aid, ag = self.fixture("a", reference_image=True)
        bid, bg = self.fixture("b", reference_image=True)
        path = "audit/" + bid + "_conditioning.json"
        condition = module.read_json(self.root / path)
        pixels, _ = self.tensor([1, 32, 32, 3], byte=6, save=False)
        condition["qwen_presentation"][0]["data"]["tensor"] = pixels
        prepared, _ = self.tensor([1, 32, 32, 3], byte=6)
        condition["native_vae_calls"][0]["prepared_frames"] = prepared
        self.write(path, condition)
        verifier = module.Verifier(self.root, self.probe)
        a, b = verifier.run(aid), verifier.run(bid)
        self.assertEqual(b["status"], "complete", b)
        pair = module.pair_validation(a, b, ag, bg)
        self.assertIn("paired qwen_image_observations mismatch", pair["errors"])
        b["reference_image"]["sha256"] = "f" * 64
        pair = module.pair_validation(a, b, ag, bg)
        self.assertIn("paired reference_image mismatch", pair["errors"])

    def test_image_qwen_pixels_must_match_native_prepared_pixels(self):
        run, _ = self.fixture(reference_image=True)
        path = "audit/" + run + "_conditioning.json"
        condition = module.read_json(self.root / path)
        pixels, _ = self.tensor([1, 32, 32, 3], byte=6, save=False)
        condition["qwen_presentation"][0]["data"]["tensor"] = pixels
        self.write(path, condition)
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertIn("reference image Qwen pixels differ from native prepared image", result["errors"])

    def test_reference_image_graph_without_metadata_is_rejected(self):
        run, _ = self.fixture(reference_image=True)
        self.metadata(reference_image=None)
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertIn("reference image requires per-source reference_image metadata", result["errors"])

    def test_dense_video_length_mismatch_is_rejected(self):
        run, _ = self.fixture(frames=141)
        path = "audit/" + run + "_conditioning.json"
        condition = module.read_json(self.root / path)
        prepared, _ = self.tensor([140, 32, 32, 3])
        condition["native_vae_calls"][0]["prepared_frames"] = prepared
        self.write(path, condition)
        result = module.Verifier(self.root, self.probe).run(run)
        self.assertIn("dense video reference geometry/count mismatch", result["errors"])

    def test_single_source_four_run_matrix_is_complete(self):
        jobs = [self.fixture(arm, run_id=f"01_test_{arm}_s{seed}")[0]
                for seed in (1, 2) for arm in ("a", "b")]
        self.write("configs/queue.json", {"jobs": jobs})
        result = module.verify(self.root, self.probe)
        self.assertEqual(result["status"], "complete", result["issues"])
        self.assertEqual(result["summary"]["planned_primary"], 4)
        self.assertEqual(result["summary"]["valid_pairs"], 2)

    def test_single_source_missing_or_duplicate_arm_is_rejected(self):
        jobs = [self.fixture(arm, run_id=f"01_test_{arm}_s{seed}")[0]
                for seed in (1, 2) for arm in ("a", "b")]
        for wrong in (jobs[:-1], jobs[:-1] + [jobs[0]]):
            self.write("configs/queue.json", {"jobs": wrong})
            result = module.verify(self.root, self.probe)
            self.assertEqual(result["status"], "failed_validation")
            self.assertTrue(any("exactly match" in x for x in result["issues"]))

    def test_empty_source_manifest_cannot_be_complete(self):
        self.write("inputs/source_manifest.json", {"clips": []})
        self.write("configs/queue.json", {"jobs": []})
        result = module.verify(self.root, self.probe)
        self.assertEqual(result["status"], "failed_validation")

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
