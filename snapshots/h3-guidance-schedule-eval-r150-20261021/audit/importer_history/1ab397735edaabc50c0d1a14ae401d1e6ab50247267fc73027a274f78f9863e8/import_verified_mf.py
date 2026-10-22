"""Import collected official MF evidence into display records; no network/model work."""
import argparse
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, read, write, bound, require, verify_record
from finalize_batch import verify_batch_record

ARMS = ("early", "late", "split", "global_weak")


def import_case(sid):
    case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"] if c["source_id"] == sid)
    package = ROOT / "mf_preparation/host60_batches" / sid
    remote = Path(read(package / "configs/RUNTIME.json")["remote_root"])

    def remote_record(item):
        relative = Path(item["file"]).relative_to(remote)
        require(".." not in relative.parts, "Invalid remote evidence path")
        local = {"file": str(package / relative), "sha256": item["sha256"]}
        verify_record(local)
        return local

    verified_path = package / "audit/RESULTS_VERIFIED.json"
    verified = read(verified_path)
    require(verified["completed_targets"] == verified["requested_targets"] == 4
            and len(verified["results"]) == 4
            and {r["role"] for r in verified["results"]} == set(ARMS), "Four verified results required")
    final_path = package / "audit/FINAL_RELEASE_VERIFIED.json"
    final = read(final_path)
    require(all(final.get(k) is True for k in ("passed", "exact_processes_absent",
            "exact_CUDA_allocations_absent", "all_spawned_trackers_released", "peer_registrations_removed"))
            and len(final["tracker_identities"]) == final["completed_generated_scores"] == 4,
            "Exact target tracker release incomplete")
    seal = remote_record(final["seal"])
    complete_file = remote_record(final["final_complete"])
    complete = read(complete_file["file"])
    require(complete.get("passed") is True and complete.get("new_trackers") == 4
            and complete.get("remaining") == [] and complete.get("all_spawned_trackers_released") is True,
            "MF completion differs")
    result_receipts = {x["file"]: x["sha256"] for x in final["result_receipts"]}
    release_receipts = {x["file"]: x["sha256"] for x in final["child_release_receipts"]}
    inputs_path = package / "cases" / sid / "INPUTS.json"
    inputs = read(inputs_path)
    geometry = case["geometry"]
    require(inputs["valid_frames"] == inputs["evaluation_frames"] == geometry["valid_frames"]
            and inputs["evaluation_fps"] == geometry["fps"]
            and inputs["crop_xywh"] == geometry["crop_xywh"], "MF frame domain differs")
    require(bound(inputs_path)["sha256"] ==
            read(seal["file"])["files"][str(inputs_path.relative_to(package))], "Unsealed MF inputs")
    prepared = {}
    for arm in ARMS:
        v = next(r for r in verified["results"] if r["role"] == arm)
        result_file = {"file": v["result_file"], "sha256": v["result_sha256"]}
        release_file = {"file": v["release_file"], "sha256": v["release_sha256"]}
        verify_record(result_file)
        verify_record(release_file)
        result = read(result_file["file"])
        release = read(release_file["file"])
        relative = Path(result_file["file"]).relative_to(package)
        require(result_receipts.get(str(remote / relative)) == result_file["sha256"],
                "Final release does not bind this score")
        relative = Path(release_file["file"]).relative_to(package)
        require(release_receipts.get(str(remote / relative)) == release_file["sha256"]
                and release.get("passed") is True and release.get("returncode") == 0
                and release.get("process_absent") is True and release.get("CUDA_absent") is True,
                "Exact individual tracker release differs")
        presentation_path = ROOT / "review" / sid / arm / "PRESENTATION.json"
        proof = read(presentation_path)["validated_execution"]
        video = proof["video"]
        verify_record(video)
        verify_record(proof["gate"])
        verify_record(proof["binding"])
        require(read(proof["gate"]["file"]) == proof["run_record"], "Actual gate changed")
        batch = ROOT / "actual" / sid / "BATCH_RELEASE.json"
        verify_batch_record(batch, case, read(proof["binding"]["file"]), proof["run_record"])
        target = next(t for t in inputs["targets"] if t["role"] == arm)
        value = result.get("score", result.get("motion_fidelity"))
        require(isinstance(value, (int, float)) and math.isfinite(value) and value == v["score"]
                and result["case"] == v["case"] == sid and result["role"] == arm
                and result["actual_generated_video_sha256"] == v["actual_generated_video_sha256"] ==
                target["full_sha256"] == video["sha256"]
                and result["inventory_bindings"] == target["inventory_bindings"]
                and result["valid_frames"] == result["evaluation_frames"] == geometry["valid_frames"]
                and result["evaluation_fps"] == geometry["fps"]
                and result["source_cache_reused"] is True and result["official_numerics_unchanged"] is True,
                "Score is not the exact completed output/domain")
        require(remote_record(result["case_input"]) == bound(inputs_path), "Result used different inputs")
        require(result["source_full_sha256"] == case["media"]["source"]["sha256"]
                and result["source_score_sha256"] == inputs["source_score_sha256"], "Source media differs")
        score_video = package / "cases" / sid / target["score_file"]
        require(bound(score_video)["sha256"] == target["score_sha256"], "Score-view MP4 differs")
        reports = {}
        for role in ("source", "target"):
            report_file = remote_record(result[role + "_report"])
            report = read(report_file["file"])
            track = bound(Path(report_file["file"]).parent / "tracks.npz")
            require(report.get("passed") is True
                    and report["tracks_sha256"] == result[role + "_tracks_sha256"] == track["sha256"]
                    and report["effective_frame_count"] == geometry["valid_frames"]
                    and report["checkpoint_sha256"] == result["checkpoint_sha256"] ==
                    case["MF_source_cache"]["checkpoint_sha256"]
                    and report["official_commit"] == case["MF_source_cache"]["official_commit"],
                    "Official tracker report/cache differs")
            expected_md5 = inputs["source_frame_md5"] if role == "source" else target["score_frame_md5"]
            require(report["decoded_frame_md5"] == expected_md5, "Tracker evaluated different pixels")
            if role == "target":
                require(report["score_video"]["sha256"] == target["score_sha256"],
                        "Target tracker score-video differs")
            reports[role] = {"report": report_file, "tracks": track}
        prepared[arm] = {
            "schema": "r150-display-official-mf-v1", "case": sid, "role": arm,
            "run_id": proof["run_id"], "score": value,
            "actual_generated_video_sha256": video["sha256"],
            "valid_frames": geometry["valid_frames"], "fps": geometry["fps"],
            "crop_xywh": geometry["crop_xywh"],
            "metric": "IVEBench official Motion Fidelity",
            "dataset_scope": "Custom Sam task; same official MF implementation" if sid == "05_real_megumi_v" else "IVEBench",
            "evidence": {"verified_results": bound(verified_path), "original_result": result_file,
                         "individual_tracker_release": release_file, "final_tracker_release": bound(final_path),
                         "MF_complete": complete_file, "MF_seal": seal, "MF_inputs": bound(inputs_path),
                         "score_video": bound(score_video), "generated_video": video,
                         "generation_gate": proof["gate"], "generation_release": bound(batch),
                         "presentation": bound(presentation_path), "reports": reports},
            "non_target_GPU_allocation_state": None if final.get("unqueryable_GPU_allocations") else "queryable"}
    outputs = {}
    for arm, record in prepared.items():
        path = ROOT / "scores" / sid / (arm + ".json")
        if path.exists():
            require(read(path) == record, "Existing display score must not be replaced with different evidence")
        else:
            write(path, record)
        outputs[arm] = bound(path)
    summary = {"passed": True, "case": sid, "count": 4, "outputs": outputs,
               "original_verified_results": bound(verified_path), "final_release": bound(final_path),
               "scope": "Local import of already collected verified results; no scoring or GPU work"}
    write(ROOT / "audit/score_import" / (sid + ".json"), summary)
    print(sid, {arm: r["score"] for arm, r in prepared.items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    import_case(parser.parse_args().case)
