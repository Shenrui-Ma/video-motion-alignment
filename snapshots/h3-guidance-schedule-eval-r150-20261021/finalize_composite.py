"""R150 book: one verified output before hardware failure, then three new outputs."""
import argparse
import importlib.util
import sys
from pathlib import Path
from common import ROOT, bound, read, write, require, verify_record, expected_router
from ingest import validate_job

OLD = ROOT.with_name("h3-guidance-schedule-eval-r149-20261020")
sys.path.append(str(OLD))
spec = importlib.util.spec_from_file_location("r149_release_helpers", OLD / "finalize_composite.py")
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
ARMS = ("early", "late", "split", "global_weak")
SCHEMA = "r149-evaluation-composite-release-v1"
RECEIPTS = legacy.RECEIPTS
def evidence_records(record):
    if record.get("segment_count") == 3:
        base = dict(record)
        base.pop("segment_count")
        result = legacy.evidence_records(base)
        for key in ("prior_migration", "prior_deployment", "middle_partial_release", "middle_source_evidence"):
            result[key] = record[key]
        result.update({"middle_" + key: value for key, value in record["middle_artifacts"].items()})
        return result
    return legacy.evidence_records(record)


def validate_migration(manifest, deployment, record, case, bindings):
    require(case["source_id"] == "long_0039"
            and manifest.get("schema") == "r149-hardware-recovery-migration-v1"
            and manifest.get("source_id") == case["source_id"]
            and manifest.get("stop_kind") == "hardware_failure",
            "Expected actual book hardware recovery")
    require(set(manifest["segments"]) == {"host41_prefix", "host41_recovery"}, "Segment set differs")
    source, target = (manifest["segments"][k] for k in ("host41_prefix", "host41_recovery"))
    require(source["roles"] == ["early"] and target["roles"] == list(ARMS[1:])
            and target["segment_id"] == "book_late_split_global_host41", "Approved 1+3 partition differs")
    require(deployment.get("schema") == "r149-hardware-recovery-deployment-v1"
            and deployment.get("source_id") == case["source_id"]
            and deployment.get("migration_manifest_sha256") == record["migration"]["sha256"]
            and deployment.get("prefix_partial_release_sha256") == record["partial_release"]["sha256"]
            and set(deployment["segments"]) == set(manifest["segments"]), "Deployment linkage differs")
    for key, seg in manifest["segments"].items():
        dep = deployment["segments"][key]
        require(seg["run_ids"] == dep["run_ids"] == [bindings[a]["run_id"] for a in seg["roles"]]
                and dep["roles"] == seg["roles"], "Role/run set differs")
        for arm in seg["roles"]:
            b = bindings[arm]
            require(seg["host"] == dep["host"] == b["host"] == "H3_SERVER_B"
                    and seg["remote_root"] == dep["remote_root"] == b["remote_root"]
                    and dep["producer_seal_sha256"] == b["producer_seal"]["sha256"],
                    "Actual host/root/seal differs")
    require(source["producer_seal_sha256"] == bindings["early"]["producer_seal"]["sha256"],
            "Original producer seal differs")
    s, g = manifest["science"], case["geometry"]
    require(s["seed"] == case["seed"] and s["prompt_sha256"] == case["prompt_sha256"]
            and s["noise_file_sha256"] == case["historical_initial_noise"]["sha256"]
            and s["geometry"] == dict(width=g["width"], height=g["height"], frames=g["sampled_frames"], fps=g["fps"])
            and s["valid_frames"] == g["valid_frames"] and s["NFE"] == 20 and s["blocks"] == [0, 50],
            "Scientific controls differ")
    for arm in ARMS:
        router = expected_router(case, {"id": arm})
        require(s["schedules"][arm] == bindings[arm]["steps_0based"]
                and s["arms"][arm] == dict(alpha=router["alpha"],
                    physical_query_window=[router["start_frame"], router["end_frame"]], phase_displacement=0),
                "Schedule/query controls differ")
        key = "source_graph_sha256" if arm == "early" else "target_graph_sha256"
        require(s[key][arm] == bindings[arm]["graph"]["sha256"], "Migration graph SHA differs")
    require(manifest["boundary"]["original_four_arm_COMPLETE_remains_absent"] is True
            and manifest["boundary"]["same_persistent_service_across_segments"] is False,
            "Original incomplete batch must remain incomplete")
    seal = read(bindings["global_weak"]["producer_seal"]["file"])["files"]
    require(seal["configs/MIGRATION_MANIFEST.json"]["sha256"] == record["migration"]["sha256"],
            "Target seal does not cover migration")


def verify_prefix(manifest, deployment, partial, record, bindings, runs):
    source, target = (manifest["segments"][k] for k in ("host41_prefix", "host41_recovery"))
    owner = source["service_owner"]
    require(partial.get("schema") == "r149-schedule-hardware-partial-release-v1"
            and partial.get("passed") is True and partial.get("source_id") == "long_0039"
            and partial.get("segment_id") == "host41_prefix" and partial.get("stop_kind") == "hardware_failure"
            and partial.get("source_root") == source["remote_root"] and partial.get("service_owner") == owner
            and partial.get("producer_seal_sha256") == source["producer_seal_sha256"]
            and partial.get("completed_roles") == ["early"] and partial.get("completed_runs") == source["run_ids"]
            and partial.get("remaining_runs") == target["run_ids"]
            and partial.get("migration_manifest_sha256") == record["migration"]["sha256"]
            and partial.get("process_generation_absent") is True
            and partial.get("original_four_arm_COMPLETE") is False, "Prefix identity/completion differs")
    require("CUDA_allocation_absent" in partial and partial["CUDA_allocation_absent"] is None
            and partial.get("release_state") == "processes_exited_gpu_unqueryable"
            and partial.get("gpu_health") == "requires_reset" and partial.get("gpu_uuid") == owner["gpu_uuid"],
            "Original GPU6 state must remain unknown")
    expected = manifest["failure"]["source_evidence"]
    evidence = read(record["partial_artifacts"]["source_evidence"]["file"])
    require(set(record["partial_artifacts"]) == {"source_evidence", *expected}
            and partial["evidence"] == expected and set(evidence["files"]) == set(expected)
            and evidence["owner"] == owner and evidence["boot_id"] == source["boot_id"]
            and evidence["generations"] == partial["registered_generations"]
            and evidence["cuda_raw"] == partial["raw_compute_telemetry"]
            and evidence["observed_unix"] == partial["created_unix"], "Prefix evidence snapshot differs")
    originals = {}
    for rel, item in expected.items():
        local, embedded = record["partial_artifacts"][rel], evidence["files"][rel]
        require(item["path"] == source["remote_root"] + "/" + rel
                and local["sha256"] == item["sha256"] == embedded["sha256"]
                and embedded["path"] == item["path"] and embedded["content"] == read(local["file"]),
                "Original evidence bytes/content differ: " + rel)
        originals[rel] = embedded["content"]
    attempt = "audit/" + source["attempt"] + "/"
    require(expected["deploy_manifest.json"]["sha256"] == source["producer_seal_sha256"]
            and originals["processes/service.json"] == owner, "Original owner/seal differs")
    early_path = bindings["early"]["gate_relative_file"]
    require(originals[early_path] == runs["early"] and set(partial["gates"]) == set(source["run_ids"])
            and partial["gates"][runs["early"]["run_id"]] == {
                "path": source["remote_root"] + "/" + early_path,
                "sha256": record["job_gates"]["early"]["sha256"]}, "Original early gate differs")
    generations = partial["registered_generations"]
    required = {"audit/ATTEMPT1_LAUNCH.json", "processes/service.json", "processes/controller.json",
                "processes/supervisor.json", "processes/watchdog.json",
                "processes/capacity_watchdog.json", "processes/capacity_monitor.json"}
    require(required <= set(generations) and all(
        v.get("generation_absent") is True and v.get("actual_identity") is None
        and v.get("expected_identity", {}).get("start_ticks") for v in generations.values()),
        "All registered process generations must have exited")
    exit_check = originals[attempt + "HARDWARE_FAILURE_EXIT_CHECK.json"]
    checks = {x["file"].removeprefix(source["remote_root"] + "/"): x
              for x in exit_check["exact_process_checks"]}
    require(set(checks) == set(generations) and exit_check["all_recorded_generations_exited"] is True
            and exit_check["GPU6_CUDA_allocation_absent"] is None
            and "GPU requires reset" in exit_check["devices"]["6"]["health"],
            "Actual hardware/exit check missing")
    for name, generation in generations.items():
        check = checks[name]
        require(check["pid"] == generation["pid"] and check["expected_identity"] == generation["expected_identity"]
                and check["same_generation_alive"] is False and check["current_identity"] is None,
                "Process exit check differs from registered generation")
    for name, original in (("processes/service.json", owner),
                           ("audit/ATTEMPT1_LAUNCH.json", originals["audit/ATTEMPT1_LAUNCH.json"])):
        require(generations[name]["pid"] == original["pid"]
                and generations[name]["expected_identity"] == original["identity"], "Original generation differs")
    monitor = originals[attempt + "CAPACITY_MONITOR_EXIT.json"]
    gen = generations["processes/capacity_monitor.json"]
    require(monitor["exit_code"] == 0 and monitor["exact_generation_absent"] is True
            and monitor["pid"] == gen["pid"] and monitor["identity"] == gen["expected_identity"],
            "Capacity monitor release differs")
    failure, cleanup = originals[attempt + "FAILURE.json"], originals[attempt + "CLEANUP_FAILURE.json"]
    require(failure.get("error") and cleanup["primary"] == failure["error"]
            and owner["gpu_uuid"] in cleanup["cleanup"] and "[N/A]" in cleanup["cleanup"],
            "Hardware cleanup failure must remain explicit")
    rows = [[x.strip() for x in line.split(",")] for line in evidence["cuda_raw"].splitlines()]
    require([owner["gpu_uuid"], "[N/A]", "[N/A]"] in rows, "Unknown device telemetry missing")
    require(manifest["failure"]["failed_run"] == target["run_ids"][0]
            and manifest["failure"]["replay_from_original_noise"] is True
            and originals["logs/" + target["run_ids"][0] + "_job.json"]["status"] != "success",
            "Failed late may not count as an output")


def verify_composite_record(record, case, selected_binding=None, selected_run=None):
    if record.get("segment_count") == 3:
        from book_three_segment import verify_three_segment
        return verify_three_segment(record, case, selected_binding, selected_run)
    require(record.get("schema") == SCHEMA and record.get("passed") is True
            and record.get("source_id") == case["source_id"] == "long_0039"
            and record.get("same_persistent_service") is False
            and record.get("original_four_arm_COMPLETE") is False
            and set(record.get("job_gates", {})) == set(ARMS)
            and set(record.get("bindings", {})) == set(ARMS), "Explicit complete 1+3 evidence required")
    for item in evidence_records(record).values():
        verify_record(item)
    m, d, p = (read(record[k]["file"]) for k in ("migration", "deployment", "partial_release"))
    bindings = {a: read(record["bindings"][a]["file"]) for a in ARMS}
    runs = {a: read(record["job_gates"][a]["file"]) for a in ARMS}
    schedules = read(ROOT / "EVALUATION_MANIFEST.json")["schedules"]
    for arm in ARMS:
        validate_job(case, dict(schedules[arm], id=arm), bindings[arm], runs[arm])
    if selected_run is not None:
        role = selected_run["role"]
        require(runs[role] == selected_run and bindings[role] == selected_binding, "Presentation differs")
    validate_migration(m, d, record, case, bindings)
    old_owner, new_owner = m["segments"]["host41_prefix"]["service_owner"], runs["global_weak"]["service_owner"]
    require(runs["early"]["service_owner"] == old_owner and old_owner != new_owner
            and all(runs[a]["service_owner"] == new_owner for a in ARMS[1:]), "Segment owners differ")
    verify_prefix(m, d, p, record, bindings, runs)
    legacy.verify_target_segment(record, case, bindings, runs, m["segments"]["host41_recovery"],
                                 "book_late_split_global_host41", record["migration"]["sha256"])
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=["long_0039"])
    parser.add_argument("--prefix-evidence-dir", type=Path, required=True)
    for name in RECEIPTS:
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    a = parser.parse_args()
    case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"] if c["source_id"] == a.case)
    migration = read(a.migration)
    record = dict(schema=SCHEMA, passed=True, source_id=a.case, same_persistent_service=False,
                  original_four_arm_COMPLETE=False,
                  **{n: bound(getattr(a, n)) for n in RECEIPTS},
                  partial_artifacts={"source_evidence": bound(a.prefix_evidence_dir / "SOURCE_EVIDENCE.json"),
                                    **{n: bound(a.prefix_evidence_dir / n)
                                       for n in migration["failure"]["source_evidence"]}},
                  bindings={arm: bound(ROOT / "runtime" / a.case / (arm + ".json")) for arm in ARMS},
                  job_gates={arm: bound(ROOT / "actual" / a.case / arm / "GATE.json") for arm in ARMS})
    verify_composite_record(record, case)
    for arm in ARMS:
        path = ROOT / "review" / a.case / arm / "PRESENTATION.json"
        if path.exists():
            proof = read(path)["validated_execution"]
            require(proof["run_record"] == read(record["job_gates"][arm]["file"])
                    and proof["binding"] == record["bindings"][arm],
                    "Rendered media belongs to another per-job record or binding")
    path = ROOT / "actual" / a.case / "BATCH_RELEASE.json"
    require(not path.exists() or read(path) == record, "Existing release may not be replaced")
    write(path, record)
    print(path)


if __name__ == "__main__":
    main()
