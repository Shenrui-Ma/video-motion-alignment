"""Score two archived tracker results on the same original 49 timestamps."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent
CHECKPOINT_SHA = "dbb9006c0dc89479c34993ac23d37ae0af13deac18be6028009d7483754b2fc3"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_tracks(folder, torch):
    report = json.loads((folder / "REPORT.json").read_text())
    if report["passed"] is not True or sha(folder / "tracks.pt") != report["tracks_sha256"]:
        raise ValueError("Tracker result is incomplete or changed")
    times = [float(frame["best_effort_timestamp_time"]) for frame in report["timebase"]["frames"]]
    if len(times) != 49 or any(not math.isfinite(t) or abs(t - i / 8) > 1e-6 for i, t in enumerate(times)):
        raise ValueError("Tracker result has a different physical timebase")
    expected = {"checkpoint_sha256": CHECKPOINT_SHA,
                "metric_functions_sha256": sha(ROOT / "METRIC_FUNCTIONS.json"),
                "vendor_manifest_sha256": sha(ROOT / "VENDOR.json"),
                "grid_size": 55, "mask": None, "tracks_dtype": "torch.float32"}
    for field, value in expected.items():
        if report[field] != value:
            raise ValueError("Tracker result differs from pinned setup: " + field)
    tracks = torch.load(folder / "tracks.pt", map_location="cpu", weights_only=True)["tracks"]
    if list(tracks.shape) != [3025, 49, 2] or tracks.dtype != torch.float32:
        raise ValueError("Tracker tensor has unexpected shape or dtype")
    if report["case"]["role"] == "generated":
        from run_tracks import validate_generated_binding
        item = report["case"]
        video = ROOT / item["file"]
        if sha(video) != item["sha256"] or validate_generated_binding(item, video) != report["generation_binding_checked"]:
            raise ValueError("Generated input release provenance differs")
    elif report["case"]["role"] == "reference":
        manifest = ROOT / "SOURCE_INPUTS.json"
        matches = [row for row in json.loads(manifest.read_text())["inputs"] if row["id"] == report["case"]["id"]]
        if (len(matches) != 1 or report["case"] != matches[0] or
                report["manifest_sha256"] != sha(manifest) or
                sha(ROOT / matches[0]["file"]) != matches[0]["sha256"]):
            raise ValueError("Reference cache differs from the fixed official source")
    else:
        raise ValueError("Unknown tracker input role")
    return tracks, report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", required=True)
    parser.add_argument("--edited", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    import torch
    torch.set_num_threads(2)
    from metric_adapter import score_tracks
    reference_path, edited_path = Path(args.reference), Path(args.edited)
    reference, ref_report = read_tracks(reference_path, torch)
    edited, edit_report = read_tracks(edited_path, torch)
    if ref_report["case"]["role"] != "reference" or edit_report["case"]["role"] != "generated":
        raise ValueError("The metric is directional: edited rows must compare to reference columns")
    if ref_report["case"]["id"] != edit_report["case"]["id"]:
        raise ValueError("Reference and edit have different official pair IDs")
    for field in ("checkpoint_sha256", "metric_functions_sha256", "vendor_manifest_sha256", "grid_size", "mask", "tracks_dtype"):
        if ref_report[field] != edit_report[field]:
            raise ValueError("Tracker setup differs: " + field)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    record, matrix = score_tracks(edited, reference)
    record.update({"pair_id": ref_report["case"]["id"],
                   "reference_report_sha256": sha(reference_path / "REPORT.json"),
                   "edit_report_sha256": sha(edited_path / "REPORT.json"),
                   "timebase": "49 frames, original j/8 seconds", "score_seconds": time.monotonic() - start,
                   "cuda_initialized": torch.cuda.is_initialized()})
    torch.save({"similarity_matrix": matrix}, output / "similarity.pt")
    record["similarity_sha256"] = sha(output / "similarity.pt")
    (output / "SCORE.json").write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
    print(json.dumps(record, allow_nan=False))


if __name__ == "__main__":
    main()
