"""Existing-tensor CPU development ablation. No model inference or new encoding."""
import ast
import bisect
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import selectors
import shlex
import subprocess
import time

HERE = Path(__file__).resolve().parent
PROTOCOL_SHA = "2bfa8c1d53f7494b47e7265475aa7b5dfb188d4f3686d3c869cf4fd20e5132eb"
ARMS = ("real_reencoded", "latent_interpolated", "original_gap5_restricted")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    with (HERE / name).open("x") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")


@contextlib.contextmanager
def shared_locks(config):
    """Acquire Mac then remote, never wait while preventing a consumer's work."""
    with Path(config["local_lock"]).open("a") as local:
        fcntl.flock(local, fcntl.LOCK_EX | fcntl.LOCK_NB)
        code = ("import fcntl,json,os,sys; "
                "f=open(sys.argv[1],'a'); "
                "fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB); "
                "print(json.dumps({'locked':True,'pid':os.getpid()}),flush=True); "
                "sys.stdin.read()")
        command = shlex.join(["python3", "-c", code, config["remote_lock"]])
        proc = subprocess.Popen(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
             "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=2",
             config["remote_host"], command], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ)
                if not selector.select(15):
                    raise TimeoutError("remote CPU lock handshake; no tensors loaded")
            line = proc.stdout.readline()
            if not line:
                raise BlockingIOError("remote CPU lock unavailable: " + proc.stderr.read())
            identity = json.loads(line)
            assert identity["locked"]
            yield {"order": "Mac then remote", "local_pid": os.getpid(),
                   "remote_lock_holder": identity, "host": config["remote_host"],
                   "acquired_unix": time.time(), "threads": 1}
            assert proc.poll() is None, "remote CPU lock lost during evaluation"
        finally:
            if proc.stdin:
                proc.stdin.close()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.terminate()
                proc.wait(timeout=5)


def stencil(grid, query):
    high = max(1, min(len(grid) - 1, bisect.bisect_right(grid, query)))
    low = high - 1
    weight = min(1., max(0., (query - grid[low]) / (grid[high] - grid[low])))
    used = ([] if weight == 1 else [{"index": low, "weight": 1 - weight}])
    if weight > 0:
        used.append({"index": high, "weight": weight})
    return {"query": query, "stencil": used,
            "clamped": query < grid[0] or query > grid[-1]}


def support_record(source_u, delay, arm, centers, times):
    def bin_context(bins, shift):
        chunks = sorted(set(b // 5 for b in bins))
        rows = []
        for chunk in chunks:
            raw = list(range(17 * chunk, 17 * chunk + 17))
            shifted = [i - shift for i in raw]
            rows.append({"chunk": chunk, "input_interval": [raw[0], raw[-1]],
                         "source_interval_before_padding": [shifted[0], shifted[-1]],
                         "valid": 1 <= chunk <= 7 and min(shifted) >= 0 and max(shifted) <= 140})
        return rows

    def motion_trace(query, transform_delay=None, real_delay=0):
        motion = stencil(times, query)
        bins = sorted(set(i["index"] + offset for i in motion["stencil"] for offset in (0, 5)))
        interpolations = []
        original_bins = bins
        if transform_delay is not None:
            interpolations = [{"synthetic_latent_bin": b,
                               **stencil(centers, centers[b] - transform_delay)} for b in bins]
            original_bins = sorted(set(t["index"] for s in interpolations for t in s["stencil"]))
        contexts = bin_context(original_bins, real_delay)
        valid = (not motion["clamped"] and not any(s["clamped"] for s in interpolations)
                 and all(5 <= b < 40 for b in bins + original_bins)
                 and all(c["valid"] for c in contexts))
        return {"motion_interpolation": motion, "gap5_endpoint_bins": bins,
                "latent_interpolation": interpolations, "B0_dependency_bins": original_bins,
                "conservative_full_chunk_context": contexts, "valid": valid}

    target = motion_trace(source_u + delay)
    if arm == "real_reencoded":
        reference = motion_trace(source_u + delay, real_delay=delay)
    elif arm == "latent_interpolated":
        reference = motion_trace(source_u + delay, transform_delay=delay)
    else:
        assert arm == "original_gap5_restricted"
        reference = motion_trace(source_u)
    return {"source_u": source_u, "candidate_frames": delay, "arm": arm,
            "target": target, "reference": reference,
            "valid": target["valid"] and reference["valid"]}


def main():
    started = time.monotonic()
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == ""
    assert sha(HERE / "PROTOCOL.json") == PROTOCOL_SHA
    p = json.loads((HERE / "PROTOCOL.json").read_text())
    for key in ("review", "review_json", "old_protocol", "old_results", "control_encoding_execution"):
        assert sha(p[key]["path"]) == p[key]["sha256"], key
    with shared_locks(p["compute"]) as lock_record:
        import numpy as np
        import torch
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        assert not torch.cuda.is_initialized()
        rng_before = torch.get_rng_state().clone()
        np_rng_before = np.random.get_state()
        env_before = dict(os.environ)
        source = p["signal_source"]
        assert sha(source["path"]) == source["sha256"]
        tree = ast.parse(Path(source["path"]).read_text())
        functions = [x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name in source["functions"]]
        assert {x.name for x in functions} == set(source["functions"])
        ns = {"np": np}
        exec(compile(ast.Module(body=functions, type_ignores=[]), source["path"], "exec"), ns)
        geometry, signal, interp = (ns[x] for x in ("geometry", "signal", "interp"))
        centers = geometry(42).tolist()
        times = signal(np.zeros((42, 1)), "same_phase_gap5")[0].tolist()
        delays = p["candidates_frames"]
        proposed_u = list(range(50, 66))
        records = [support_record(u, d, a, centers, times)
                   for u in proposed_u for d in delays for a in ARMS]
        common_u = [u for u in proposed_u if all(s["valid"] for s in records if s["source_u"] == u)]
        support_valid = len(common_u) >= p["support"]["minimum_frames"] and len(common_u) == len(proposed_u)
        support = {"selection_before_target_load_or_score": True, "source_u": common_u,
                   "proposed_u": proposed_u, "frames": len(common_u), "sufficient": support_valid,
                   "records": records, "target_context_meaning": "nominal temporal support only; target is generated x0, not asserted to be reencoded RGB"}
        save("SUPPORT.json", support)
        assert support_valid, "UNKNOWN_SUPPORT: frozen common support insufficient; do not change windows"
        queries = np.asarray(common_u, dtype=np.float64)

        execution = json.loads(Path(p["control_encoding_execution"]["path"]).read_text())
        assert execution["status"] == "complete" and execution["geometry"] == [141, 736, 1312, 3]
        expected_ref = p["bank"]["original"]["tensor"]
        assert execution["inputs"]["cached_latent"]["sha256"] == expected_ref["sha256"]
        encode_arms = {a["arm"]: a for a in execution["arms"]}
        for name, d in (("original", 0), ("delay4", 4), ("delay8", 8)):
            assert encode_arms[name]["pixel_indices"] == [max(0, t - d) for t in range(141)]
            assert encode_arms[name]["latent"] == p["bank"][name]["tensor"]
        assert encode_arms["constant0"]["pixel_indices"] == [0] * 141
        checked_files, checked_tensors, condition_checks = {}, {}, {}

        def load(name, item, target=False):
            path = item["local_tensor"] if target else item["path"]
            assert sha(path) == item["file_sha256"], name + " file"
            checked_files[path] = item["file_sha256"]
            blob = torch.load(path, weights_only=True, map_location="cpu", mmap=True)
            z = blob["video"] if target else blob
            signature = {"shape": list(z.shape), "dtype": str(z.dtype),
                         "sha256": hashlib.sha256(z.contiguous().view(torch.uint8).numpy()).hexdigest()}
            expected = item["video"] if target else item["tensor"]
            assert signature == {k: expected[k] for k in signature}, name + " raw tensor"
            assert z.shape == (1, 24, 42, 46, 82) and z.dtype == torch.float32 and bool(torch.isfinite(z).all())
            if target:
                meta = blob["metadata"]
                assert meta["run_id"] == name and meta["snapshot_kind"] == "sampler_final"
                assert meta["normalization_stage"] == "after_process_latent_out"
                assert meta["sigma_video"] == 0 and meta["video_latent_scale_factor"] == 1
                assert sha(item["capture_manifest"]) == item["capture_manifest_sha256"]
                assert sha(item["conditioning_path"]) == item["conditioning_sha256"]
                cond = json.loads(Path(item["conditioning_path"]).read_text())
                refs = [v for v in cond["pair_snapshot"]["actual"]["references"] if v["kind"] == "video"]
                assert len(refs) == 1 and refs[0]["clean_latent"] == item["actual_clean_reference"] == expected_ref
                prepared = cond["native_vae_calls"][1]["prepared_frames"]
                assert prepared == item["prepared_frames"] == execution["inputs"]["prepared_RGB"]
                assert item["input_video"] == execution["inputs"]["input_video"]
                condition_checks[name] = {"prepared": prepared, "clean_reference": expected_ref,
                                          "actual_input_match": True, "normalization_scale": 1}
            checked_tensors[name] = signature
            return z[0].permute(1, 0, 2, 3).reshape(42, -1).numpy().astype(np.float64)

        bank = {n: load(n, b) for n, b in p["bank"].items()}
        signals = {n: signal(v, "same_phase_gap5") for n, v in bank.items()}
        # Frozen interp storage may clamp unused edge bins. SUPPORT proves no used dependency does.
        transformed = {d: interp(np.asarray(centers), bank["original"], np.asarray(centers) - d) for d in delays}
        assert np.array_equal(transformed[0], bank["original"])
        interpolated_signals = {d: signal(v, "same_phase_gap5") for d, v in transformed.items()}
        ref = {a: {} for a in ARMS}
        for d, name in ((0, "original"), (4, "delay4"), (8, "delay8")):
            ref["real_reencoded"][d] = interp(*signals[name], queries + d)
            ref["latent_interpolated"][d] = interp(*interpolated_signals[d], queries + d)
            ref["original_gap5_restricted"][d] = interp(*signals["original"], queries)
        assert all(np.array_equal(ref[a][0], ref[ARMS[0]][0]) for a in ARMS)

        def rank(rows):
            reasons = []
            if not all(r["support_valid"] for r in rows):
                reasons.append("UNKNOWN_SUPPORT")
            if not all(r["coverage"] == 1.0 for r in rows):
                reasons.append("UNKNOWN_LOW_SIGNAL")
            ranked = sorted([r for r in rows if r["score"] is not None], key=lambda r: (r["score"], r["candidate_frames"]))
            margin = ranked[1]["score"] - ranked[0]["score"] if len(ranked) > 1 else None
            if margin is None or margin <= p["top2_margin_min"]:
                reasons.append("UNKNOWN_AMBIGUOUS")
            winner = ranked[0]["candidate_frames"] if ranked else None
            decision = "UNKNOWN" if reasons else p["rank_rejections"]["winner" + str(winner)]
            return {"ranking": [r["candidate_frames"] for r in ranked], "winner": winner,
                    "all_candidate_top2_margin": margin, "decision": decision,
                    "rejection_reasons": reasons, "safe_stop": False, "precise_lag_estimate": None}

        def measure(target_signal):
            result = {}
            target_values = {d: interp(*target_signal, queries + d) for d in delays}
            for arm in ARMS:
                rows = []
                for d in delays:
                    b, y = ref[arm][d], target_values[d]
                    assert np.isfinite(b).all() and np.isfinite(y).all()
                    bn, yn = np.linalg.norm(b, axis=1), np.linalg.norm(y, axis=1)
                    br, yr = bn / np.sqrt(b.shape[1]), yn / np.sqrt(y.shape[1])
                    valid = (br > p["min_per_frame_rms"]) & (yr > p["min_per_frame_rms"])
                    errors = [None] * len(queries)
                    for i in np.flatnonzero(valid):
                        errors[int(i)] = float(1 - np.dot(b[i], y[i]) / (bn[i] * yn[i]))
                    rows.append({"candidate_frames": d, "source_u": common_u,
                                 "target_query_frames": (queries + d).tolist(),
                                 "score": float(np.mean([v for v in errors if v is not None])) if valid.any() else None,
                                 "coverage": float(valid.mean()), "valid_frames": int(valid.sum()),
                                 "support_valid": support_valid, "per_frame_signed_cosine_error": errors,
                                 "reference_per_frame_rms": br.tolist(), "target_per_frame_rms": yr.tolist()})
                result[arm] = {"candidate_scores": rows, **rank(rows)}
            assert all(result[a]["candidate_scores"][0] == result[ARMS[0]]["candidate_scores"][0] for a in ARMS)
            return result

        tests = {"real_shift_frame_maps": True, "d0_latent_exact": True, "d0_three_arms_exact": True}
        boundaries = [support_record(u, d, a, centers, times) for u in (0, 140) for d in delays for a in ARMS]
        assert all(not s["valid"] for s in boundaries)
        tests["excluded_boundary_stencils"] = boundaries
        tie = rank([{"candidate_frames": d, "score": .25, "coverage": 1., "support_valid": True} for d in delays])
        assert tie["decision"] == "UNKNOWN" and "UNKNOWN_AMBIGUOUS" in tie["rejection_reasons"]
        tests["equal_cost"] = tie
        controls = {n: measure(s) for n, s in signals.items()}
        for name, d in (("original", 0), ("delay4", 4), ("delay8", 8)):
            assert controls[name]["real_reencoded"]["winner"] == d
        assert all(x["decision"] == "UNKNOWN" and "UNKNOWN_LOW_SIGNAL" in x["rejection_reasons"] for x in controls["constant0"].values())
        tests["controls"] = controls
        targets = []
        old = json.loads(Path(p["old_results"]["path"]).read_text())
        old_by_id = {x["run_id"]: x for x in old["targets"]}
        for item in p["targets"]:
            t0 = time.monotonic()
            name = item["run_id"]
            result = measure(signal(load(name, item, target=True), "same_phase_gap5"))
            failures = {}
            for arm, value in result.items():
                reliable = value["decision"] != "UNKNOWN"
                nearzero_wrong = item["independent_pose_lag_frames"] == 0 and reliable and value["winner"] != 0
                far_false = item["independent_pose_lag_frames"] > 8 and reliable and value["winner"] in (0, 4)
                failures[arm] = {"nearzero_nonzero_rank": nearzero_wrong, "large_delay_false_interior_or_zero": far_false}
            targets.append({"run_id": name, "independent_pose_lag_frames": item["independent_pose_lag_frames"],
                            "arms": result, "necessary_failures": failures,
                            "prior_fixed_target_window": old_by_id[name],
                            "seconds_with_hash_load": time.monotonic() - t0})
            print(json.dumps({"run": name, "arms": {a: {"scores": [r["score"] for r in v["candidate_scores"]], "rank": v["ranking"], "decision": v["decision"]} for a, v in result.items()}}), flush=True)
        excluded = []
        for item in p["not_evaluated"]:
            assert sha(item["conditioning"]["path"]) == item["conditioning"]["sha256"]
            cond = json.loads(Path(item["conditioning"]["path"]).read_text())
            prepared = cond["native_vae_calls"][1]["prepared_frames"]
            actual_ref = [v["clean_latent"] for v in cond["pair_snapshot"]["actual"]["references"] if v["kind"] == "video"]
            assert prepared == item["actual_prepared_frames"] and actual_ref == [item["actual_clean_reference"]]
            assert prepared["sha256"] != execution["inputs"]["prepared_RGB"]["sha256"] and actual_ref[0] != expected_ref
            excluded.append(item)
        assert torch.equal(rng_before, torch.get_rng_state()) and not torch.cuda.is_initialized()
        nr = np.random.get_state()
        assert np_rng_before[0] == nr[0] and np.array_equal(np_rng_before[1], nr[1]) and np_rng_before[2:] == nr[2:]
        assert env_before == dict(os.environ)
        assert all(sha(path) == h for path, h in checked_files.items())
        save("RESULTS.json", {"protocol_sha256": PROTOCOL_SHA, "script_sha256": sha(__file__),
                             "support_sha256": sha(HERE / "SUPPORT.json"), "CPU_only": True,
                             "new_VAE_calls": 0, "new_DiT_calls": 0, "CUDA_initialized": False,
                             "threads": torch.get_num_threads(), "lock": lock_record,
                             "RNG_env_input_files_unchanged": True, "verified_tensors": checked_tensors,
                             "condition_checks": condition_checks, "tests": tests, "targets": targets,
                             "not_evaluated": excluded, "elapsed_seconds": time.monotonic() - started,
                             "interpretation": p["scope"]})
        print("DONE", time.monotonic() - started, "seconds", flush=True)


if __name__ == "__main__":
    main()
