"""Synthetic denominator/provenance fault tests; no real result is invented."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("paired_cohorts", Path(__file__).with_name("paired_cohorts.py"))
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def fixture():
    status, official, manifest, frozen, visuals = {"jobs": []}, {"cases": []}, {"jobs": []}, {}, {}
    tasks = [t for ts in mod.COHORTS.values() for t in ts]
    for i, task in enumerate(tasks):
        method = "temporal_gain_field"
        jid = task + "__test"
        hashes = {role: hashlib.sha256((task + role).encode()).hexdigest() for role in mod.ROLES}
        sha = hashlib.sha256(jid.encode()).hexdigest()
        offsets = (2, 4, 30, 40)
        weak = (1, 2, 3, 4)[i]
        n_events = (2, 4, 3, 3)[i]
        events = [{"id": str(j), "source": [j * 20, j * 20 + 1],
                   "native": [j * 20 + 5, j * 20 + 6],
                   "global_weak": [j * 20 + weak, j * 20 + weak + 1],
                   "status_by_role": {role: "measured" for role in mod.ROLES}}
                  for j in range(n_events)]
        frozen[task] = {"case_id": task, "fps": 24, "valid_frames": 200,
                        "video_provenance": {r: {"sha256": h} for r, h in hashes.items()},
                        "events": events, "means": {"native": 5, "global_weak": weak}}
        controls = {}
        for role in mod.ROLES:
            cid = task + "__" + role
            rec = {"id": cid, "task_id": task, "method": role, "sha256": hashes[role],
                   "fps": 24, "valid_frames": 200, "timing": {"sampling_seconds": 100, "mean_step_seconds": 5}}
            manifest["jobs"].append(rec)
            score = (1.0 - i / 10) if role == "source" else .6
            controls[role] = {"job_id": cid, "metrics": {k: {"status": "done", "score": score} for k in mod.METRICS}}
        status["jobs"].append({"job_id": jid, "task_id": task, "method": method, "status": "verified",
                               "media": [{"actual_sha256": sha, "status": "verified"}],
                               "timing": {"sampling_seconds": 20 + i * 10, "mean_sampling_step_seconds": 1 + i / 2}})
        official["cases"].append({"job_id": jid, "task_id": task, "method": method,
                                   "metrics": {k: {"status": "done", "score": .8 + .01 * i} for k in mod.METRICS},
                                   "controls": controls})
        visuals[jid] = {"provenance": {"job_id": jid, "method": method, "generated_sha256": sha,
                                       "fps": 24, "valid_frames": 200,
                                       "controls": [{"id": task + "__" + r, "sha256": h} for r, h in hashes.items()]},
                        "annotation": {"job_id": jid, "task_id": task, "method": method, "video_sha256": sha,
                                       "fps": 24, "events": [{"id": e["id"], "source_interval": e["source"],
                                           "new_interval": [n + offsets[i] for n in e["source"]],
                                           "signed_offset_frames": offsets[i], "event_present": True} for e in events],
                                       "mean_absolute_offset_frames": offsets[i]}}
    return status, official, manifest, frozen, visuals


def target(report, cohort="original_pilots"):
    return report["cohorts"][cohort]["methods"]["temporal_gain_field"]


class PairedTests(unittest.TestCase):
    def test_complete_video_weighted_and_reference_pairing(self):
        out = target(mod.summarize(*fixture()))
        self.assertEqual(out["mean_absolute_event_offset_frames"]["complete_mean"], 3)
        self.assertEqual(out["event_delta_from_weak"]["complete_mean"], 1.5)
        self.assertAlmostEqual(out["metrics"]["motion_fidelity"]["complete_mean"], .805)
        self.assertAlmostEqual(out["delta_from_weak"]["motion_fidelity"]["complete_mean"], .205)
        self.assertAlmostEqual(out["mf_delta_from_reference"]["complete_mean"], -.145)
        self.assertEqual(out["timing"]["sampling_seconds"]["complete_mean"], 25)
        self.assertIsNone(out["metrics"]["motion_fidelity"]["partial_mean"])

    def test_pending_and_unverified_never_make_complete(self):
        args = fixture()
        args[1]["cases"][1]["metrics"]["motion_fidelity"] = {"status": "pending", "score": None}
        out = target(mod.summarize(*args))["metrics"]["motion_fidelity"]
        self.assertEqual(out["n_done"], 1)
        self.assertIsNone(out["complete_mean"])
        self.assertEqual(out["partial_mean"], .8)
        args = fixture()
        args[0]["jobs"][1]["status"] = "research_hold"
        out = target(mod.summarize(*args))
        self.assertEqual(out["n_verified"], 1)
        self.assertEqual(out["metrics"]["motion_fidelity"]["status_counts"], {"done": 1, "unverified": 1})
        self.assertIsNone(out["mean_absolute_event_offset_frames"]["complete_mean"])

    def test_na_nonfinite_and_sentinel_are_not_scores(self):
        for item, state in (({"status": "not_applicable", "score": None}, "not_applicable"),
                            ({"status": "done", "score": float("nan")}, "invalid"),
                            ({"status": "done", "score": -1}, "invalid")):
            with self.subTest(state=state):
                args = fixture()
                args[1]["cases"][1]["metrics"]["motion_fidelity"] = item
                out = target(mod.summarize(*args))["metrics"]["motion_fidelity"]
                self.assertEqual(out["n_done"], 1)
                self.assertEqual(out["n_expected"], 2)
                self.assertEqual(out["status_counts"][state], 1)
                self.assertIsNone(out["complete_mean"])

    def test_duplicates_rejected(self):
        for mutation in ("status_id", "task_method", "metric_id"):
            args = fixture()
            if mutation == "metric_id":
                args[1]["cases"].append(copy.deepcopy(args[1]["cases"][0]))
            else:
                row = copy.deepcopy(args[0]["jobs"][0])
                if mutation == "task_method":
                    row["job_id"] += "_duplicate"
                args[0]["jobs"].append(row)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, "duplicate"):
                mod.summarize(*args)

    def test_missing_annotation_and_incomplete_events(self):
        args = fixture()
        jid = args[0]["jobs"][1]["job_id"]
        args[4].pop(jid)
        out = target(mod.summarize(*args))["mean_absolute_event_offset_frames"]
        self.assertEqual(out["partial_mean"], 2)
        self.assertIsNone(out["complete_mean"])
        args = fixture()
        a = args[4][jid]["annotation"]
        a["events"][0]["new_interval"] = None
        a["events"][0]["signed_offset_frames"] = None
        a["mean_absolute_offset_frames"] = None
        out = target(mod.summarize(*args))
        self.assertEqual(out["cases"][1]["events"]["n_events_done"], 3)
        self.assertIsNone(out["cases"][1]["events"]["score"])
        self.assertEqual(out["mean_absolute_event_offset_frames"]["n_done"], 1)
        a["events"].pop()
        with self.assertRaisesRegex(ValueError, "event IDs"):
            mod.summarize(*args)

    def test_mismatched_controls_and_source_intervals_rejected(self):
        for mutation in ("manifest", "metric_control", "visual_sha", "visual_control", "source_interval"):
            args = fixture()
            jid = args[0]["jobs"][0]["job_id"]
            if mutation == "manifest":
                args[2]["jobs"][0]["sha256"] = "wrong"
            elif mutation == "metric_control":
                args[1]["cases"][0]["controls"]["global_weak"]["job_id"] = "other"
            elif mutation == "visual_sha":
                args[4][jid]["annotation"]["video_sha256"] = "wrong"
            elif mutation == "visual_control":
                args[4][jid]["provenance"]["controls"][0]["sha256"] = "wrong"
            else:
                args[4][jid]["annotation"]["events"][0]["source_interval"] = [2, 3]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                mod.summarize(*args)

    def test_cohorts_never_mix_and_absent_side_keeps_denominator(self):
        args = fixture()
        report = mod.summarize(*args)
        self.assertEqual(target(report)["mean_absolute_event_offset_frames"]["complete_mean"], 3)
        self.assertEqual(target(report, "book_handkerchief_extension")["mean_absolute_event_offset_frames"]["complete_mean"], 35)
        args[0]["jobs"].pop(1)
        args[1]["cases"].pop(1)
        out = target(mod.summarize(*args))["metrics"]["motion_fidelity"]
        self.assertEqual((out["n_done"], out["n_expected"]), (1, 2))
        with self.assertRaisesRegex(ValueError, "overlap"):
            mod.summarize(*fixture(), cohorts={"a": ("short_0252",), "b": ("short_0252",)})

    def test_repeated_control_scores_must_match(self):
        args = fixture()
        row = copy.deepcopy(args[0]["jobs"][0])
        case = copy.deepcopy(args[1]["cases"][0])
        for item in (row, case):
            item["method"] = "other"
            item["job_id"] += "_other"
        case["controls"]["source"]["metrics"]["motion_fidelity"]["score"] = .7
        args[0]["jobs"].append(row)
        args[1]["cases"].append(case)
        with self.assertRaisesRegex(ValueError, "repeated control"):
            mod.summarize(*args)

    def test_csv_has_separate_complete_partial_columns(self):
        args = fixture()
        args[0]["jobs"][1]["status"] = "pending"
        rows = list(mod.csv_rows(mod.summarize(*args)))
        mf = next(r for r in rows if r["cohort"] == "original_pilots" and r["method"] == "temporal_gain_field" and
                  r["measure"] == "metrics" and r["metric"] == "motion_fidelity")
        self.assertEqual((mf["n_done"], mf["n_expected"], mf["complete_mean"], mf["partial_mean"]), (1, 2, None, .8))
        self.assertFalse(any(r["metric"] in ("instruction_satisfaction", "content_fidelity") for r in rows))

    def test_file_inputs_are_hashed_and_importable(self):
        status, official, manifest, frozen, visuals = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            e = Path(tmp)
            latest = e / "latest"
            latest.mkdir()
            (latest / "status.json").write_text(json.dumps(status))
            (latest / "official_metrics.json").write_text(json.dumps(official))
            (e / "metrics").mkdir()
            (e / "metrics/manifest.json").write_text(json.dumps(manifest))
            for task, f in frozen.items():
                p = e / f"timing/event_offset_completion_20261022/{task}"
                p.mkdir(parents=True)
                (p / "ANNOTATION.json").write_text(json.dumps(f))
            for row in status["jobs"]:
                p = e / "showcases/adaptive_strength_20261023/visual" / row["task_id"] / row["method"]
                p.mkdir(parents=True)
                for name, key in (("ANNOTATION.json", "annotation"), ("PROVENANCE.json", "provenance")):
                    (p / name).write_text(json.dumps(visuals[row["job_id"]][key]))
            report = mod.load_and_summarize(latest, e)
            self.assertEqual(len(report["inputs_sha256"]), 15)
            self.assertEqual(report["code_sha256"], hashlib.sha256(Path(mod.__file__).read_bytes()).hexdigest())
            self.assertEqual(target(report)["mean_absolute_event_offset_frames"]["complete_mean"], 3)


if __name__ == "__main__":
    unittest.main()
