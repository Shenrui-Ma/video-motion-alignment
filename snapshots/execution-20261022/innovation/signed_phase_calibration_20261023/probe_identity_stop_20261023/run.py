"""Strict identity-preserving reference-only CPU entry; no alpha or GPU."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import zipfile

import numpy as np
import core

HERE = Path(__file__).resolve().parent
ALLOWED_KEYS = frozenset(("qrn_kn", "qrw_kw", "valid_bins", "physical_frame_spans_inclusive", "spatial_ids"))


class Pending(Exception):
    pass


class Invalid(ValueError):
    pass


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def require(condition, message):
    if not condition:
        raise Invalid(message)


def locked_policy():
    ready = read(HERE / "READY.json")
    for path, digest in ready["files_sha256"].items():
        require(sha(HERE / path) == digest, "frozen source changed: " + path)
    return read(HERE / "POLICY.json")


def path_inputs(manifest):
    manifest = Path(manifest)
    if not manifest.is_file():
        raise Pending("input manifest absent")
    doc = read(manifest)
    require(set(doc) == {"schema", "upstream_status", "steps"}, "unknown/missing top-level input fields")
    require(doc["schema"] == "h3-probe-identity-stop-input-v1", "input schema differs")
    keys = set(doc["steps"])
    require(not keys - {"9", "19"}, "unknown step")
    if keys != {"9", "19"}:
        raise Pending("both steps9/19 required")
    paths = {"status": doc["upstream_status"], **doc["steps"]}
    for key, value in paths.items():
        require(isinstance(value, str) and bool(value), "invalid input path: " + key)
        p = Path(value)
        p = p if p.is_absolute() else manifest.parent / p
        if not p.is_file():
            raise Pending("missing input: " + key)
        paths[key] = p
    return paths


def decode_reference(path):
    """Never access generated-query members, even if they are present/corrupt."""
    decoded = {}
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        require(len(names) == len(set(names)), "duplicate ZIP member")
    with np.load(path, allow_pickle=False) as archive:
        for key in sorted(ALLOWED_KEYS):
            require(key in archive.files, "required reference/metadata member absent: " + key)
            decoded[key] = archive[key]
    return decoded


def validate_arrays(arrays, policy):
    for name in ("valid_bins", "physical_frame_spans_inclusive", "spatial_ids"):
        require(np.array_equal(arrays[name], np.asarray(policy[name])), "fixed geometry differs: " + name)
    require(arrays["valid_bins"].dtype == np.bool_, "valid mask must be boolean")
    # Upstream serializes exact integer-valued spans as float64; values above
    # must still match every frozen policy entry, without rounding or casting.
    require(arrays["physical_frame_spans_inclusive"].dtype.kind in "iuf", "spans must be real numeric")
    require(np.issubdtype(arrays["spatial_ids"].dtype, np.integer), "spatial ids must be integral")
    valid = arrays["valid_bins"]
    for branch in policy["reference_branches"]:
        p = arrays[branch]
        require(list(p.shape) == policy["shape"] and p.dtype == np.float64, "fixed probability geometry/dtype differs")
        require(np.isfinite(p).all() and np.all(p >= 0), "probabilities must be finite nonnegative")
        require(np.allclose(p[:, valid].sum(-1), 1, atol=1e-12, rtol=0), "reference probabilities not normalized")
        require(not np.any(p[:, ~valid]) and not np.any(p[..., ~valid]), "padding contains probability")


def preflight(paths, policy):
    status = read(paths["status"])
    if status.get("status") in ("pending", "running"):
        raise Pending("upstream analysis not complete")
    require(status.get("status") == "complete" and status.get("results_written") is True, "upstream failed")
    require(sha(paths["status"]) == policy["upstream"]["status_sha256"], "upstream completion identity differs")
    require(status.get("summary_sha256") == policy["upstream"]["summary_sha256"], "upstream summary identity differs")
    all_arrays = {}
    for step in policy["steps"]:
        path = paths[str(step)]
        require(sha(path) == policy["upstream"]["npz_sha256"][str(step)], "NPZ identity differs: " + str(step))
        arrays = decode_reference(path)
        validate_arrays(arrays, policy)
        all_arrays[step] = arrays
    return all_arrays


def execute(inputs, output, policy):
    """Policy argument supports synthetic fixtures; CLI always loads locked policy."""
    out = Path(output)
    if out.exists():
        raise FileExistsError(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    try:
        require(set(policy["decoded_npz_keys"]) == ALLOWED_KEYS, "decode whitelist differs")
        paths = path_inputs(inputs)
        arrays = preflight(paths, policy)
        summaries = []
        with tempfile.TemporaryDirectory(prefix=".probe-identity-", dir=out.parent) as tmp:
            tmp = Path(tmp)
            for step in policy["steps"]:
                values = arrays[step]
                for direction in policy["primary_directions"]:
                    dictionary, query = direction["dictionary"], direction["query"]
                    result = core.analyze(values[dictionary], values[query], values["valid_bins"],
                                          values["physical_frame_spans_inclusive"])
                    result.update(input_valid_bins=values["valid_bins"],
                                  input_physical_frame_spans_inclusive=values["physical_frame_spans_inclusive"],
                                  input_spatial_ids=values["spatial_ids"])
                    filename = f"step{step:03d}_{dictionary}_to_{query}.npz"
                    np.savez_compressed(tmp / filename, **result)
                    summaries.append({"step_zero_based": step, "dictionary_branch": dictionary,
                                      "query_branch": query, "array_file": filename,
                                      "array_sha256": sha(tmp / filename), **core.summarize(result)})
            tested = sum(x["tested_correlated_bins"] for x in summaries)
            require(tested == policy["planned_correlated_bins"], "planned correlated-bin denominator differs")
            passed = all(x["all_unique_correct"] for x in summaries)
            summary = {"schema": "h3-probe-identity-stop-summary-v1", "status": "complete",
                       "case": policy["case"], "layer_zero_based": policy["layer_zero_based"],
                       "diagnostics": summaries, "decoded_npz_keys": sorted(ALLOWED_KEYS),
                       "input_sha256": {k: sha(v) for k, v in paths.items()},
                       "planned_correlated_bins": policy["planned_correlated_bins"],
                       "tested_correlated_bins": tested,
                       "planned_video_count": policy["planned_video_count"],
                       "all_heads_probes_times_directions_retained": True,
                       "all_unique_correct": passed,
                       "unique_correct_correlated_bins": sum(x["unique_correct_count"] for x in summaries),
                       "decision": "CONTINUE_TO_INDEPENDENT_CONTENT_CALIBRATION_ONLY" if passed else "STOP_FULL_SUPPORT_ZERO_SHIFT_OBSERVER",
                       "decision_scope": policy["stop_scope"],
                       "positional_code_counterexample": "Pure positional code can pass all tests; content-time validity remains unestablished.",
                       "sparse_or_abstaining_controllers_evaluated": False,
                       "policy_sha256": hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest(),
                       "policy_hash_representation": "canonical JSON sort_keys=True default separators",
                       "tie_tolerance": float(core.TIE_TOLERANCE),
                       "noise_robustness_validated": False,
                       "generated_domain_validated": False,
                       "controller_released": False,
                       "gpu_used": False, "model_calls": 0,
                       "cpu_wall_seconds": time.monotonic() - started}
            write(tmp / "summary.json", summary)
            write(tmp / "STATUS.json", {"status": "complete", "results_written": True,
                                        "summary_sha256": sha(tmp / "summary.json")})
            os.replace(tmp, out)
        return read(out / "STATUS.json")
    except (Pending, ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile) as error:
        out.mkdir(exist_ok=False)
        status = {"status": "pending" if isinstance(error, Pending) else "invalid",
                  "results_written": False, "reason": type(error).__name__ + ": " + str(error)}
        write(out / "STATUS.json", status)
        return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    result = execute(args.inputs, args.output, locked_policy())
    print(json.dumps(result))
    return 0 if result["status"] in ("complete", "pending") else 2


if __name__ == "__main__":
    raise SystemExit(main())
