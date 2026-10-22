"""Actual book 1+2+1 releases: two failed GPUs remain explicitly unknown."""
import argparse
from pathlib import Path
from common import ROOT, read, write, bound, require, verify_record, expected_router
from ingest import validate_job
import finalize_composite as base


def verify_middle(record, manifest, partial, runs):
    seg = manifest["segments"]["host41_middle"]
    owner = seg["service_owner"]
    require(partial["schema"] == "r149-schedule-hardware-partial-release-v1"
            and partial["passed"] is True and partial["source_id"] == "long_0039"
            and partial["segment_id"] == "host41_middle" and partial["stop_kind"] == "hardware_failure"
            and partial["migration_manifest_sha256"] == record["migration"]["sha256"]
            and partial["source_root"] == seg["remote_root"]
            and partial["producer_seal_sha256"] == seg["producer_seal_sha256"]
            and partial["service_owner"] == owner
            and partial["completed_roles"] == ["late", "split"]
            and partial["completed_runs"] == seg["run_ids"]
            and partial["remaining_runs"] == manifest["segments"]["host41_global"]["run_ids"]
            and partial["original_segment_COMPLETE"] is False
            and partial["process_generation_absent"] is True,
            "Middle two-output partial release differs")
    require(partial["CUDA_allocation_absent"] is None
            and partial["release_state"] == "processes_exited_gpu_unqueryable"
            and partial["gpu_health"] == "requires_reset"
            and partial["gpu_uuid"] == owner["gpu_uuid"], "GPU7 CUDA state must remain unknown")
    evidence = read(record["middle_source_evidence"]["file"])
    require(evidence["owner"] == owner and evidence["generations"] == partial["registered_generations"]
            and evidence["observed_unix"] == partial["created_unix"]
            and set(evidence["files"]) == set(partial["evidence"]) == set(record["middle_artifacts"]),
            "Middle original evidence set differs")
    originals = {}
    for rel, item in partial["evidence"].items():
        embedded, actual = evidence["files"][rel], record["middle_artifacts"][rel]
        require(item["path"] == embedded["path"] == seg["remote_root"] + "/" + rel
                and item["sha256"] == embedded["sha256"] == actual["sha256"]
                and embedded["content"] == read(actual["file"]), "Middle original bytes differ")
        originals[rel] = embedded["content"]
    require(partial["evidence"]["deploy_manifest.json"]["sha256"] == seg["producer_seal_sha256"]
            and originals["processes/service.json"] == owner, "Middle owner/seal differs")
    for arm in ("late", "split"):
        rel = read(record["bindings"][arm]["file"])["gate_relative_file"]
        require(originals[rel] == runs[arm]
                and partial["evidence"][rel]["sha256"] == record["job_gates"][arm]["sha256"],
                "Middle passed output differs")
    attempt = "audit/" + seg["attempt"] + "/"
    exit_check = originals[attempt + "HARDWARE_FAILURE_EXIT_CHECK.json"]
    generations = partial["registered_generations"]
    require(exit_check["all_recorded_generations_exited"] is True
            and exit_check["GPU_requires_reset"] is True and exit_check["gpu_index"] == 7
            and exit_check["gpu_uuid"] == owner["gpu_uuid"]
            and exit_check["CUDA_allocation_absent"] is None
            and exit_check["scientific_seal_sha256"] == seg["producer_seal_sha256"]
            and "GPU requires reset" in exit_check["GPU_health_stdout"], "GPU7 exit/health evidence differs")
    checks = {x["file"]: x for x in exit_check["recorded_processes"]}
    require(checks.keys() == generations.keys(), "Missing recorded process generation")
    for path, gen in generations.items():
        check = checks[path]
        require(gen["generation_absent"] is True and gen["actual_identity"] is None
                and gen["expected_identity"].get("start_ticks")
                and check["pid"] == gen["pid"] and check["expected_identity"] == gen["expected_identity"]
                and check["exact_generation_absent"] is True and check["actual_identity"] is None,
                "Middle registered generation remains alive or changed")
    for rel in ("processes/service.json", "audit/ATTEMPT1_LAUNCH.json"):
        actual = originals[rel]
        gen = generations[seg["remote_root"] + "/" + rel]
        require(gen["pid"] == actual["pid"] and gen["expected_identity"] == actual["identity"],
                "Middle actual service/wrapper differs")
    monitor = originals[attempt + "CAPACITY_MONITOR_EXIT.json"]
    gen = generations[seg["remote_root"] + "/processes/capacity_monitor.json"]
    require(monitor["pid"] == gen["pid"] and monitor["identity"] == gen["expected_identity"]
            and monitor["exit_code"] == 0 and monitor["exact_generation_absent"] is True,
            "Middle monitor exit differs")
    failure, cleanup = originals[attempt + "FAILURE.json"], originals[attempt + "CLEANUP_FAILURE.json"]
    require(failure.get("error") and cleanup["primary"] == failure["error"]
            and owner["gpu_uuid"] in cleanup["cleanup"] and "[N/A]" in cleanup["cleanup"],
            "Middle failed cleanup must remain recorded")
    failed = manifest["failure"]["failed_run"]
    router = originals["audit/router/" + failed + ".json"]
    require(originals["logs/" + failed + "_job.json"]["status"] != "success"
            and manifest["failure"]["replay_from_original_noise"] is True
            and router["completed_forward_calls"] == manifest["failure"]["completed_callbacks"] == 10
            and router["routed_calls"] == manifest["failure"]["routed_calls"] == 526,
            "Failed global attempt must not be counted as a complete output")


def verify_three_segment(record, case, selected_binding=None, selected_run=None):
    require(record.get("schema") == base.SCHEMA and record.get("passed") is True
            and record.get("source_id") == case["source_id"] == "long_0039"
            and record.get("segment_count") == 3 and record.get("same_persistent_service") is False
            and record.get("original_four_arm_COMPLETE") is False
            and set(record.get("bindings", {})) == set(base.ARMS)
            and set(record.get("job_gates", {})) == set(base.ARMS), "Actual complete 1+2+1 required")
    for item in base.evidence_records(record).values():
        verify_record(item)
    m, d, old_m, old_d = (read(record[k]["file"]) for k in
                          ("migration", "deployment", "prior_migration", "prior_deployment"))
    require(m["schema"] == "r150-three-segment-hardware-recovery-migration-v1"
            and m["source_id"] == "long_0039"
            and m["segment_order"] == ["host41_prefix", "host41_middle", "host41_global"]
            and set(m["segments"]) == set(m["segment_order"])
            and m["boundary"]["old_segments_COMPLETE_remain_absent"] is True
            and m["boundary"]["same_persistent_service_across_segments"] is False,
            "Actual three-segment manifest differs")
    require(d["schema"] == "r150-three-segment-hardware-recovery-deployment-v1"
            and d["source_id"] == "long_0039" and set(d["segments"]) == set(m["segments"])
            and d["migration_manifest_sha256"] == record["migration"]["sha256"]
            and d["second_partial_release_sha256"] == record["middle_partial_release"]["sha256"],
            "Three-segment deployment differs")
    prior = m["prior_hardware_recovery"]
    for key, entry in (("manifest", "prior_migration"), ("prefix_release", "partial_release")):
        require(prior[key]["sha256"] == record[entry]["sha256"], "Prior hardware lineage differs")
    require(prior["source_evidence"]["sha256"] == record["partial_artifacts"]["source_evidence"]["sha256"],
            "Prior source evidence differs")
    bindings = {a: read(record["bindings"][a]["file"]) for a in base.ARMS}
    runs = {a: read(record["job_gates"][a]["file"]) for a in base.ARMS}
    schedules = read(ROOT / "EVALUATION_MANIFEST.json")["schedules"]
    partitions = {"host41_prefix": ["early"], "host41_middle": ["late", "split"],
                  "host41_global": ["global_weak"]}
    owners = []
    for key, roles in partitions.items():
        seg, dep = m["segments"][key], d["segments"][key]
        require(seg["roles"] == dep["roles"] == roles and seg["run_ids"] == dep["run_ids"]
                == [bindings[a]["run_id"] for a in roles], "Segment roles/run IDs differ")
        owner = runs[roles[0]]["service_owner"]
        owners.append(owner)
        for arm in roles:
            b = bindings[arm]
            require(seg["host"] == dep["host"] == b["host"] == "H3_SERVER_B"
                    and seg["remote_root"] == dep["remote_root"] == b["remote_root"]
                    and dep["producer_seal_sha256"] == b["producer_seal"]["sha256"]
                    and runs[arm]["service_owner"] == owner, "Per-arm actual producer differs")
            validate_job(case, dict(schedules[arm], id=arm), b, runs[arm])
        if key != "host41_global":
            require(owner == seg["service_owner"]
                    and dep["producer_seal_sha256"] == seg["producer_seal_sha256"], "Failed-segment owner differs")
    require(all(owners[i] != owners[j] for i in range(3) for j in range(i)), "Distinct services required")
    for key in ("seed", "noise_file_sha256", "prompt_sha256", "conditioning_sha256", "geometry",
                "valid_frames", "schedules", "arms", "NFE", "blocks", "core_sha256", "layout_sha256"):
        require(m["science"][key] == old_m["science"][key], "Scientific settings changed")
    for arm in base.ARMS:
        expected = (old_m["science"]["source_graph_sha256"]["early"] if arm == "early"
                    else m["science"]["target_graph_sha256"][arm] if arm == "global_weak"
                    else old_m["science"]["target_graph_sha256"][arm])
        require(bindings[arm]["graph"]["sha256"] == expected, "Actual arm graph differs")
    require(m["segments"]["host41_prefix"] == old_m["segments"]["host41_prefix"], "Old prefix changed")
    prior_record = dict(record, migration=record["prior_migration"], deployment=record["prior_deployment"])
    base.verify_prefix(old_m, old_d, read(record["partial_release"]["file"]),
                       prior_record, bindings, runs)
    verify_middle(record, m, read(record["middle_partial_release"]["file"]), runs)
    seal = read(bindings["global_weak"]["producer_seal"]["file"])["files"]
    require(seal["configs/MIGRATION_MANIFEST.json"]["sha256"] == record["migration"]["sha256"],
            "Final target seal must cover migration")
    base.legacy.verify_target_segment(record, case, bindings, runs, m["segments"]["host41_global"],
                                      "book_final_global_host41", record["migration"]["sha256"])
    if selected_run is not None:
        role = selected_run["role"]
        require(runs[role] == selected_run and bindings[role] == selected_binding, "Presentation differs")
    return record


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prefix-evidence-dir", type=Path, required=True)
    p.add_argument("--middle-evidence-dir", type=Path, required=True)
    for name in ("segment_gate", "segment_complete", "segment_release"):
        p.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    a = p.parse_args()
    old, middle = a.prefix_evidence_dir, a.middle_evidence_dir
    om = read(old / "MIGRATION_MANIFEST.json")
    second = read(middle / "SECOND_PARTIAL_RELEASE.json")
    record = dict(schema=base.SCHEMA, passed=True, source_id="long_0039", segment_count=3,
                  same_persistent_service=False, original_four_arm_COMPLETE=False,
                  migration=bound(middle / "MIGRATION_MANIFEST.json"),
                  deployment=bound(middle / "MIGRATION_DEPLOYMENT.json"),
                  partial_release=bound(old / "PREFIX_PARTIAL_RELEASE.json"),
                  prior_migration=bound(old / "MIGRATION_MANIFEST.json"),
                  prior_deployment=bound(old / "MIGRATION_DEPLOYMENT.json"),
                  middle_partial_release=bound(middle / "SECOND_PARTIAL_RELEASE.json"),
                  middle_source_evidence=bound(middle / "SECOND_SOURCE_EVIDENCE.json"),
                  **{k: bound(getattr(a, k)) for k in ("segment_gate", "segment_complete", "segment_release")},
                  partial_artifacts={"source_evidence": bound(old / "SOURCE_EVIDENCE.json"),
                                     **{k: bound(old / k) for k in om["failure"]["source_evidence"]}},
                  middle_artifacts={k: bound(middle / k) for k in second["evidence"]},
                  bindings={a: bound(ROOT / "runtime/long_0039" / (a + ".json")) for a in base.ARMS},
                  job_gates={a: bound(ROOT / "actual/long_0039" / a / "GATE.json") for a in base.ARMS})
    case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"] if c["source_id"] == "long_0039")
    verify_three_segment(record, case)
    path = ROOT / "actual/long_0039/BATCH_RELEASE.json"
    require(not path.exists() or read(path) == record, "Existing release may not be replaced")
    write(path, record)
    print(path)


if __name__ == "__main__":
    main()
