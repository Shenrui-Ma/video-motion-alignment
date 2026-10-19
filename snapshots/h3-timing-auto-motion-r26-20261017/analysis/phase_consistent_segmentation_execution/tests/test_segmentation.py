import itertools
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import segmentation as s


def features(total=141, shift=0, rotation=None, missing=None, periodic=False):
    t = np.arange(total, dtype=float) - shift
    vectors = []
    for bone in range(4):
        angle = (2 * np.pi * t / 12 + 0.1 * bone if periodic else
                 0.013 * t + 0.00019 * t * t + 0.17 * np.sin(0.083 * t + 0.4 * bone))
        if rotation is not None:
            angle = angle + rotation
        vectors.append(np.stack((np.cos(angle), np.sin(angle)), axis=-1))
    vectors = np.stack(vectors, axis=1)
    confidence = np.ones((total, 4))
    if missing is not None:
        vectors[missing] = np.nan
        confidence[missing] = 0
    values = {"raw": {"video": {"fps": 24}}, "times": np.arange(total) / 24,
              "frames": np.arange(total)}
    for part, sl in (("left_arm", slice(0, 2)), ("right_arm", slice(2, 4))):
        values[part + "_direction"] = vectors[:, sl]
        values[part + "_conf"] = confidence[:, sl]
    return {threshold: values for threshold in s.THRESHOLDS}


def scan(source, target):
    example = source[0.3]
    return s.full_scan(source, target, example["times"], 24)


def row(a, b, value, lag=6, part="left_arm"):
    return {"start": a, "end": b, "value": value, "lag": lag, "part": part}


class ArithmeticTests(unittest.TestCase):
    def test_nonfinite_raw_confidence_is_unknown(self):
        a, b = features(total=30), features(total=30)
        context = s.contexts(a, b, "left_arm", a[0.3]["times"], 24)[0]
        context.targets[0][1][10, 0] = np.inf
        context.targets[0][1][11, 0] = np.nan
        context.targets[0][1][12, 0] = 0.2
        valid, weight = s.common_arrays(context, (*s.NULL, 6))
        self.assertFalse(valid[10:13, 0].any())
        self.assertTrue((weight[10:13, 0] == 0).all())

    def test_only_named_scientific_missingness_becomes_unknown(self):
        with patch.object(s, "load_pose", side_effect=ValueError("Insufficient reliable torso anchors for scale normalization")):
            result, failures = s.load_thresholds("unused")
            self.assertTrue(all(v is None for v in result.values()))
            self.assertEqual(len(failures), 2)
        for error in (ValueError("invalid array shape"), json.JSONDecodeError("bad json", "x", 0)):
            with patch.object(s, "load_pose", side_effect=error):
                with self.assertRaises(type(error)):
                    s.load_thresholds("unused")

    def test_zero_based_closed_interval_sums(self):
        sums = s.interval_sums(np.array([1, 2, 4, 8]))
        self.assertEqual(sums[0, 0], 1)
        self.assertEqual(sums[1, 3], 14)

    def test_structural_code(self):
        self.assertEqual(s.code_cost(141, 16), 25)
        self.assertGreater(s.code_cost(141, 32), s.code_cost(141, 16))
        with self.assertRaises(ValueError):
            s.code_cost(141, 0)

    def test_common_weights_include_every_null(self):
        shape = (10, 2, 2)
        x = np.zeros(shape); x[..., 0] = 1
        targets = {d: (x.copy(), np.full((10, 2), 0.9)) for d in s.SEARCH}
        targets[-2][1][3, 0] = 0.31
        context = s.Context(x, np.full((10, 2), 0.8), targets, 0.3, "left_arm")
        known, w = s.common_arrays(context, (*s.NULL, 6))
        self.assertTrue(known.all())
        self.assertEqual(w[3, 0], 0.31)

    def test_unknown_never_increases_fixed_slot_evidence(self):
        a, b = features(), features(shift=6)
        context = s.contexts(a, b, "left_arm", a[0.3]["times"], 24)[0]
        before = s.slot_evidence(context, 6)["gain"].copy()
        context.targets[-2][0][40, 0] = np.nan
        after = s.slot_evidence(context, 6)
        self.assertEqual(after["gain"][40, 0], -1)
        self.assertFalse(after["valid"][40, 0])
        self.assertTrue(np.all(after["gain"] <= before + 1e-12))

    def test_complete_missing_frame_breaks_intervals(self):
        a, b = features(total=45), features(total=45, missing=20)
        block = scan(a, b)["left_arm"]
        for i, lag in enumerate(s.PROPOSALS):
            self.assertFalse(block["feasible"][i, 5, 35])

    def test_empty_calibration_stays_unknown(self):
        a = features(total=20)
        b = features(total=20, missing=slice(None))
        result = s.calibration_max([("masked", scan(a, b))])
        self.assertEqual(result["status"], "UNKNOWN_CALIBRATION")
        self.assertIsNone(result["lambda"])


class DynamicProgrammingTests(unittest.TestCase):
    def test_partial_visible_coverage_is_not_nominal_coverage(self):
        observed = [[20, 0], [20, 1], [21, 0]]
        proposal = row(20, 21, 1)
        proposal.update(status="PHASE_CANDIDATE_DELAY", support=[{"known_slot_indices": observed}, {"known_slot_indices": observed[:2]}])
        observability = {p: {"nominal_slots": 100, "known_null_slots": 60} for p in s.PARTS}
        metric = s.method_coverage({"selected": [proposal]}, observability)
        self.assertEqual(metric["qualified_nominal_slots"], 4)
        self.assertEqual(metric["qualified_known_slots_both_thresholds"], 2)
        self.assertEqual(metric["nominal_slots_denominator"], 200)

    def test_persistence_requires_adjacent_endpoints_and_observed_overlap(self):
        a = row(20, 27, 1, 6)
        a.update(status="PHASE_CANDIDATE_DELAY", support=[{"known_slot_indices": [[20, 0]]}] * 2)
        b = row(20, 27, 1, 8)
        b.update(status="PHASE_CANDIDATE_DELAY", support=[{"known_slot_indices": [[21, 0]]}] * 2)
        self.assertEqual(s.adjacent_persistence({3: {"selected": [a]}, 4: {"selected": [b]}})["pairs"], [])
        b["support"] = a["support"]
        self.assertEqual(len(s.adjacent_persistence({3: {"selected": [a]}, 4: {"selected": [b]}})["pairs"]), 1)
        self.assertEqual(s.adjacent_persistence({3: {"selected": [a]}, 5: {"selected": [b]}})["pairs"], [])

    def test_advance_persistence_and_opposite_sign(self):
        a = row(20, 27, 1, -6)
        a.update(status="PHASE_CANDIDATE_ADVANCE", support=[{"known_slot_indices": [[20, 0]]}] * 2)
        b = a | {"lag": -8}
        result = s.adjacent_persistence({3: {"selected": [a]}, 4: {"selected": [b]}})
        self.assertEqual(result["advance_pairs"], 1)
        self.assertEqual(result["delay_pairs"], 0)
        b = b | {"lag": 6, "status": "PHASE_CANDIDATE_DELAY"}
        self.assertEqual(s.adjacent_persistence({3: {"selected": [a]}, 4: {"selected": [b]}})["pairs"], [])

    def test_closed_intervals_and_uncovered_frames(self):
        result = s.solve_intervals([row(0, 7, 4), row(8, 15, 5)], 16)
        self.assertEqual(result["K"], 2)
        self.assertEqual(result["objective"], 9)

    def test_short_positive_region_can_exclude_negative_tail(self):
        result = s.solve_intervals([row(20, 35, 7), row(20, 43, 3)], 50)
        self.assertEqual(result["selected"][0]["end"], 35)

    def test_zero_and_negative_rewards_choose_K0(self):
        result = s.solve_intervals([row(0, 7, 0), row(8, 15, -1)], 16)
        self.assertEqual(result["K"], 0)

    def test_fewer_segments_tie_break(self):
        result = s.solve_intervals([row(0, 7, 2), row(8, 15, 2), row(0, 15, 4)], 16)
        self.assertEqual(result["K"], 1)

    def test_lexical_phase_tie_break(self):
        result = s.solve_intervals([row(0, 7, 4, 7), row(0, 7, 4, -6), row(0, 7, 4, 6)], 8)
        self.assertEqual(result["selected"][0]["lag"], -6)

    def test_exhaustive_equivalence(self):
        rows = [row(0, 7, 2), row(2, 9, 3), row(8, 15, 4), row(10, 17, 3),
                row(0, 17, 6), row(18, 25, 1), row(5, 12, 2)]
        candidates = []
        for flags in itertools.product((0, 1), repeat=len(rows)):
            chosen = sorted([r for r, flag in zip(rows, flags) if flag], key=s._key)
            if all(chosen[i]["end"] < chosen[i + 1]["start"] for i in range(len(chosen) - 1)):
                candidates.append((sum(r["value"] for r in chosen), chosen))
        best = sorted(candidates, key=lambda v: (-v[0], len(v[1]), tuple(map(s._key, v[1]))))[0]
        actual = s.solve_intervals(rows, 26)
        self.assertEqual(actual["objective"], best[0])
        self.assertEqual(actual["selected"], best[1])

    def test_cross_limb_overlap_is_allowed(self):
        total = 16
        cost, length = s.code_grid(total)
        blocks = {}
        for p in s.PARTS:
            gain = np.zeros((44, total, total))
            valid = np.zeros_like(gain, dtype=bool)
            gain[0, 0, 7] = 3
            valid[0, 0, 7] = True
            blocks[p] = {"gain": gain, "feasible": valid, "cost": cost, "length": length}
        self.assertEqual(s.select(blocks, 0)["K"], 2)
        self.assertEqual(s.select(blocks, 0, cross_part_exclusion=True)["K"], 1)


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = features()
        cls.identity_scan = scan(cls.source, features())

    def test_identity_no_phase_deviation(self):
        self.assertEqual(s.select(self.identity_scan, 0)["K"], 0)

    def test_zero_lambda_is_literal_zero(self):
        result = s.calibration_max([("identity_view", self.identity_scan)])
        self.assertEqual(result["status"], "zero_empirical_scale")
        self.assertEqual(result["lambda"], 0)

    def test_all_null_tolerance_shifts(self):
        for lag in (-2, -1, 1, 2):
            with self.subTest(lag=lag):
                block = scan(self.source, features(shift=lag))
                self.assertEqual(s.select(block, 0)["K"], 0)

    def test_delayed_and_advanced_phase_controls(self):
        for lag in (-12, -6, 6, 12):
            with self.subTest(lag=lag):
                block = scan(self.source, features(shift=lag))
                result = s.evaluate(block, 0)["proposal"]
                accepted = [r for r in result["selected"] if r["status"].startswith("PHASE_CANDIDATE")]
                self.assertTrue(accepted)
                self.assertEqual({r["part"] for r in accepted}, set(s.PARTS))
                self.assertTrue(all(abs(r["lag"] - lag) <= 2 for r in accepted))

    def test_periodic_phase_remains_ambiguous(self):
        a, b = features(periodic=True), features(shift=6, periodic=True)
        block = scan(a, b)
        result = s.evaluate(block, 0)["proposal"]
        self.assertTrue(result["selected"])
        self.assertEqual(result["qualified_K"], 0)
        self.assertTrue(any("UNKNOWN_MULTIPLE_PHASES" in r["reasons"] for r in result["selected"]))

    def test_search_boundary_rejected(self):
        context = s.contexts(self.source, features(shift=24), "left_arm", self.source[0.3]["times"], 24)
        result = s.phase_check(row(35, 50, 1, 24), context)
        self.assertIn("UNKNOWN_SEARCH_BOUNDARY", result["reasons"])

    def test_competitor_support_unknown_retained(self):
        context = s.contexts(self.source, features(shift=6), "left_arm", self.source[0.3]["times"], 24)
        result = s.phase_check(row(3, 14, 1, 6), context)
        self.assertIn("UNKNOWN_PHASE_COMPARISON", result["reasons"])
        self.assertTrue(any(r["status"] == "UNKNOWN_PHASE_COMPARISON" for r in result["competitors"]))

    def test_empirical_maximum_bounds_entire_calibration_family(self):
        perturbation = np.repeat(np.array([0.1, -0.1]), 16)
        perturbation = np.resize(perturbation, 141)
        block = scan(self.source, features(rotation=perturbation))
        result = s.calibration_max([("source_perturbation", block)])
        self.assertIsNotNone(result["lambda"])
        for part in s.PARTS:
            b = block[part]
            v = b["gain"] - result["lambda"] * b["cost"][None]
            self.assertLessEqual(float(v[b["feasible"]].max()), 1e-12)

    def test_final_rejection_keeps_selected_proposal(self):
        a, b = features(periodic=True), features(shift=6, periodic=True)
        block = scan(a, b)
        raw = s.select(block, 0)
        checked = s.evaluate(block, 0)["proposal"]
        self.assertEqual([s._key(r) for r in raw["selected"]], [s._key(r) for r in checked["selected"]])

    def test_fully_occluded_frames_remain_unknown(self):
        block = scan(self.source, features(missing=slice(None)))
        observable = s.frame_observability(block)
        self.assertTrue(all(set(v["base_frame_labels"]) == {"UNKNOWN"} for v in observable.values()))


class AdmissionTests(unittest.TestCase):
    def test_authorization_rejects_integer_one(self):
        import run_once
        fake = {"authorized": 1, "phase": "calibration", "execution_freeze_sha256": "sealed",
                "design_freeze_sha256": run_once.DESIGN_SHA, "inputs_sha256": run_once.INPUT_SHA}
        with patch.object(run_once, "verify_execution", return_value="sealed"), patch.object(run_once, "read", return_value=fake):
            with self.assertRaises(ValueError):
                run_once.authorize("calibration")

    def test_grid_rejects_nonfinite_fps_and_times(self):
        import run_once
        data = {"video": {"fps": 24}, "frames": [{"frame": i, "time_s": i / 24} for i in range(141)]}
        self.assertEqual(run_once.validate_grid(data)["records"], 141)
        for bad in (float("nan"), float("inf"), 25, True):
            with self.assertRaises(ValueError):
                run_once.validate_grid(data | {"video": {"fps": bad}})
        data["frames"][5]["time_s"] = float("nan")
        with self.assertRaises(ValueError):
            run_once.validate_grid(data)

    def test_atomic_commit_rechecks_and_leaves_no_partial_marker(self):
        import run_once
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "audit") as tmp:
            p = Path(tmp) / "COMPLETE.json"
            with patch.object(run_once, "require_record", side_effect=TimeoutError("simulated interruption before commit")):
                with self.assertRaises(TimeoutError):
                    run_once.commit_new(p, {"status": "complete", "files": []}, [{"path": "unused"}])
            self.assertFalse(p.exists())
            self.assertEqual(list(Path(tmp).iterdir()), [])
            run_once.commit_new(p, {"status": "complete", "files": []}, [])
            self.assertEqual(json.loads(p.read_text())["status"], "complete")
            with self.assertRaises(FileExistsError):
                run_once.commit_new(p, {"status": "changed"}, [])

    def test_corrupt_complete_marker_is_explicit_error(self):
        import run_once
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "audit") as tmp:
            p = Path(tmp) / "COMPLETE.json"
            p.write_text('{"status":')
            with self.assertRaisesRegex(ValueError, "Partial/corrupt"):
                run_once.ensure_no_complete(p)

    def test_root_authorization_is_required_for_real_numerics(self):
        import run_once
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "audit") as tmp:
            with patch.object(run_once, "HERE", Path(tmp)), patch.object(run_once, "verify_execution", return_value="sealed"):
                with self.assertRaises(FileNotFoundError):
                    run_once.authorize("calibration")

    def test_exclusive_result_writer_preserves_existing_evidence(self):
        import run_once
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "audit") as tmp:
            p = Path(tmp) / "result.json"
            run_once.write_new(p, {"original": True})
            with self.assertRaises(FileExistsError):
                run_once.write_new(p, {"original": False})
            self.assertEqual(json.loads(p.read_text()), {"original": True})


def stress_report():
    """Known zero-time-warp geometric errors; report failures without retuning."""
    source = features()
    rows = []
    for block_length, amplitude, sign in itertools.product((8, 16), (0.05, 0.10), (-1, 1)):
        rotation = sign * amplitude * np.where((np.arange(141) // block_length) % 2, -1, 1)
        result = s.evaluate(scan(source, features(rotation=rotation)), 0)["proposal"]
        rows.append({"block_length": block_length, "amplitude_radians": amplitude, "sign": sign,
                     "ground_truth_time_warp": 0, "lambda": 0, "K": result["K"],
                     "qualified_K": result["qualified_K"],
                     "selected": [{k: r[k] for k in ("part", "start", "end", "lag", "status", "reasons")} for r in result["selected"]]})
    return {"scope": "synthetic zero-scale limitation test, not real source calibration",
            "cases": rows, "cases_with_qualified_phase": sum(r["qualified_K"] > 0 for r in rows),
            "interpretation": "Any qualified phase is a descriptor confound with zero time warp; retain as an algorithm limitation."}


if __name__ == "__main__":
    if "--stress" in sys.argv:
        print(json.dumps(stress_report(), indent=2))
    else:
        unittest.main()
