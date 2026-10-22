"""Verify genuine segmented releases without claiming one four-job producer completed."""
import argparse
from pathlib import Path

from common import ROOT, bound, read, write, require, verify_record
from ingest import validate_job
from hardware_prefix import hardware_files, verify_hardware_prefix

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

def migration_shape(manifest):
    if (manifest.get("schema") == "r149-sam-global-weak-migration-v1"
            and manifest.get("source_id") == "05_real_megumi_v"):
        return "host9_prefix", "host41_global", "sam_global_weak_host41", False
    require(manifest.get("schema") == "r149-hardware-recovery-migration-v1"
            and manifest.get("source_id") == "short_0358"
            and manifest.get("stop_kind") == "hardware_failure",
            "Unsupported migration case or stop kind")
    return "host41_prefix", "host41_recovery", "drink_split_global_host41", True


def evidence_records(record):
    result = {name: record[name] for name in RECEIPTS}
    for arm in ARMS:
        result["job_gate_" + arm] = record["job_gates"][arm]
        result["producer_binding_" + arm] = record["bindings"][arm]
    result.update({"prefix_" + key: value for key, value in record["partial_artifacts"].items()})
    if record.get("segment_count") == 3:
        for key in ("prior_migration", "prior_deployment", "split_partial_release", "split_source_evidence"):
            result[key] = record[key]
        result.update({"split_" + key: value for key, value in record["split_artifacts"].items()})
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
    if record.get("segment_count") == 3:
        from three_segment_release import verify_three_segment_record
        return verify_three_segment_record(record, case, selected_binding, selected_run)
    for item in evidence_records(record).values():
        verify_record(item)
    manifest = read(record["migration"]["file"])
    source_key, target_key, segment_id, hardware = migration_shape(manifest)
    expected_files = hardware_files(manifest) if hardware else PARTIAL_FILES
    require(set(record.get("partial_artifacts", {})) == set(expected_files),
            "All original prefix release evidence files required")
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
    source = manifest["segments"][source_key]
    target = manifest["segments"][target_key]
    migration_sha = record["migration"]["sha256"]
    old_owner = source["service_owner"]
    new_owner = runs["global_weak"]["service_owner"]
    require(old_owner != new_owner, "Migration must retain distinct actual service owners")
    require(all(runs[arm]["service_owner"] == old_owner for arm in source["roles"]),
            "Prefix roles came from another source service")
    require(all(runs[arm]["service_owner"] == new_owner for arm in target["roles"]),
            "Recovery roles came from different services")
    if hardware:
        verify_hardware_prefix(manifest, deployment, partial, record, bindings, runs)
    else:
        verify_planned_prefix(partial, record, source, target, old_owner, migration_sha, bindings, runs)

    verify_target_segment(record, case, bindings, runs, target, segment_id, migration_sha)
    return record


def verify_target_segment(record, case, bindings, runs, target, segment_id, migration_sha):
    segment = read(record["segment_gate"]["file"])
    complete = read(record["segment_complete"]["file"])
    release = read(record["segment_release"]["file"])
    new_owner = runs["global_weak"]["service_owner"]
    require(segment.get("schema") == "r149-fixed-schedule-segment-gate-v1"
            and segment.get("passed") is True and segment.get("source_id") == case["source_id"]
            and segment.get("segment_id") == segment_id
            and segment.get("migration_manifest_sha256") == migration_sha
            and segment.get("same_persistent_service") is True
            and segment.get("phase_displacement") == 0
            and segment.get("producer_seal_sha256") == bindings["global_weak"]["producer_seal"]["sha256"]
            and segment.get("runs") == {arm: runs[arm] for arm in target["roles"]}
            and segment.get("service_owner") == new_owner, "Recovery segment gate differs")
    require(complete.get("schema") == "r149-schedule-segment-completion-v1"
            and complete.get("passed") is True
            and complete.get("segment_id") == segment_id
            and complete.get("migration_manifest_sha256") == migration_sha
            and complete.get("jobs") == target["run_ids"] and complete.get("remaining") == []
            and complete.get("GPU_released") is True and complete.get("service_owner") == new_owner
            and complete.get("runtime_gate_sha256") == record["segment_gate"]["sha256"],
            "Recovery segment completion differs")
    cleanup = release.get("cleanup", {})
    require(release.get("owner") == new_owner and release.get("passed") is True
            and release.get("process_absent") is True and release.get("CUDA_allocation_absent") is True
            and cleanup.get("pid") == new_owner["pid"] and cleanup.get("process_absent") is True
            and cleanup.get("own_compute_absent") is True, "Recovery segment exact release incomplete")



def verify_planned_prefix(partial, record, source, target, old_owner, migration_sha, bindings, runs):
    require(partial.get("schema") == "r149-schedule-partial-release-v1"
            and partial.get("passed") is True and partial.get("source_id") == "05_real_megumi_v"
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

def validate_migration(manifest, deployment, record, case, bindings):
    source_key, target_key, _, hardware = migration_shape(manifest)
    require(manifest.get("source_id") == case["source_id"]
            and set(manifest["segments"]) == {source_key, target_key},
            "Unexpected migration case or segment set")
    source, target = (manifest["segments"][key] for key in (source_key, target_key))
    cut = 2 if hardware else 3
    require(source["roles"] == list(ARMS[:cut]) and target["roles"] == list(ARMS[cut:]),
            "Migration roles differ from the approved partition")
    for segment in (source, target):
        require(segment["run_ids"] == [bindings[arm]["run_id"] for arm in segment["roles"]],
                "Migration run IDs differ")
        for arm in segment["roles"]:
            b = bindings[arm]
            require(segment["host"] == b["host"] and segment["remote_root"] == b["remote_root"],
                    "Migration host/root differs from this arm's producer")
    require(all(bindings[arm]["producer_seal"]["sha256"] == source["producer_seal_sha256"]
                for arm in source["roles"]), "Prefix producer seal differs")
    require(source["host"] == ("H3_SERVER_B" if hardware else "H3_SERVER_A")
            and target["host"] == "H3_SERVER_B",
            "Unexpected migration host pair")
    science, geometry = manifest["science"], case["geometry"]
    require(science["seed"] == case["seed"]
            and science["noise_file_sha256"] == case["historical_initial_noise"]["sha256"]
            and science["prompt_sha256"] == case["prompt_sha256"]
            and science["geometry"] == {"width": geometry["width"], "height": geometry["height"],
                                        "frames": geometry["sampled_frames"], "fps": geometry["fps"]}
            and science["valid_frames"] == geometry["valid_frames"]
            and science["NFE"] == 20 and science["blocks"] == [0, 50]
            and science["schedules"] == {arm: bindings[arm]["steps_0based"] for arm in ARMS},
            "Migration scientific controls differ")
    if hardware:
        from common import expected_router
        for arm in ARMS:
            router = expected_router(case, {"id": arm})
            require(science["arms"][arm] == {
                "alpha": router["alpha"],
                "physical_query_window": [router["start_frame"], router["end_frame"]],
                "phase_displacement": 0}, "Recovery arm controls differ")
            graph_set = "source_graph_sha256" if arm in source["roles"] else "target_graph_sha256"
            require(science[graph_set][arm] == bindings[arm]["graph"]["sha256"],
                    "Recovery graph differs from the migration manifest")
    else:
        require(science["global_weak"] == {"alpha": 0.25, "physical_query_window": [0, 140],
                                          "phase_displacement": 0}, "Migration global controls differ")
    boundary = manifest["boundary"]
    require(boundary["original_four_arm_COMPLETE_remains_absent"] is True
            and boundary["same_persistent_service_across_segments" if hardware
                         else "same_persistent_service_across_hosts"] is False,
            "Migration must preserve the original incomplete batch")
    target_binding = bindings["global_weak"]
    if not hardware:
        require(science["target_global_graph_sha256"] == target_binding["graph"]["sha256"],
                "Migration target graph differs")
    verify_record(target_binding["graph"])
    sealed = read(target_binding["producer_seal"]["file"])["files"]
    require(sealed["configs/MIGRATION_MANIFEST.json"]["sha256"] == record["migration"]["sha256"],
            "Migration manifest is not covered by the actual target seal")
    validate_deployment(deployment, record, bindings, manifest)


def validate_deployment(deployment, record, bindings, manifest):
    source_key, target_key, _, hardware = migration_shape(manifest)
    require(deployment.get("schema") == ("r149-hardware-recovery-deployment-v1" if hardware
                                        else "r149-sam-migration-deployment-v1")
            and deployment.get("source_id") == manifest["source_id"]
            and deployment.get("migration_manifest_sha256") == record["migration"]["sha256"]
            and set(deployment.get("segments", {})) == {source_key, target_key},
            "Deployment does not bind the actual migration manifest")
    cut = 2 if hardware else 3
    for key, arms in ((source_key, ARMS[:cut]), (target_key, ARMS[cut:])):
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
                   help="Sam: four original stop/cleanup files. Drink: SOURCE_EVIDENCE.json plus original files in their relative paths.")
    for name in RECEIPTS:
        p.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    a = p.parse_args()
    case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]
                if c["source_id"] == a.case)
    manifest = read(a.migration)
    files = hardware_files(manifest) if migration_shape(manifest)[3] else PARTIAL_FILES
    record = {"schema": SCHEMA, "passed": True, "source_id": a.case,
              "same_persistent_service": False, "original_four_arm_COMPLETE": False,
              **{name: bound(getattr(a, name)) for name in RECEIPTS},
              "partial_artifacts": {key: bound(a.prefix_evidence_dir / name)
                                    for key, name in files.items()},
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
