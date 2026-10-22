"""Drink-only 2+1+1 receipts: unknown GPU5, released split, released final global."""
import argparse
from pathlib import Path

from common import ROOT, bound, read, write, require, verify_record, expected_router
from hardware_prefix import hardware_files, verify_hardware_prefix
from ingest import validate_job

SEGMENTS = ("host41_prefix", "host41_split", "host41_global")
ROLES = (("early", "late"), ("split",), ("global_weak",))


def verify_split_release(record, manifest, bindings, runs):
    partial = read(record["split_partial_release"]["file"])
    evidence = read(record["split_source_evidence"]["file"])
    source = manifest["segments"]["host41_split"]
    target = manifest["segments"]["host41_global"]
    owner = source["service_owner"]
    require(partial.get("schema") == "r149-schedule-admission-partial-release-v1"
            and partial.get("passed") is True and partial.get("source_id") == "short_0358"
            and partial.get("segment_id") == "host41_split"
            and partial.get("stop_kind") == manifest["boundary"]["stop_kind"] == "independent_peer_admission"
            and partial.get("migration_manifest_sha256") == record["migration"]["sha256"]
            and partial.get("source_root") == source["remote_root"]
            and partial.get("service_owner") == owner
            and partial.get("producer_seal_sha256") == source["producer_seal_sha256"]
            and partial.get("completed_runs") == source["run_ids"]
            and partial.get("completed_roles") == ["split"]
            and partial.get("remaining_runs") == target["run_ids"]
            and partial.get("process_generation_absent") is True
            and partial.get("CUDA_allocation_absent") is True
            and partial.get("release_state") == "processes_and_cuda_released"
            and partial.get("original_segment_COMPLETE") is False,
            "Split partial release must preserve its one completed job and exact cleanup")
    attempt = "audit/" + source["attempt"] + "/"
    required = {"deploy_manifest.json", "processes/service.json", "processes/cleanup.json",
                "audit/RECOVERY_ATTEMPT1_LAUNCH.json", attempt + "FAILURE.json",
                attempt + "CAPACITY_MONITOR_EXIT.json", bindings["split"]["gate_relative_file"]}
    require(set(partial.get("evidence", {})) == set(evidence.get("files", {})) ==
            set(record.get("split_artifacts", {})) == required
            and evidence.get("owner") == owner
            and evidence.get("generations") == partial.get("registered_generations"),
            "All seven original split evidence files and process generations are required")
    originals = {}
    for relative in required:
        item, actual = partial["evidence"][relative], evidence["files"][relative]
        local = record["split_artifacts"][relative]
        require(item["path"] == source["remote_root"] + "/" + relative
                and item["sha256"] == actual["sha256"] == local["sha256"]
                and actual["path"] == item["path"]
                and actual["content"] == read(local["file"]),
                "Split evidence differs from the SHA-verified original: " + relative)
        originals[relative] = actual["content"]
    require(originals["processes/service.json"] == owner
            and partial["evidence"]["deploy_manifest.json"]["sha256"] == source["producer_seal_sha256"]
            and originals[bindings["split"]["gate_relative_file"]] == runs["split"]
            and partial["evidence"][bindings["split"]["gate_relative_file"]]["sha256"] ==
            record["job_gates"]["split"]["sha256"], "Split owner/seal/gate differs")
    cleanup = originals["processes/cleanup.json"]
    require(cleanup.get("service_record") == owner and cleanup.get("pid") == owner["pid"]
            and cleanup.get("process_absent") is True and cleanup.get("own_compute_absent") is True
            and cleanup.get("child_compute_absent") is True, "Split exact cleanup incomplete")
    generations = partial["registered_generations"]
    require(set(generations) == {"root_wrapper", "service", "controller", "supervisor",
                                "watchdog", "capacity_watchdog", "capacity_monitor"}
            and all(g.get("generation_absent") is True and g.get("actual_identity") is None
                    and isinstance(g.get("pid"), int) and g.get("expected_identity", {}).get("start_ticks")
                    for g in generations.values()), "Split generations are not all absent")
    launch = originals["audit/RECOVERY_ATTEMPT1_LAUNCH.json"]
    for name, process in (("service", owner), ("root_wrapper", launch)):
        require(generations[name]["pid"] == process["pid"]
                and generations[name]["expected_identity"] == process["identity"],
                "Split release registered another process generation")
    monitor = originals[attempt + "CAPACITY_MONITOR_EXIT.json"]
    require(monitor.get("exit_code") == 0 and monitor.get("exact_generation_absent") is True
            and monitor.get("pid") == generations["capacity_monitor"]["pid"]
            and monitor.get("identity") == generations["capacity_monitor"]["expected_identity"],
            "Split capacity monitor release differs")
    peer = manifest["readonly_peer"]
    failure = originals[attempt + "FAILURE.json"]
    require("Unexpected own compute identity " + str(peer["pid"]) in failure.get("error", "")
            and evidence.get("peer") == peer["identity"],
            "Original independent-peer admission failure must remain explicit")


def verify_three_segment_record(record, case, selected_binding=None, selected_run=None):
    from finalize_composite import ARMS, evidence_records, verify_target_segment
    require(case["source_id"] == "short_0358" and record.get("segment_count") == 3
            and record.get("recovery_two_arm_COMPLETE") is False, "Three actual drink segments required")
    for item in evidence_records(record).values():
        verify_record(item)
    manifest, deployment = (read(record[k]["file"]) for k in ("migration", "deployment"))
    require(manifest.get("schema") == "r149-three-segment-recovery-migration-v1"
            and manifest.get("source_id") == case["source_id"]
            and manifest.get("segment_order") == list(SEGMENTS)
            and set(manifest.get("segments", {})) == set(SEGMENTS)
            and deployment.get("schema") == "r149-three-segment-recovery-deployment-v1"
            and deployment.get("source_id") == case["source_id"]
            and deployment.get("migration_manifest_sha256") == record["migration"]["sha256"]
            and deployment.get("split_partial_release_sha256") == record["split_partial_release"]["sha256"]
            and set(deployment.get("segments", {})) == set(SEGMENTS), "Three-segment migration differs")
    bindings = {a: read(record["bindings"][a]["file"]) for a in ARMS}
    runs = {a: read(record["job_gates"][a]["file"]) for a in ARMS}
    schedules = read(ROOT / "EVALUATION_MANIFEST.json")["schedules"]
    for arm in ARMS:
        validate_job(case, dict(schedules[arm], id=arm), bindings[arm], runs[arm])
    if selected_run is not None:
        role = selected_run["role"]
        require(role in ARMS and runs[role] == selected_run and bindings[role] == selected_binding,
                "Selected media belongs to another run/binding")
    owners = []
    for key, roles in zip(SEGMENTS, ROLES):
        segment, deployed = manifest["segments"][key], deployment["segments"][key]
        require(segment["roles"] == deployed["roles"] == list(roles)
                and segment["run_ids"] == deployed["run_ids"] == [bindings[a]["run_id"] for a in roles],
                "Three-segment roles/runs differ")
        owner = runs[roles[0]]["service_owner"]
        owners.append(owner)
        for arm in roles:
            binding = bindings[arm]
            require(segment["host"] == deployed["host"] == binding["host"] == "H3_SERVER_B"
                    and segment["remote_root"] == deployed["remote_root"] == binding["remote_root"]
                    and deployed["producer_seal_sha256"] == binding["producer_seal"]["sha256"]
                    and runs[arm]["service_owner"] == owner, "Segment producer or actual owner differs")
        if key != SEGMENTS[-1]:
            require(owner == segment["service_owner"] and
                    segment["producer_seal_sha256"] == deployed["producer_seal_sha256"],
                    "Completed segment owner/seal differs")
    require(all(owners[i] != owners[j] for i in range(3) for j in range(i)),
            "Three segments must preserve distinct service owners")

    prior = read(record["prior_migration"]["file"])
    prior_deployment = read(record["prior_deployment"]["file"])
    links = manifest["prior_hardware_recovery"]
    for name, artifact in (("manifest", record["prior_migration"]),
                           ("prefix_release", record["partial_release"]),
                           ("source_evidence", record["partial_artifacts"]["source_evidence"])):
        require(links[name + "_sha256"] == artifact["sha256"], "Prior hardware evidence SHA differs")
    require(manifest["segments"]["host41_prefix"] == prior["segments"]["host41_prefix"]
            and manifest["segments"]["host41_split"]["remote_root"] ==
            prior["segments"]["host41_recovery"]["remote_root"], "Prior hardware lineage differs")
    prior_record = dict(record, migration=record["prior_migration"],
                        deployment=record["prior_deployment"])
    require(set(record["partial_artifacts"]) == set(hardware_files(prior)), "Hardware evidence missing")
    verify_hardware_prefix(prior, prior_deployment, read(record["partial_release"]["file"]),
                           prior_record, bindings, runs)

    science, geometry = manifest["science"], case["geometry"]
    require(science["seed"] == case["seed"]
            and science["noise_file_sha256"] == case["historical_initial_noise"]["sha256"]
            and science["prompt_sha256"] == case["prompt_sha256"]
            and science["geometry"] == {"width": geometry["width"], "height": geometry["height"],
                                       "frames": geometry["sampled_frames"], "fps": geometry["fps"]}
            and science["valid_frames"] == geometry["valid_frames"]
            and science["NFE"] == 20 and science["blocks"] == [0, 50]
            and science["schedules"] == {a: bindings[a]["steps_0based"] for a in ARMS},
            "Three-segment scientific controls differ")
    for arm in ARMS:
        router = expected_router(case, {"id": arm})
        require(science["arms"][arm] == {"alpha": router["alpha"], "phase_displacement": 0,
                "physical_query_window": [router["start_frame"], router["end_frame"]]},
                "Arm scientific controls differ")
        graph = (prior["science"]["target_graph_sha256"]["split"] if arm == "split" else
                 science["target_graph_sha256"][arm] if arm == "global_weak" else
                 science["source_graph_sha256"][arm])
        verify_record(bindings[arm]["graph"])
        require(graph == bindings[arm]["graph"]["sha256"], "Actual segment graph differs")
    boundary = manifest["boundary"]
    require(boundary["original_four_arm_COMPLETE_remains_absent"] is True
            and boundary["recovery_two_arm_COMPLETE_remains_absent"] is True
            and boundary["same_persistent_service_across_segments"] is False,
            "Partial batches must remain incomplete")
    sealed = read(bindings["global_weak"]["producer_seal"]["file"])["files"]
    require(sealed["configs/MIGRATION_MANIFEST.json"]["sha256"] == record["migration"]["sha256"],
            "Actual final producer does not seal this migration")
    verify_split_release(record, manifest, bindings, runs)
    verify_target_segment(record, case, bindings, runs, manifest["segments"]["host41_global"],
                          "drink_final_global_host41", record["migration"]["sha256"])
    return record


def build_record(evidence_dir, segment_gate, segment_complete, segment_release):
    from finalize_composite import ARMS, SCHEMA
    prior_dir = ROOT / "audit/hardware_recovery/prefix_evidence"
    prior = read(prior_dir / "MIGRATION_MANIFEST.json")
    split = read(evidence_dir / "SPLIT_SOURCE_EVIDENCE.json")
    return {
        "schema": SCHEMA, "passed": True, "source_id": "short_0358", "segment_count": 3,
        "same_persistent_service": False, "original_four_arm_COMPLETE": False,
        "recovery_two_arm_COMPLETE": False,
        "migration": bound(evidence_dir / "MIGRATION_MANIFEST.json"),
        "deployment": bound(evidence_dir / "MIGRATION_DEPLOYMENT.json"),
        "prior_migration": bound(prior_dir / "MIGRATION_MANIFEST.json"),
        "prior_deployment": bound(prior_dir / "MIGRATION_DEPLOYMENT.json"),
        "partial_release": bound(prior_dir / "PREFIX_PARTIAL_RELEASE.json"),
        "partial_artifacts": {k: bound(prior_dir / p) for k, p in hardware_files(prior).items()},
        "split_partial_release": bound(evidence_dir / "SPLIT_PARTIAL_RELEASE.json"),
        "split_source_evidence": bound(evidence_dir / "SPLIT_SOURCE_EVIDENCE.json"),
        "split_artifacts": {p: bound(evidence_dir / p) for p in split["files"]},
        "segment_gate": bound(segment_gate), "segment_complete": bound(segment_complete),
        "segment_release": bound(segment_release),
        "bindings": {a: bound(ROOT / "runtime/short_0358" / (a + ".json")) for a in ARMS},
        "job_gates": {a: bound(ROOT / "actual/short_0358" / a / "GATE.json") for a in ARMS}}


def main():
    from finalize_composite import ARMS, verify_composite_record
    p = argparse.ArgumentParser()
    p.add_argument("--evidence-dir", type=Path,
                   default=ROOT / "audit/three_segment_release/split_evidence")
    for name in ("segment-gate", "segment-complete", "segment-release"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args()
    record = build_record(args.evidence_dir, args.segment_gate, args.segment_complete, args.segment_release)
    case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"] if c["source_id"] == "short_0358")
    verify_composite_record(record, case)
    for arm in ARMS:
        presentation = ROOT / "review/short_0358" / arm / "PRESENTATION.json"
        if presentation.exists():
            proof = read(presentation)["validated_execution"]
            require(proof["run_record"] == read(record["job_gates"][arm]["file"])
                    and proof["binding"] == record["bindings"][arm], "Presentation differs")
    output = ROOT / "actual/short_0358/BATCH_RELEASE.json"
    if output.exists():
        require(read(output) == record, "Existing release record must not be replaced")
    write(output, record)
    print(output)


if __name__ == "__main__":
    main()
