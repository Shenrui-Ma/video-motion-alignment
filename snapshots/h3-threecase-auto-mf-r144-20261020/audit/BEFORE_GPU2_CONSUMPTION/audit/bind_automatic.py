"""Bind real R144 output through its existing ONLINE_RUNTIME_GATE and exit receipt."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import bound, read, save, sha


def check_gate(gate, release, name, geometry):
    assert gate["schema"] == "r86-online-runtime-gate-v1" and gate["passed"] is True
    assert gate["status"] == "pass" and gate["cleanup_verified"] is True
    assert gate["partial_batch"] is False and gate["existing_case_Native_reused"] is True
    assert gate["valid_frames"] == geometry["valid_frames"]
    cases = gate["cases"]
    assert len(cases) == 1
    assert cases[0]["run"] == f"r144_{name}_seed2026101701_visible_only"
    assert cases[0]["arm"] == "visible_only" and cases[0]["updates"] == 20
    info = gate["video"]["properties"]
    assert [info[k] for k in ("width", "height", "avg_frame_rate", "nb_read_frames")] == [
        geometry["width"], geometry["height"], "24/1", str(geometry["sampled_frames"])]
    assert release["passed"] is True and release["service"] == gate["service_record"]
    assert release["service_cleanup"]["process_absent"] is True
    assert release["service_cleanup"]["own_compute_absent"] is True
    assert release["observer_children"]["all_exact_generations_absent"] is True
    assert release["observer_children"]["all_registered_CUDA_pids_absent"] is True
    producer = Path("/data4/researcher/h3_runs/threecase_auto_r144_20261020/cases") / name
    assert Path(gate["video"]["file"]).is_relative_to(producer / "output")
    assert ".." not in Path(gate["video"]["file"]).parts
    return gate["video"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True, choices=("short_0358", "long_0039", "long_0059"))
    p.add_argument("--gate", type=Path, required=True)
    p.add_argument("--release", type=Path, required=True)
    p.add_argument("--video", type=Path, required=True, help="Locally collected raw full output MP4")
    p.add_argument("--inventory-id", required=True, help="Root-selected new automatic row ID")
    a = p.parse_args()
    assert not (ROOT / "SEAL.json").exists(), "Preserve finalized package"
    case = ROOT / "cases" / a.case
    manifest = read(case / "INPUTS.json")
    assert manifest["targets"] == [], "Do not overwrite an existing automatic binding"
    proof = next(x for x in read(ROOT / "audit/SOURCE_CACHE_VERIFIED.json")["cases"] if x["case"] == a.case)
    geometry = proof["geometry"]
    gate, release = read(a.gate), read(a.release)
    video = check_gate(gate, release, a.case, geometry)
    assert sha(a.video) == video["sha256"], "Raw automatic video SHA differs from final gate"
    assert a.inventory_id != proof["inventory_id"], "Do not overwrite the historical fixed row"
    sys.path.insert(0, str(ROOT / "runtime/ive/metric_runtime"))
    from ive_mf_adapter import frame_hashes, media_info, validate_time_view

    info = media_info(a.video, "/opt/homebrew/bin/ffprobe")
    assert [info[k] for k in ("width", "height", "count")] == [
        geometry["width"], geometry["height"], geometry["sampled_frames"]]
    assert all(abs(v - i / 24) < 1e-6 for i, v in enumerate(info["pts_s"]))
    target = case / "automatic"
    target.mkdir(exist_ok=False)
    # Isolated copies avoid exposing producer media to later accidental changes.
    shutil.copyfile(a.video, target / "full.mp4")
    n = geometry["valid_frames"]
    crop = f"crop=1280:720:16:8,trim=end_frame={n},setsar=1"
    subprocess.run([
        "/opt/homebrew/bin/ffmpeg", "-v", "error", "-threads", "2", "-i", str(a.video),
        "-an", "-vf", crop, "-vsync", "0", "-c:v", "libx264", "-qp", "0",
        "-preset", "fast", "-pix_fmt", "yuv420p", "-threads", "2", str(target / "score.mp4")
    ], check=True)
    pixels = frame_hashes(target / "score.mp4", "/opt/homebrew/bin/ffmpeg")
    assert pixels == frame_hashes(a.video, "/opt/homebrew/bin/ffmpeg", crop)
    validate_time_view(media_info(target / "score.mp4", "/opt/homebrew/bin/ffprobe"), n)
    gate_copy = ROOT / "configs/evidence" / (a.case + "_ONLINE_RUNTIME_GATE.json")
    release_copy = ROOT / "configs/evidence" / (a.case + "_ROOT_EXIT_RECEIPT.json")
    shutil.copyfile(a.gate, gate_copy)
    shutil.copyfile(a.release, release_copy)
    manifest["targets"] = [{
        "role": "automatic", "full_file": "automatic/full.mp4", "full_sha256": video["sha256"],
        "score_file": "automatic/score.mp4", "score_sha256": sha(target / "score.mp4"),
        "score_frame_md5": pixels, "evaluation_indices": list(range(n)),
        "inventory_bindings": [{"id": a.inventory_id, "field": "guided"}],
        "actual_runtime_gate": bound(gate_copy), "actual_producer_release": bound(release_copy),
        "actual_run_id": proof["run_id"], "preprocessing": crop,
        "raw_video_required": True, "display_overlay_evaluated": False}]
    save(case / "INPUTS.json", manifest)
    assert "torch" not in sys.modules
    print({"case": a.case, "role": "automatic", "frames": n, "raw_video_sha256": video["sha256"],
               "source_cache_reused": True, "GPU_started": False})


if __name__ == "__main__":
    main()
