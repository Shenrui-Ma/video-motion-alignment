"""Import collected official MF evidence into display records; no network/model work."""
import argparse
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, read, write, bound, require, verify_record, case_and_schedule
from finalize_batch import verify_batch_record
from ingest import validate

ARMS = ("early", "late", "split", "global_weak")
DANCES = {"musk05", "firefly06", "sam07"}
CHECKPOINT_SHA = "da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df"
OFFICIAL_COMMIT = "2dcf8900ee65197f43854c76f61c66a32bb8dbfc"


def expected_jobs(sid, plan, stream=None):
    if stream is not None:
        role = stream["role"]
        allowed = ("native", "fixed") + ARMS if sid in DANCES else ARMS
        require(stream["schema"] == "r150-completed-video-stream-input-v1"
                and stream["passed"] is True and stream["case"] == sid
                and role in allowed, "Invalid completed-video stream")
        new_source = plan["new_source_trackers"]
        require(type(new_source) is int and new_source in (0, 1)
                and plan["source_cache_count"] == 1 - new_source,
                "Source tracking/cache domain differs")
        require(not new_source or sid in {"firefly06", "sam07"},
                "Unexpected new source tracker")
        expected = [{"case": sid, "role": r}
                    for r in (["source"] if new_source else []) + [role]]
        require(plan["groups"] == [sid] and plan["jobs"] == expected
                and plan["unique_targets"] == 1, "Stream scoring job domain differs")
        return (role,), len(expected)
    roles = ("native", "fixed") + ARMS if sid in DANCES else ARMS
    jobs = [("source",) if sid in {"firefly06", "sam07"} else (), roles]
    expected = [{"case": sid, "role": r} for group in jobs for r in group]
    require(plan["groups"] == [sid] and plan["jobs"] == expected
            and plan["unique_targets"] == len(roles), "Scoring job domain differs")
    return roles, len(expected)


def import_case(sid, package_key=None):
    case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"] if c["source_id"] == sid)
    package_key = package_key or sid
    require(Path(package_key).name == package_key, "Invalid package key")
    package = ROOT / "mf_preparation/host60_batches" / package_key
    remote = Path(read(package / "configs/RUNTIME.json")["remote_root"])
    stream_file = package / "configs/GENERATION_INPUTS_VERIFIED.json"
    stream = read(stream_file) if stream_file.exists() else None
    roles, tracker_count = expected_jobs(sid, read(package / "configs/PLAN.json"), stream)
    target_count = len(roles)

    def remote_record(item):
        relative = Path(item["file"]).relative_to(remote)
        require(".." not in relative.parts, "Invalid remote evidence path")
        local = {"file": str(package / relative), "sha256": item["sha256"]}
        verify_record(local)
        return local

    verified_path = package / "audit/RESULTS_VERIFIED.json"
    verified = read(verified_path)
    require(verified["completed_targets"] == verified["requested_targets"] == target_count
            and len(verified["results"]) == target_count
            and {r["role"] for r in verified["results"]} == set(roles),
            "All declared target results required")
    final_path = package / "audit/FINAL_RELEASE_VERIFIED.json"
    final = read(final_path)
    require(all(final.get(k) is True for k in ("passed", "exact_processes_absent",
            "exact_CUDA_allocations_absent", "all_spawned_trackers_released", "peer_registrations_removed"))
            and len(final["tracker_identities"]) == tracker_count
            and final["completed_generated_scores"] == target_count,
            "Exact target tracker release incomplete")
    seal = remote_record(final["seal"])
    if stream is not None:
        require(bound(stream_file)["sha256"] ==
                read(seal["file"])["files"][str(stream_file.relative_to(package))],
                "Unsealed completed-video input proof")
    complete_file = remote_record(final["final_complete"])
    complete = read(complete_file["file"])
    require(complete.get("passed") is True and complete.get("new_trackers") == tracker_count
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
    for arm in roles:
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
        batch = ROOT / "actual" / sid / "BATCH_RELEASE.json"
        historical = sid == "musk05" and arm == "native"
        if historical:
            evidence_path = stream_file if stream else package / "configs/evidence/native/EVIDENCE.json"
            require(read(seal["file"])["files"][str(evidence_path.relative_to(package))] ==
                    bound(evidence_path)["sha256"], "Unsealed historical evidence")
            historical_proof = stream["proof"] if stream else read(evidence_path)
            for record in ("historical_manifest", "condition_recovery"):
                verify_record(historical_proof[record])
            recovery = read(historical_proof["condition_recovery"]["file"])
            require(recovery["passed"] and recovery["same_historical_embedding"] is True
                    and recovery["requires_shared_cache_native"] is False
                    and recovery["original_embedding_signature"] ==
                    recovery["actual_embedding_signature"], "Historical Native cache differs")
            video = case["media"]["native"]
            proof = {"video": video, "run_id": Path(video["file"]).stem, "gate": None}
            if stream is None:
                actual = read(ROOT / "review" / sid / "early/PRESENTATION.json")["validated_execution"]
                verify_batch_record(batch, case, read(actual["binding"]["file"]), actual["run_record"])
        else:
            proof = read(presentation_path)["validated_execution"]
            video = proof["video"]
            verify_record(proof["gate"])
            verify_record(proof["binding"])
            require(read(proof["gate"]["file"]) == proof["run_record"], "Actual gate changed")
            if stream is None:
                verify_batch_record(batch, case, read(proof["binding"]["file"]), proof["run_record"])
            else:
                _, _, schedule = case_and_schedule(sid, arm)
                validate(case, schedule, video["file"], proof["gate"]["file"], proof["binding"]["file"])
                for key in ("gate", "binding", "video"):
                    require(stream["proof"][key] == proof[key], "Stream generation proof differs")
                verify_record(stream["proof"]["presentation"])
                require(stream["proof"]["presentation"] == bound(presentation_path),
                        "Stream presentation changed")
        if stream is not None:
            require(stream["video"] == video and stream["run_id"] == proof["run_id"]
                    and stream["geometry"] == geometry, "Stream output differs")
            generation_release = stream["proof"]["generation_batch_release"]
            require(stream["generation_batch_release_pending"] is (generation_release is None),
                    "Producer release state is ambiguous")
            if generation_release:
                verify_record(generation_release)
                verify_batch_record(generation_release["file"], case,
                                    read(proof["binding"]["file"]), proof["run_record"])
        else:
            generation_release = bound(batch)
        verify_record(video)
        target = next(t for t in inputs["targets"] if t["role"] == arm)
        value = result.get("score", result.get("motion_fidelity"))
        require(isinstance(value, (int, float)) and math.isfinite(value) and value == v["score"]
                and result["case"] == v["case"] == sid and result["role"] == arm
                and result["actual_generated_video_sha256"] == v["actual_generated_video_sha256"] ==
                target["full_sha256"] == video["sha256"]
                and result["inventory_bindings"] == target["inventory_bindings"]
                and result["valid_frames"] == result["evaluation_frames"] == geometry["valid_frames"]
                and result["evaluation_fps"] == geometry["fps"]
                and result["source_cache_reused"] is bool(inputs["source_cache"])
                and result["official_numerics_unchanged"] is True,
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
                    CHECKPOINT_SHA and report["official_commit"] == OFFICIAL_COMMIT,
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
            "dataset_scope": "Custom role replacement; same official MF implementation" if sid in DANCES else "IVEBench",
            "evidence": {"verified_results": bound(verified_path), "original_result": result_file,
                         "individual_tracker_release": release_file, "final_tracker_release": bound(final_path),
                         "MF_complete": complete_file, "MF_seal": seal, "MF_inputs": bound(inputs_path),
                         "score_video": bound(score_video), "generated_video": video,
                         "generation_gate": proof["gate"], "generation_release": generation_release,
                         "presentation": bound(presentation_path) if not historical else None, "reports": reports},
            "non_target_GPU_allocation_state": None if final.get("unqueryable_GPU_allocations") else "queryable"}
        if historical:
            prepared[arm]["historical_media_reused"] = True
            prepared[arm]["evidence"]["historical_condition_binding"] = bound(evidence_path)
        if stream is not None:
            prepared[arm]["generation_batch_release_pending_at_MF"] = stream["generation_batch_release_pending"]
            prepared[arm]["evidence"]["completed_video_input"] = bound(stream_file)
    outputs = {}
    for arm, record in prepared.items():
        path = ROOT / "scores" / sid / (arm + ".json")
        if path.exists():
            require(read(path) == record, "Existing display score must not be replaced with different evidence")
        else:
            write(path, record)
        outputs[arm] = bound(path)
    summary = {"passed": True, "case": sid, "count": target_count, "outputs": outputs,
               "original_verified_results": bound(verified_path), "final_release": bound(final_path),
               "scope": "Local import of already collected verified results; no scoring or GPU work"}
    write(ROOT / "audit/score_import" / (package_key + ".json"), summary)
    if stream is not None and not inputs["source_cache"]:
        record = prepared[roles[0]]
        cache_path = ROOT / "mf_preparation/source_caches" / sid / "SOURCE_CACHE.json"
        cache = {"schema": "r150-verified-created-source-cache-v1", "case": sid,
                 "inputs": bound(inputs_path), **record["evidence"]["reports"]["source"],
                 "MF_release": bound(final_path), "verified_import": bound(
                     ROOT / "audit/score_import" / (package_key + ".json"))}
        if cache_path.exists():
            require(read(cache_path) == cache, "Different source cache is already registered")
        else:
            write(cache_path, cache)
    print(sid, {arm: r["score"] for arm, r in prepared.items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--package")
    args = parser.parse_args()
    import_case(args.case, args.package)
