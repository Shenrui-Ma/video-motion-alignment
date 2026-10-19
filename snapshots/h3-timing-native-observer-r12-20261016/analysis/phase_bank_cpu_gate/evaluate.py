"""Frozen, CPU-only coarse candidate-bank falsification; never calls a model."""
import ast
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
PROTOCOL_SHA = "fe223f2a864ccf9662b811924913c5b382c8fa21631aa5f55435417d02854fc1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    started = time.monotonic()
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    assert sha(HERE / "PROTOCOL.json") == PROTOCOL_SHA
    p = json.loads((HERE / "PROTOCOL.json").read_text())
    approval = json.loads((HERE / "REVIEW_ACK.json").read_text())
    assert approval["protocol_sha256"] == PROTOCOL_SHA and approval["approved"] is True
    with Path(p["cpu_lock"]).open("a") as lock:
        # Do not block other researchers invisibly: caller may retry this same job.
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        import numpy as np
        import torch
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        assert not torch.cuda.is_initialized()
        rng_before = torch.get_rng_state().clone()
        frozen = p["signal_source"]
        assert sha(frozen["path"]) == frozen["sha256"]
        tree = ast.parse(Path(frozen["path"]).read_text())
        selected = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name in frozen["functions"]]
        assert {n.name for n in selected} == set(frozen["functions"])
        ns = {"np": np}
        exec(compile(ast.Module(body=selected, type_ignores=[]), frozen["path"], "exec"), ns)
        geometry, signal, interp, scan = [ns[n] for n in frozen["functions"]]

        def tensor_signature(z):
            return {"shape": list(z.shape), "dtype": str(z.dtype),
                    "sha256": hashlib.sha256(z.contiguous().view(torch.uint8).numpy()).hexdigest()}

        checked_files = {}
        checked_tensors = {}

        def load_tensor(name, item, target=False):
            path = item["local_tensor"] if target else item["path"]
            expected = item["video"] if target else item["tensor"]
            assert sha(path) == item["file_sha256"], name + " file hash"
            checked_files[path] = item["file_sha256"]
            blob = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
            z = blob["video"] if target else blob
            actual = tensor_signature(z)
            assert actual == {k: expected[k] for k in actual}, name + " tensor hash"
            assert tuple(z.shape) == (1, 24, 42, 46, 82)
            assert z.dtype == torch.float32 and bool(torch.isfinite(z).all())
            if target:
                meta = blob["metadata"]
                assert meta["snapshot_kind"] == "sampler_final" and meta["run_id"] == name
                assert meta["sigma_video"] == 0 and meta["video_latent_scale_factor"] == 1
                assert meta["normalization_stage"] == "after_process_latent_out"
                assert sha(item["capture_manifest"]) == item["capture_manifest_sha256"]
                assert sha(item["conditioning_path"]) == item["conditioning_sha256"]
                condition = json.loads(Path(item["conditioning_path"]).read_text())
                refs = [r for r in condition["pair_snapshot"]["actual"]["references"]
                        if r["kind"] == "video"]
                assert len(refs) == 1 and refs[0]["clean_latent"] == item["actual_clean_reference"]
                assert refs[0]["clean_latent"]["sha256"] == p["bank"]["original"]["tensor"]["sha256"]
                assert condition["native_vae_calls"][1]["prepared_frames"] == item["prepared_frames"]
            checked_tensors[name] = actual
            return z[0].permute(1, 0, 2, 3).reshape(42, -1).numpy().astype(np.float64)

        times = signal(np.zeros((42, 1), np.float64), "same_phase_gap5")[0]
        queries = np.arange(50, 66, dtype=np.float64)

        def support(q):
            hi = np.searchsorted(times, q, side="right").clip(1, len(times) - 1)
            lo = hi - 1
            w = ((q - times[lo]) / (times[hi] - times[lo])).clip(0, 1)
            rows = []
            for t, low, high, weight in zip(q, lo, hi, w):
                indices = ([int(low)] if weight < 1 else []) + ([int(high)] if weight > 0 else [])
                bins = sorted(set(indices + [i + 5 for i in indices]))
                chunks = sorted(set(i // 5 for i in bins))
                clamp = bool(t < times[0] or t > times[-1])
                valid = not clamp and all(5 <= b < 40 for b in bins)
                rows.append({"query_frame": float(t), "gap5_indices": indices,
                             "latent_bins": bins, "encoding_chunks": chunks,
                             "chunk_rgb_intervals": [[17*c, 17*c+16] for c in chunks],
                             "weight_upper": float(weight), "clamped": clamp, "valid": valid})
            return rows

        common_support = support(queries)
        assert all(r["valid"] for r in common_support)

        def rank_scores(rows):
            reasons = []
            if not all(row["support_valid"] for row in rows):
                reasons.append("UNKNOWN_SUPPORT")
            if not all(row["coverage"] == 1.0 for row in rows):
                reasons.append("UNKNOWN_LOW_SIGNAL")
            ranked = sorted((r for r in rows if r["score"] is not None),
                            key=lambda r: (r["score"], r["candidate_frames"]))
            margin = ranked[1]["score"] - ranked[0]["score"] if len(ranked) >= 2 else None
            if margin is None or margin <= p["top2_margin_min"]:
                reasons.append("UNKNOWN_AMBIGUOUS")
            winner = ranked[0]["candidate_frames"] if ranked else None
            if reasons:
                decision = "UNKNOWN"
            elif winner == 0:
                decision = p["rejection_rules"]["winner0"]
            elif winner == 8:
                decision = p["rejection_rules"]["winner8"]
            else:
                decision = p["rejection_rules"]["winner4"]
            return {"ranking": [r["candidate_frames"] for r in ranked], "winner": winner,
                    "all_candidate_top2_margin": margin, "decision": decision,
                    "rejection_reasons": reasons, "safe_stop": False,
                    "precise_lag_estimate": None}

        bank_arrays = {name: load_tensor(name, item) for name, item in p["bank"].items()}
        signals = {name: signal(z, "same_phase_gap5") for name, z in bank_arrays.items()}
        bank_values = {d: interp(*signals[name], queries)
                       for d, name in [(0, "original"), (4, "delay4"), (8, "delay8")]}

        def rank_query(query_signal):
            y = interp(*query_signal, queries)
            yn = np.linalg.norm(y, axis=1)
            yr = yn / np.sqrt(y.shape[1])
            rows = []
            for d, b in bank_values.items():
                bn = np.linalg.norm(b, axis=1)
                br = bn / np.sqrt(b.shape[1])
                valid = (yr > p["min_per_frame_rms"]) & (br > p["min_per_frame_rms"])
                errors = [None] * len(queries)
                for i in np.flatnonzero(valid):
                    errors[int(i)] = float(1 - np.dot(b[i], y[i]) / (bn[i] * yn[i]))
                score = float(np.mean([v for v in errors if v is not None])) if valid.any() else None
                rows.append({"candidate_frames": d, "score": score,
                             "coverage": float(valid.mean()), "valid_frames": int(valid.sum()),
                             "support_valid": all(r["valid"] for r in common_support),
                             "per_frame_signed_cosine_error": errors,
                             "bank_per_frame_rms": br.tolist(), "target_per_frame_rms": yr.tolist()})
            return {"candidate_scores": rows, **rank_scores(rows)}

        checks = {}
        for name, expected in [("original", 0), ("delay4", 4), ("delay8", 8)]:
            ranking = rank_query(signals[name])
            baseline = scan(signals["original"], signals[name], [50, 65], p["baseline"]["limits"])
            assert ranking["winner"] == expected, "self lookup index/sign failed"
            assert baseline["accepted"] and baseline["best"]["lag_frames"] == expected
            checks[name] = {"bank": ranking, "gap5_scan": baseline,
                            "interpretation": "same tensor self-match only; not cross-identity accuracy"}
        constant = rank_query(signals["constant0"])
        assert constant["decision"] == "UNKNOWN" and "UNKNOWN_LOW_SIGNAL" in constant["rejection_reasons"]
        checks["constant0"] = constant
        tie = rank_scores([{"candidate_frames": d, "score": 0.25, "coverage": 1.0,
                            "support_valid": True} for d in [0, 4, 8]])
        assert tie["decision"] == "UNKNOWN" and "UNKNOWN_AMBIGUOUS" in tie["rejection_reasons"]
        checks["synthetic_equal_cost"] = tie
        boundaries = support(np.array([0., 8.5, 130., 140.]))
        assert not any(r["valid"] for r in boundaries)
        checks["excluded_boundary_queries"] = boundaries
        # Boundary classifier must never turn truncation into a point estimate.
        for winner in [0, 4, 8]:
            test = rank_scores([{"candidate_frames": d, "score": 0.0 if d == winner else 0.5,
                                 "coverage": 1.0, "support_valid": True} for d in [0, 4, 8]])
            assert test["decision"] == p["rejection_rules"][f"winner{winner}"]
            assert test["precise_lag_estimate"] is None and not test["safe_stop"]

        target_results = []
        for item in p["targets"]:
            timer = time.monotonic()
            z = load_tensor(item["run_id"], item, target=True)
            target_signal = signal(z, "same_phase_gap5")
            ranking = rank_query(target_signal)
            baseline = scan(signals["original"], target_signal, [50, 65], p["baseline"]["limits"])
            lag = item["independent_pose_lag_frames"]
            misleading_zero = lag > 8 and ranking["winner"] == 0 and ranking["decision"] != "UNKNOWN"
            false_interior = lag > 8 and ranking["winner"] == 4 and ranking["decision"] != "UNKNOWN"
            target_results.append({"run_id": item["run_id"], "independent_pose_lag_frames": lag,
                                   "bank": ranking, "gap5_scan": baseline,
                                   "out_of_range_false_interior_accept": false_interior,
                                   "out_of_range_misleading_zero_rank": misleading_zero,
                                   "read_seconds_including_hash_load": time.monotonic() - timer})
            print(item["run_id"], ranking["ranking"], ranking["decision"],
                  [r["score"] for r in ranking["candidate_scores"]],
                  "gap5", baseline["best"]["lag_frames"] if baseline["best"] else None, flush=True)

        assert torch.equal(rng_before, torch.get_rng_state())
        assert not torch.cuda.is_initialized()
        assert all(sha(path) == expected for path, expected in checked_files.items())
        result = {"protocol_sha256": PROTOCOL_SHA, "script_sha256": sha(__file__),
                  "review": approval, "CPU_only": True, "CUDA_initialized": False,
                  "torch_threads": torch.get_num_threads(), "RNG_unchanged": True,
                  "input_files_rehashed_unchanged": True, "verified_tensors": checked_tensors,
                  "common_support": common_support, "tests": checks,
                  "targets": target_results, "elapsed_seconds": time.monotonic() - started,
                  "necessary_failures": [r["run_id"] for r in target_results if
                      r["out_of_range_false_interior_accept"] or r["out_of_range_misleading_zero_rank"]],
                  "interpretation": "Coarse necessary rejection test only. No exact 0/2/4, unknown-origin, safe-stop, early-x0 or generalization claim."}
        with (HERE / "RESULTS.json").open("x") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write("\n")
        print("DONE", result["elapsed_seconds"], "seconds", flush=True)


if __name__ == "__main__":
    main()
