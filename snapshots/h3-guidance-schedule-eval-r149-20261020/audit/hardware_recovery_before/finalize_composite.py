"""Verify genuine Sam 3+1 releases without claiming one four-job producer completed."""
import argparse
from pathlib import Path

from common import ROOT, bound, read, write, require, verify_record
from ingest import validate_job

SCHEMA = "r149-evaluation-composite-release-v1"
ARMS = ("early", "late", "split", "global_weak")
RECEIPTS = ("migration", "deployment", "partial_release", "segment_gate",
            "segment_complete", "segment_release")
PARTIAL_FILES = {
    "cleanup": "cleanup.json",
    "root_failure": "FAILURE.json",
    "capacity_monitor_exit": "CAPACITY_MONITOR_EXIT.json",
    "boundary_request": "BOUNDARY_REQUEST.json",
}


def evidence_records(record):
    result = {name: record[name] for name in RECEIPTS}
    for arm in ARMS:
        result["job_gate_" + arm] = record["job_gates"][arm]
        result["producer_binding_" + arm] = record["bindings"][arm]
    result.update({"prefix_" + key: record["partial_artifacts"][key] for key in PARTIAL_FILES})
    return result


def embedded_artifact(item, local):
    """Check the embedded JSON against a hash-verified copy of its original file."""
    require(isinstance(item.get("record"), dict) and len(item.get("sha256", "")) == 64
            and item.get("file"), "Missing embedded producer evidence")
    require(item["sha256"] == local["sha256"] and item["record"] == read(local["file"]),
            "Embedded partial artifact differs from the original file")
    return item["record"]


def verify_composite_record(record, case, selected_binding=None, selected_run=None):
    require(record.get("schema") == SCHEMA and record.get("passed") is True
            and record.get("source_id") == case["source_id"]
            and record.get("same_persistent_service") is False
            and record.get("original_four_arm_COMPLETE") is False,
            "Explicit multi-service evaluation record required")
    require(set(record.get("job_gates", {})) == set(ARMS)
            and set(record.get("bindings", {})) == set(ARMS), "All four roles required exactly once")
    require(set(record.get("partial_artifacts", {})) == set(PARTIAL_FILES),
            "Original prefix cleanup/failure/monitor/boundary files required")
    for item in evidence_records(record).values():
        verify_record(item)
    manifest = read(record["migration"]["file"])
    deployment = read(record["deployment"]["file"])
    partial = read(record["partial_release"]["file"])
    segment = read(record["segment_gate"]["file"])
    complete = read(record["segment_complete"]["file"])
    release = read(record["segment_release"]["file"])
    bindings = {arm: read(record["bindings"][arm]["file"]) for arm in ARMS}
    runs = {arm: read(record["job_gates"][arm]["file"]) for arm in ARMS}
    schedules = read(ROOT / "EVALUATION_MANIFEST.json")["schedules"]
    for arm in ARMS:
        validate_job(case, dict(schedules[arm], id=arm), bindings[arm], runs[arm])
    if selected_run is not None:
        role = selected_run["role"]
        require(role in ARMS and runs[role] == selected_run
                and bindings[role] == selected_binding, "Selected presentation belongs to another run/binding")

    validate_migration(manifest, deployment, record, case, bindings)
    source = manifest["segments"]["host9_prefix"]
    target = manifest["segments"]["host41_global"]
    migration_sha = record["migration"]["sha256"]
    old_owner = source["service_owner"]
    new_owner = runs["global_weak"]["service_owner"]
    require(old_owner != new_owner, "Migration must retain distinct actual service owners")
    require(all(runs[arm]["service_owner"] == old_owner for arm in ARMS[:3]),
            "Prefix roles came from another source service")
    require(partial.get("schema") == "r149-schedule-partial-release-v1"
            and partial.get("passed") is True and partial.get("source_id") == case["source_id"]
            and partial.get("segment_id") == "host9_prefix"
            and partial.get("jobs") == source["run_ids"]
            and partial.get("remaining") == target["run_ids"]
            and partial.get("service_owner") == old_owner
            and partial.get("producer_seal_sha256") == source["producer_seal_sha256"]
            and partial.get("migration_manifest_sha256") == migration_sha
            and partial.get("process_generation_absent") is True
            and partial.get("CUDA_allocation_absent") is True
            and partial.get("original_four_arm_COMPLETE") is False,
            "Three-job partial release is incomplete or falsely claims four jobs")
    require(set(partial["job_gates"]) == set(source["run_ids"]), "Prefix gate set differs")
    for arm in ARMS[:3]:
        expected = partial["job_gates"][runs[arm]["run_id"]]
        require(expected["sha256"] == record["job_gates"][arm]["sha256"],
                "Partial release refers to a different per-job gate")
        require(expected["file"] == bindings[arm]["remote_root"] + "/" +
                bindings[arm]["gate_relative_file"], "Partial gate remote identity differs")
    artifacts = {name: embedded_artifact(partial[name], record["partial_artifacts"][name])
                 for name in PARTIAL_FILES}
    cleanup, failure, monitor, boundary = (artifacts[name] for name in PARTIAL_FILES)
    require(cleanup.get("service_record") == old_owner and cleanup.get("pid") == old_owner["pid"]
            and cleanup.get("process_absent") is True and cleanup.get("own_compute_absent") is True
            and cleanup.get("child_compute_absent") is True, "Exact prefix cleanup incomplete")
    require(boundary.get("migration_manifest_sha256") == migration_sha
            and boundary.get("service_owner") == old_owner
            and boundary.get("remaining") == target["run_ids"]
            and "root admission pending" in failure.get("error", "")
            and failure["unix"] >= boundary["created_unix"], "Planned stop lineage differs")
    require(monitor.get("exit_code") == 0 and monitor.get("exact_generation_absent") is True,
            "Prefix capacity monitor release incomplete")
    generations = partial.get("registered_generations", {})
    require(all(name in generations for name in ("service", "root_wrapper"))
            and all(v.get("generation_absent") is True and
                    v.get("actual_identity") != v.get("expected_identity")
                    for v in generations.values()), "Prefix generation release incomplete")

    require(segment.get("schema") == "r149-fixed-schedule-segment-gate-v1"
            and segment.get("passed") is True and segment.get("source_id") == case["source_id"]
            and segment.get("segment_id") == "sam_global_weak_host41"
            and segment.get("migration_manifest_sha256") == migration_sha
            and segment.get("same_persistent_service") is True
            and segment.get("phase_displacement") == 0
            and segment.get("producer_seal_sha256") == bindings["global_weak"]["producer_seal"]["sha256"]
            and segment.get("runs") == {"global_weak": runs["global_weak"]}
            and segment.get("service_owner") == new_owner, "Single-arm segment gate differs")
    require(complete.get("schema") == "r149-schedule-segment-completion-v1"
            and complete.get("passed") is True
            and complete.get("segment_id") == "sam_global_weak_host41"
            and complete.get("migration_manifest_sha256") == migration_sha
            and complete.get("jobs") == target["run_ids"] and complete.get("remaining") == []
            and complete.get("GPU_released") is True and complete.get("service_owner") == new_owner
            and complete.get("runtime_gate_sha256") == record["segment_gate"]["sha256"],
            "Single-arm completion differs")
    cleanup = release.get("cleanup", {})
    require(release.get("owner") == new_owner and release.get("passed") is True
            and release.get("process_absent") is True and release.get("CUDA_allocation_absent") is True
            and cleanup.get("pid") == new_owner["pid"] and cleanup.get("process_absent") is True
            and cleanup.get("own_compute_absent") is True, "Single-arm exact release incomplete")
    return record


def validate_migration(manifest, deployment, record, case, bindings):
    require(manifest.get("schema") == "r149-sam-global-weak-migration-v1"
            and manifest.get("source_id") == case["source_id"] == "05_real_megumi_v"
            and set(manifest["segments"]) == {"host9_prefix", "host41_global"},
            "Unexpected migration case or segment set")
    source, target = (manifest["segments"][key] for key in ("host9_prefix", "host41_global"))
    require(source["roles"] == list(ARMS[:3]) and target["roles"] == ["global_weak"],
            "Migration roles must be the exact 3+1 partition")
    for segment in (source, target):
        require(segment["run_ids"] == [bindings[arm]["run_id"] for arm in segment["roles"]],
                "Migration run IDs differ")
        for arm in segment["roles"]:
            b = bindings[arm]
            require(segment["host"] == b["host"] and segment["remote_root"] == b["remote_root"],
                    "Migration host/root differs from this arm's producer")
    require(all(bindings[arm]["producer_seal"]["sha256"] == source["producer_seal_sha256"]
                for arm in ARMS[:3]), "Prefix producer seal differs")
    require(source["host"] == "H3_SERVER_A" and target["host"] == "H3_SERVER_B",
            "Unexpected migration host pair")
    science, geometry = manifest["science"], case["geometry"]
    require(science["seed"] == case["seed"]
            and science["noise_file_sha256"] == case["historical_initial_noise"]["sha256"]
            and science["prompt_sha256"] == case["prompt_sha256"]
            and science["geometry"] == {"width": geometry["width"], "height": geometry["height"],
                                        "frames": geometry["sampled_frames"], "fps": geometry["fps"]}
            and science["valid_frames"] == geometry["valid_frames"]
            and science["NFE"] == 20 and science["blocks"] == [0, 50]
            and science["schedules"] == {arm: bindings[arm]["steps_0based"] for arm in ARMS}
            and science["global_weak"] == {"alpha": 0.25, "physical_query_window": [0, 140],
                                          "phase_displacement": 0}, "Migration scientific controls differ")
    boundary = manifest["boundary"]
    require(boundary["original_four_arm_COMPLETE_remains_absent"] is True
            and boundary["same_persistent_service_across_hosts"] is False,
            "Migration must preserve the original incomplete batch")
    target_binding = bindings["global_weak"]
    require(science["target_global_graph_sha256"] == target_binding["graph"]["sha256"],
            "Migration target graph differs")
    verify_record(target_binding["graph"])
    sealed = read(target_binding["producer_seal"]["file"])["files"]
    require(sealed["configs/MIGRATION_MANIFEST.json"]["sha256"] == record["migration"]["sha256"],
            "Migration manifest is not covered by the actual target seal")
    validate_deployment(deployment, record, bindings)


def validate_deployment(deployment, record, bindings):
    require(deployment.get("schema") == "r149-sam-migration-deployment-v1"
            and deployment.get("source_id") == "05_real_megumi_v"
            and deployment.get("migration_manifest_sha256") == record["migration"]["sha256"]
            and set(deployment.get("segments", {})) == {"host9_prefix", "host41_global"},
            "Deployment does not bind the actual migration manifest")
    for key, arms in (("host9_prefix", ARMS[:3]), ("host41_global", ARMS[3:])):
        segment = deployment["segments"][key]
        require(segment.get("roles") == list(arms)
                and segment.get("run_ids") == [bindings[arm]["run_id"] for arm in arms],
                "Deployment role/run set differs")
        for arm in arms:
            binding = bindings[arm]
            require(segment.get("host") == binding["host"]
                    and segment.get("remote_root") == binding["remote_root"]
                    and segment.get("producer_seal_sha256") == binding["producer_seal"]["sha256"],
                    "Deployment does not bind this arm's exact producer seal/host/root")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--prefix-evidence-dir", type=Path, required=True,
                   help="Local original cleanup.json, FAILURE.json, CAPACITY_MONITOR_EXIT.json and BOUNDARY_REQUEST.json.")
    for name in RECEIPTS:
        p.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    a = p.parse_args()
    case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]
                if c["source_id"] == a.case)
    record = {"schema": SCHEMA, "passed": True, "source_id": a.case,
              "same_persistent_service": False, "original_four_arm_COMPLETE": False,
              **{name: bound(getattr(a, name)) for name in RECEIPTS},
              "partial_artifacts": {key: bound(a.prefix_evidence_dir / name)
                                    for key, name in PARTIAL_FILES.items()},
              "job_gates": {arm: bound(ROOT / "actual" / a.case / arm / "GATE.json") for arm in ARMS},
              "bindings": {arm: bound(ROOT / "runtime" / a.case / (arm + ".json")) for arm in ARMS}}
    verify_composite_record(record, case)
    for arm in ARMS:
        path = ROOT / "review" / a.case / arm / "PRESENTATION.json"
        if path.exists():
            proof = read(path)["validated_execution"]
            require(proof["run_record"] == read(record["job_gates"][arm]["file"])
                    and proof["binding"] == record["bindings"][arm], "Presentation differs")
    destination = ROOT / "actual" / a.case / "BATCH_RELEASE.json"
    if destination.exists():
        require(read(destination) == record, "Existing release record must not be replaced")
    write(destination, record)
    print(destination)


if __name__ == "__main__":
    main()
