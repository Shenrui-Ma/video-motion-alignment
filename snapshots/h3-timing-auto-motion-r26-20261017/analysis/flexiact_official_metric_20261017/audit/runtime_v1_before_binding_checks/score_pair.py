"""Score two archived tracker results on the same original 49 timestamps."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_tracks(folder, torch):
    report = json.loads((folder / "REPORT.json").read_text())
    if report["passed"] is not True or sha(folder / "tracks.pt") != report["tracks_sha256"]:
        raise ValueError("Tracker result is incomplete or changed")
    times = [float(frame["best_effort_timestamp_time"]) for frame in report["timebase"]["frames"]]
    if len(times) != 49 or any(abs(t - i / 8) > 1e-6 for i, t in enumerate(times)):
        raise ValueError("Tracker result has a different physical timebase")
    return torch.load(folder / "tracks.pt", map_location="cpu", weights_only=True)["tracks"], report


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
