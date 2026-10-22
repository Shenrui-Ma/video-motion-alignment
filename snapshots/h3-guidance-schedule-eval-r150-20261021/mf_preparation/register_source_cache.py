"""Register a finished source-only tracker after exact release and pixel checks."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ROOT, read, write, bound, require, verify_record, case_and_schedule


def register(sid):
    require(sid in ("firefly06", "sam07"), "Unexpected first-time source")
    package = ROOT / "mf_preparation/host60_batches" / (sid + "__source")
    remote = Path(read(package / "configs/RUNTIME.json")["remote_root"])
    final_path = package / "audit/FINAL_RELEASE_VERIFIED.json"
    final = read(final_path)

    def local(record):
        p = package / Path(record["file"]).relative_to(remote)
        value = {"file": str(p), "sha256": record["sha256"]}
        verify_record(value)
        return value

    require(all(final.get(k) is True for k in ("passed", "exact_processes_absent",
            "exact_CUDA_allocations_absent", "all_spawned_trackers_released",
            "peer_registrations_removed")), "Source tracker release incomplete")
    require(len(final["tracker_identities"]) == 1
            and final["completed_generated_scores"] == 0
            and final["result_receipts"] == [], "Unexpected target computation")
    seal = read(local(final["seal"])["file"])
    require(seal["schema"] == "r150-host60-reference-only-mf-v1", "Wrong batch kind")
    for rel, digest in seal["files"].items():
        require(bound(package / rel)["sha256"] == digest, "Sealed source input changed")
    plan = read(package / "configs/PLAN.json")
    require(plan["jobs"] == [{"case": sid, "role": "source"}]
            and plan["unique_targets"] == 0, "Unexpected source jobs")
    complete = read(local(final["final_complete"])["file"])
    require(complete["passed"] and complete["remaining"] == []
            and complete["new_trackers"] == 1, "Source tracking incomplete")
    state_path = package / "state" / sid / "source.json"
    require(bound(state_path) == local(final["state_receipts"][0]), "Unbound source state")
    state = read(state_path)
    release_file = local(state["release"])
    require(release_file == local(final["child_release_receipts"][0]),
            "Individual release differs")
    release = read(release_file["file"])
    require(release["passed"] and release["returncode"] == 0 and
            release["CUDA_absent"] and release["process_absent"], "Source child not released")
    report_path = package / state["folder"] / "REPORT.json"
    report = read(report_path)
    tracks = report_path.parent / "tracks.npz"
    inputs_path = package / "cases" / sid / "INPUTS.json"
    inputs = read(inputs_path)
    _, case, _ = case_and_schedule(sid, "native")
    require(inputs["targets"] == [] and inputs["source_cache"] is None
            and inputs["source_full_sha256"] == case["media"]["source"]["sha256"],
            "Different source video")
    require(report["passed"] and bound(report_path)["sha256"] == state["report_sha256"]
            and bound(tracks)["sha256"] == report["tracks_sha256"]
            and report["decoded_frame_md5"] == inputs["source_frame_md5"]
            and report["effective_frame_count"] == inputs["valid_frames"] == 141
            and report["source_score_sha256"] == inputs["source_score_sha256"]
            and report["source_prepared_sha256"] == inputs["source_full_sha256"]
            and report["selection_sha256"] == inputs["selection_sha256"]
            and report["official_commit"] == "2dcf8900ee65197f43854c76f61c66a32bb8dbfc"
            and report["checkpoint_sha256"] ==
            "da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df",
            "Source tracker pixels or numerical identity differ")
    cache = {"schema": "r150-verified-created-source-cache-v1", "case": sid,
             "inputs": bound(inputs_path), "report": bound(report_path), "tracks": bound(tracks),
             "MF_release": bound(final_path), "source_only": True}
    path = ROOT / "mf_preparation/source_caches" / sid / "SOURCE_CACHE.json"
    if path.exists():
        require(read(path) == cache, "Source cache already registered differently")
    else:
        write(path, cache)
    print(sid, bound(path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=("firefly06", "sam07"))
    register(parser.parse_args().case)
