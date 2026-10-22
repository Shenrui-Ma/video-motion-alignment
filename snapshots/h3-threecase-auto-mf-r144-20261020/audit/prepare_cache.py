"""CPU-only R144 cache binding, using the completed R141b MF lifecycle."""
import copy
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import bound, read, save, sha

PROJECTS = ROOT.parent
PRODUCER = PROJECTS / "h3-threecase-auto-r144-20261020"
INVENTORY = PROJECTS / "h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json"
BASE = PROJECTS / "h3-oxygen-generic-retention-mf-r141b-20261020"
COMMIT = "2dcf8900ee65197f43854c76f61c66a32bb8dbfc"
CHECKPOINT = "da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df"
TRACKER = {"grid_size": 10, "grid_query_frame": 0, "backward_tracking": False, "offline": True, "window_len": 60}
CASES = ("short_0358", "long_0039", "long_0059")


def attach(source, destination):
    source, destination = Path(source), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        os.link(source, destination)
    assert sha(source) == sha(destination), str(destination)


def source_report_valid(report, old):
    assert report["passed"] is True and report["method"] == "source"
    assert report["pair_id"] == old["canonical_id"]
    assert report["official_commit"] == COMMIT and report["checkpoint_sha256"] == CHECKPOINT
    assert report["tracker"] == TRACKER
    n = old["valid_frames"]
    assert report["effective_frame_count"] == old["evaluation_frames"] == n
    assert report["score_frame_indices"] == list(range(n))
    assert report["tracks_shape"] == [1, n, 100, 2]
    assert report["decoded_frame_md5"] == old["source_frame_md5"]
    assert report["source_prepared_sha256"] == old["source_full_sha256"]
    assert report["source_score_sha256"] == old["source_score_sha256"]
    assert report["selection_sha256"] == old["selection_sha256"]


def main():
    assert not (ROOT / "SEAL.json").exists(), "Final seal already exists"
    for path in (ROOT / "cases").glob("*/INPUTS.json"):
        assert not read(path)["targets"], "Preserve already bound automatic inputs"
    inventory = read(INVENTORY)
    rows = {x["id"]: x for x in inventory["items"]}
    reuse = {"runtime": "/data4/researcher/h3_runs/ive_reference_phase_mf_20261020/runtime"}
    evidence, comparisons = [], {}
    sys.path.insert(0, str(ROOT / "runtime/ive/metric_runtime"))
    from ive_mf_adapter import frame_hashes, media_info, validate_time_view

    for name in CASES:
        binding_path = PRODUCER / "input_audit" / (name + "_BINDING.json")
        binding = read(binding_path)
        old_ref = next(x["manifest"] for x in binding["remote41_cache_candidates"]
                       if x["role"] == "native")
        assert sha(old_ref["file"]) == old_ref["sha256"]
        old_path = Path(old_ref["file"])
        old = read(old_path)
        historical_root = old_path.parents[2]
        historical_remote = read(historical_root / "configs/RUNTIME.json")["remote_root"]
        item = rows[binding["inventory_id"]]
        mf = item["quantitative_metrics"]["motion_fidelity"]
        assert mf["status"] == "complete" and mf["protocol"] == "IVEBench official MF"
        assert mf["valid_frames"] == old["valid_frames"] == binding["geometry"]["valid_frames"]
        assert mf["evaluation_frames"] == old["evaluation_frames"]
        assert mf["evaluation_fps"] == old["evaluation_fps"] == 24
        assert old["crop_xywh"] == binding["geometry"]["crop_xywh"] == [16, 8, 1280, 720]
        assert sha(binding["paired_MF_inputs"]["file"]) == binding["paired_MF_inputs"]["sha256"]
        paired = read(binding["paired_MF_inputs"]["file"])
        assert paired["raw_videos"]["source"]["sha256"] == old["source_full_sha256"]
        assert paired["evaluation_indices"] == list(range(old["valid_frames"]))

        previous = {}
        source_report_ref = None
        for field, binding_role in (("native", "native"), ("guided", "forced")):
            target = next(x for x in old["targets"] if
                          {"id": binding["inventory_id"], "field": field} in x["inventory_bindings"])
            result_path = historical_root / "results" / name / (target["role"] + ".json")
            result = read(result_path)
            assert sha(result_path) == mf["source_sha256"][str(result_path)]
            assert result["motion_fidelity"] == mf[field]
            expected = next(x["sha256"] for x in binding["remote41_cache_candidates"]
                            if x["role"] == binding_role)
            assert result["actual_generated_video_sha256"] == target["full_sha256"] == expected
            assert result["source_full_sha256"] == old["source_full_sha256"]
            assert result["source_score_sha256"] == old["source_score_sha256"]
            if source_report_ref is not None:
                assert source_report_ref == result["source_report"]
            source_report_ref = result["source_report"]
            previous[field] = {"score": mf[field], "result": bound(result_path),
                                   "full_sha256": target["full_sha256"],
                                   "score_sha256": target["score_sha256"]}
            shutil.copyfile(result_path, ROOT / "configs/evidence" / (name + "_" + field + "_MF.json"))
        # The book cache was initially generated in that historical batch, so its
        # old source_cache field is null. The completed result identifies it.
        report_rel = Path(source_report_ref["file"]).relative_to(historical_remote)
        source_report = historical_root / report_rel
        assert sha(source_report) == source_report_ref["sha256"]
        report = read(source_report)
        source_report_valid(report, old)
        tracks = source_report.with_name("tracks.npz")
        assert sha(tracks) == report["tracks_sha256"]
        if old["source_cache"]:
            assert source_report_ref["sha256"] == old["source_cache"]["report_sha256"]
            assert report["tracks_sha256"] == old["source_cache"]["tracks_sha256"]

        case = ROOT / "cases" / name
        files = {"source_full.mp4": old_path.parent / "source_full.mp4",
                 "source_score.mp4": old_path.parent / "source_score.mp4",
                 "tracks/source/REPORT.json": source_report,
                 "tracks/source/tracks.npz": tracks}
        for rel, source in files.items():
            attach(source, case / rel)
            reuse[f"cases/{name}/{rel}"] = str(Path(historical_remote) / source.relative_to(historical_root))
        crop = f"crop=1280:720:16:8,trim=end_frame={old['valid_frames']},setsar=1"
        assert sha(case / "source_full.mp4") == old["source_full_sha256"]
        assert sha(case / "source_score.mp4") == old["source_score_sha256"]
        assert frame_hashes(case / "source_score.mp4", "/opt/homebrew/bin/ffmpeg") == old["source_frame_md5"]
        assert frame_hashes(case / "source_full.mp4", "/opt/homebrew/bin/ffmpeg", crop) == old["source_frame_md5"]
        validate_time_view(media_info(case / "source_score.mp4", "/opt/homebrew/bin/ffprobe"), old["valid_frames"])
        manifest = copy.deepcopy({k: old[k] for k in (
            "benchmark", "canonical_id", "valid_frames", "evaluation_frames", "evaluation_fps",
            "source_full_sha256", "source_score_sha256", "source_frame_md5", "selection_sha256", "crop_xywh")})
        manifest.update(schema="r144-automatic-official-mf-inputs-v1", targets=[],
                        source_cache={"report_sha256": sha(source_report), "tracks_sha256": sha(tracks)})
        save(case / "INPUTS.json", manifest)
        proof = {"case": name, "historical_input": bound(old_path), "R144_binding": bound(binding_path),
                     "inventory_id": binding["inventory_id"], "previous": previous,
                     "geometry": binding["geometry"], "source_report": bound(source_report),
                     "source_tracks": bound(tracks), "remote_source_report": source_report_ref,
                     "source_crop_pixels_and_PTS_verified": True, "new_source_tracker": False,
                     "run_id": f"r144_{name}_seed2026101701_visible_only"}
        evidence.append(proof)
        comparisons[name] = previous
        for tag, path in (("HISTORICAL_INPUTS", old_path), ("R144_BINDING", binding_path),
                          ("PAIRED_MF_INPUTS", Path(binding["paired_MF_inputs"]["file"]))):
            shutil.copyfile(path, ROOT / "configs/evidence" / f"{name}_{tag}.json")
        save(ROOT / "configs/evidence" / (name + "_INVENTORY.json"), item)
    save(ROOT / "audit/REMOTE_REUSE_PLAN.json", reuse)
    save(ROOT / "audit/SOURCE_CACHE_VERIFIED.json", {
        "passed": True, "inventory": bound(INVENTORY), "cases": evidence,
        "checkpoint_sha256": CHECKPOINT, "official_commit": COMMIT, "tracker": TRACKER,
        "new_source_trackers": 0, "new_baseline_trackers": 0, "GPU_started": False})
    save(ROOT / "configs/BASELINE_MF.json", comparisons)
    save(ROOT / "configs/PLAN.json", {
        "groups": list(CASES), "jobs": [{"case": x, "role": "automatic"} for x in CASES],
        "unique_targets": 3, "source_cache_count": 3, "expected_final_roles": ["automatic"],
        "status": "WAITING_ACTUAL_AUTOMATIC_VIDEO_GATE_AND_RELEASE"})
    print(json.dumps({"passed": True, "cached_sources": 3, "reused_baseline_scores": 6,
                          "planned_new_trackers": 3, "final_inputs_bound": False, "GPU_started": False}))


if __name__ == "__main__":
    main()
