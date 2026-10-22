#!/usr/bin/env python3
"""Bounded CPU comparison of archived float32 ZIP storages; never reads data.pkl.

Writes only analysis/numerical_drift_quantification.json and .txt under --root.
Use the existing bundled Python with NumPy. No torch, server or GPU operations.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import resource
import sys
import time
import zipfile

import numpy as np


BASELINE_RUN = "06_silverwolf_seed2_baseline"
PARENT_RUN = "06_silverwolf_seed2_emphasis3"
PARENT_ROOT = Path("/Users/researcher/DevProjects/h3-event-emphasis-silverwolf-20261014")
SUM_FIELDS = ("count", "sum_abs", "sum_squared", "sum_signed", "baseline_squared",
              "parent_squared", "exact_equal_count", "over_one_255_count")


def raw_blocks(root, record, block_elements):
    if record["dtype"] != "torch.float32":
        raise ValueError("only archived float32 tensors are supported")
    shape = record["shape"]
    if not shape or any(type(n) is not int or n < 1 for n in shape):
        raise ValueError("invalid tensor shape")
    relative = Path(record["tensor_file"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("unsafe tensor-file path")
    expected_bytes = math.prod(shape) * 4
    with zipfile.ZipFile(root / "audit" / relative) as archive:
        storages = [entry for entry in archive.infolist() if re.search(r"/data/\d+$", entry.filename)]
        if len(storages) != 1 or storages[0].file_size != expected_bytes:
            raise ValueError("expected exactly one full-size contiguous tensor storage")
        byteorders = [entry for entry in archive.infolist() if entry.filename.endswith("/byteorder")]
        if len(byteorders) != 1 or archive.read(byteorders[0]) != b"little":
            raise ValueError("expected explicit little-endian storage")
        digest = hashlib.sha256()
        with archive.open(storages[0]) as stream:
            remaining = expected_bytes
            while remaining:
                count = min(block_elements * 4, remaining)
                data = stream.read(count)
                if len(data) != count:
                    raise ValueError("truncated raw tensor storage")
                digest.update(data)
                remaining -= count
                yield np.frombuffer(data, dtype="<f4")
            if stream.read(1):
                raise ValueError("unexpected trailing tensor bytes")
        if digest.hexdigest() != record["sha256"]:
            raise ValueError("raw tensor SHA256 differs from conditioning audit: " + str(relative))


def block_statistics(baseline, parent):
    if not np.isfinite(baseline).all() or not np.isfinite(parent).all():
        raise ValueError("nonfinite values in archived tensor")
    difference = np.subtract(baseline, parent, dtype=np.float64)
    absolute = np.abs(difference)
    return {"count": int(difference.size), "sum_abs": float(absolute.sum()),
            "sum_squared": float(np.square(difference).sum()), "sum_signed": float(difference.sum()),
            "baseline_squared": float(np.square(baseline, dtype=np.float64).sum()),
            "parent_squared": float(np.square(parent, dtype=np.float64).sum()),
            "exact_equal_count": int(np.count_nonzero(difference == 0)),
            "over_one_255_count": int(np.count_nonzero(absolute > 1 / 255)),
            "max_absolute": float(absolute.max()), "baseline_min": float(baseline.min()),
            "baseline_max": float(baseline.max()), "parent_min": float(parent.min()),
            "parent_max": float(parent.max())}


def combine(total, part):
    if total is None:
        return dict(part)
    for key in SUM_FIELDS:
        total[key] += part[key]
    for key in ("max_absolute", "baseline_max", "parent_max"):
        total[key] = max(total[key], part[key])
    for key in ("baseline_min", "parent_min"):
        total[key] = min(total[key], part[key])
    return total


def metrics(stats, pixels=False):
    count = stats["count"]
    rms = math.sqrt(stats["sum_squared"] / count)
    parent_rms = math.sqrt(stats["parent_squared"] / count)
    result = {"elements": count, "mae": stats["sum_abs"] / count,
              "rms_error": rms, "max_absolute_error": stats["max_absolute"],
              "mean_signed_error_baseline_minus_parent": stats["sum_signed"] / count,
              "parent_rms": parent_rms, "baseline_rms": math.sqrt(stats["baseline_squared"] / count),
              "rms_error_relative_to_parent_rms": rms / parent_rms if parent_rms else None,
              "exact_equal_fraction": stats["exact_equal_count"] / count,
              "baseline_value_range": [stats["baseline_min"], stats["baseline_max"]],
              "parent_value_range": [stats["parent_min"], stats["parent_max"]]}
    if pixels:
        result.update(mae_8bit_equivalent=result["mae"] * 255,
                      rms_error_8bit_equivalent=rms * 255,
                      max_absolute_error_8bit_equivalent=stats["max_absolute"] * 255,
                      fraction_above_one_8bit_level=stats["over_one_255_count"] / count)
    return result


def adjacent_diagnostic(baseline, parent):
    rows, counts = [], Counter()
    for frame, current in enumerate(baseline):
        candidates = [(offset, float(np.abs(current.astype(np.float64) - parent[frame + offset]).mean()))
                      for offset in (0, -1, 1) if 0 <= frame + offset < len(parent)]
        best_offset, best_mae = min(candidates, key=lambda item: item[1])
        counts[str(best_offset)] += 1
        row = {"frame": frame, "best_neighbor_offset": best_offset,
               "same_index_downsampled_mae": candidates[0][1], "best_neighbor_downsampled_mae": best_mae}
        if 39 <= frame <= 44:
            row["candidate_mae_by_offset"] = {str(offset): value for offset, value in candidates}
        rows.append(row)
    return {"method": "RGB spatial point subsampling every 16 pixels; compare only parent t-1,t,t+1; ties prefer t",
            "best_offset_counts": dict(counts), "per_frame": rows,
            "limit": "A neighboring pose can match more closely without a timestamp shift. This bounded check does not establish global temporal alignment."}


def compare_pair(root, parent_root, baseline, parent, per_frame=False, pixels=False):
    if baseline["shape"] != parent["shape"]:
        raise ValueError("tensor shapes differ; same-index numerical comparison is not defined")
    shape = baseline["shape"]
    block_elements = math.prod(shape[1:]) if per_frame else 1024 * 1024
    total, event, frames, baseline_thumbs, parent_thumbs = None, None, [], [], []
    left = raw_blocks(root, baseline, block_elements)
    right = raw_blocks(parent_root, parent, block_elements)
    for index, (a, b) in enumerate(zip(left, right, strict=True)):
        part = block_statistics(a, b)
        total = combine(total, part)
        if per_frame:
            frames.append({"frame": index, **metrics(part, pixels=True)})
            if 39 <= index <= 44:
                event = combine(event, part)
            baseline_thumbs.append(a.reshape(shape[1:])[::16, ::16, :].copy())
            parent_thumbs.append(b.reshape(shape[1:])[::16, ::16, :].copy())
    result = {"shape": shape, "dtype": baseline["dtype"], "baseline_tensor": baseline,
              "parent_tensor": parent, "raw_storage_sha256_verified": True,
              "aggregate": metrics(total, pixels)}
    if per_frame:
        if len(frames) != shape[0]:
            raise ValueError("frame count disagrees with tensor shape")
        result.update(per_frame=frames, event_frames_39_to_44=metrics(event, pixels=True),
                      adjacent_frame_diagnostic=adjacent_diagnostic(baseline_thumbs, parent_thumbs))
    return result


def quantify(root, parent_root):
    started = time.perf_counter()
    current = json.loads((root / "audit" / (BASELINE_RUN + "_conditioning.json")).read_text())
    previous = json.loads((parent_root / "audit" / (PARENT_RUN + "_conditioning.json")).read_text())
    image, video = current["native_vae_calls"]
    parent_image, parent_video = previous["native_vae_calls"]
    if video["prepared_frames"]["shape"] != [141, 736, 1312, 3]:
        raise ValueError("unexpected prepared source-video geometry")
    result = {"created_utc": datetime.now(timezone.utc).isoformat(), "status": "pass",
              "baseline_run": BASELINE_RUN, "parent_run": PARENT_RUN,
              "difference_direction": "baseline .41 minus factor3 .9",
              "decoded_input_video": {"baseline_record": current["input_video"], "parent_record": previous["input_video"],
                  "hash_identical": current["input_video"]["sha256"] == previous["input_video"]["sha256"],
                  "quantification_available": False,
                  "limit": "The decoded input_video records have no tensor_file; only their hashes are available. Pixel metrics below quantify saved prepared frames."}}
    result["prepared_source_video"] = compare_pair(root, parent_root, video["prepared_frames"], parent_video["prepared_frames"], per_frame=True, pixels=True)
    result["prepared_reference_image"] = compare_pair(root, parent_root, image["prepared_frames"], parent_image["prepared_frames"], pixels=True)
    result["source_video_vae_latent"] = compare_pair(root, parent_root, video["latent"], parent_video["latent"])
    result["reference_image_vae_latent"] = compare_pair(root, parent_root, image["latent"], parent_image["latent"])
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result["execution"] = {"elapsed_seconds": time.perf_counter() - started,
                           "peak_resident_mib": peak / (1024 ** 2) if sys.platform == "darwin" else peak / 1024,
                           "numpy_version": np.__version__, "streaming": "one source frame at a time; other tensors use <=1048576 float32 elements per chunk"}
    result["limits"] = [
        "Raw ZIP data storages and byteorder entries only; data.pkl was not opened and no tensor object was deserialized.",
        "Same-index per-frame metrics do not prove global temporal alignment; adjacent matching is a bounded spatially downsampled diagnostic.",
        "8-bit equivalent means floating-point error multiplied by 255; it is not a comparison of independently re-encoded images.",
        "VAE relative RMS is error RMS divided by parent factor3 latent RMS; it is a numerical metric, not a semantic quality score.",
        "Different preprocessing and runtime environments remain confounded. These measurements do not isolate PyAV, PyTorch, CUDA, kernels, or a causal attention benefit."]
    return result


def text_report(result):
    if result["status"] != "pass":
        return "Numerical drift quantification failed: " + result["error"] + "\n"
    lines = ["SilverWolf cross-environment numerical drift (CPU, archived raw storages)",
             "Difference: baseline .41 minus factor3 .9. No causal efficacy claim.", ""]
    for label, value in (("Prepared source video, all 141 frames", result["prepared_source_video"]["aggregate"]),
                         ("Prepared source video, event frames 39–44", result["prepared_source_video"]["event_frames_39_to_44"]),
                         ("Prepared reference image", result["prepared_reference_image"]["aggregate"])):
        lines.append(f"{label}: MAE={value['mae']:.9g}, RMS={value['rms_error']:.9g}, max={value['max_absolute_error']:.9g} (0–1 units).")
        lines.append(f"  8-bit equivalent: MAE={value['mae_8bit_equivalent']:.6g}, RMS={value['rms_error_8bit_equivalent']:.6g}, max={value['max_absolute_error_8bit_equivalent']:.6g}; >1 level={value['fraction_above_one_8bit_level']:.6%}.")
    for key in ("source_video_vae_latent", "reference_image_vae_latent"):
        value = result[key]["aggregate"]
        lines.append(f"{key}: error RMS={value['rms_error']:.9g}, parent RMS={value['parent_rms']:.9g}, relative RMS={value['rms_error_relative_to_parent_rms']:.6%}, max={value['max_absolute_error']:.9g}.")
    lines.extend(["", "Event frame detail (MAE / RMS / max, 8-bit equivalents):"])
    for row in result["prepared_source_video"]["per_frame"][39:45]:
        lines.append(f"  {row['frame']}: {row['mae_8bit_equivalent']:.6g} / {row['rms_error_8bit_equivalent']:.6g} / {row['max_absolute_error_8bit_equivalent']:.6g}")
    lines.extend(["", "Adjacent downsample best-offset counts: " + json.dumps(result["prepared_source_video"]["adjacent_frame_diagnostic"]["best_offset_counts"]),
                  "These neighbor results do not establish global temporal alignment.",
                  "Decoded input_video hashes differ; no saved decoded-input storage exists to quantify that stage directly.",
                  f"Peak resident memory: {result['execution']['peak_resident_mib']:.1f} MiB; elapsed: {result['execution']['elapsed_seconds']:.2f} s.",
                  "", *result["limits"]])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--parent-root", type=Path, default=PARENT_ROOT)
    args = parser.parse_args()
    try:
        result = quantify(args.root, args.parent_root)
    except Exception as error:
        result = {"status": "invalid", "error": type(error).__name__ + ": " + str(error)}
    directory = args.root / "analysis"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "numerical_drift_quantification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    report = text_report(result)
    (directory / "numerical_drift_quantification.txt").write_text(report)
    print(report)
    raise SystemExit(0 if result["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
