"""The drinking GPU5 failure is process-released, with GPU allocation unqueryable."""
from common import read, require


def hardware_files(manifest):
    """Keep every source evidence file, including the failed split audit."""
    return {"source_evidence": "SOURCE_EVIDENCE.json",
            **{path: path for path in manifest["failure"]["source_evidence"]}}


def verify_hardware_prefix(manifest, deployment, partial, record, bindings, runs):
    source = manifest["segments"]["host41_prefix"]
    target = manifest["segments"]["host41_recovery"]
    owner = source["service_owner"]
    require(partial.get("schema") == "r149-schedule-hardware-partial-release-v1"
            and partial.get("passed") is True and partial.get("source_id") == "short_0358"
            and partial.get("segment_id") == "host41_prefix"
            and partial.get("stop_kind") == "hardware_failure"
            and partial.get("source_root") == source["remote_root"]
            and partial.get("service_owner") == owner
            and partial.get("producer_seal_sha256") == source["producer_seal_sha256"]
            and partial.get("completed_roles") == source["roles"] == ["early", "late"]
            and partial.get("completed_runs") == source["run_ids"]
            and partial.get("remaining_runs") == target["run_ids"]
            and partial.get("migration_manifest_sha256") == record["migration"]["sha256"]
            and partial.get("original_four_arm_COMPLETE") is False
            and partial.get("process_generation_absent") is True,
            "Hardware prefix role/owner/manifest/process evidence differs")
    require("CUDA_allocation_absent" in partial and partial["CUDA_allocation_absent"] is None
            and partial.get("release_state") == "processes_exited_gpu_unqueryable"
            and partial.get("gpu_health") == "requires_reset"
            and partial.get("gpu_uuid") == owner["gpu_uuid"],
            "Hardware prefix must retain unknown CUDA state; no successful GPU cleanup claim")
    require(deployment.get("prefix_partial_release_sha256") == record["partial_release"]["sha256"],
            "Deployment binds another hardware prefix release")

    evidence = read(record["partial_artifacts"]["source_evidence"]["file"])
    expected = manifest["failure"]["source_evidence"]
    require(partial.get("evidence") == expected and set(evidence.get("files", {})) == set(expected)
            and evidence.get("owner") == owner and evidence.get("boot_id") == source["boot_id"]
            and evidence.get("generations") == partial.get("registered_generations")
            and evidence.get("cuda_raw") == partial.get("raw_compute_telemetry")
            and evidence.get("observed_unix") == partial.get("created_unix"),
            "Hardware evidence snapshot differs")
    originals = {}
    for relative, item in expected.items():
        local = record["partial_artifacts"][relative]
        original = evidence["files"][relative]
        require(item["path"] == source["remote_root"] + "/" + relative
                and item["sha256"] == local["sha256"]
                and original["path"] == item["path"] and original["sha256"] == item["sha256"]
                and original["content"] == read(local["file"]),
                "Hardware evidence does not match its original file: " + relative)
        originals[relative] = original["content"]
    attempt = "audit/" + source["attempt"] + "/"
    required = {"deploy_manifest.json", "processes/service.json", "audit/ATTEMPT1_LAUNCH.json",
                attempt + "FAILURE.json", attempt + "CLEANUP_FAILURE.json",
                attempt + "GPU5_FAILURE_DIAGNOSIS.json", attempt + "CAPACITY_MONITOR_EXIT.json",
                "logs/" + target["run_ids"][0] + "_job.json",
                "audit/router/" + target["run_ids"][0] + ".json",
                *[bindings[arm]["gate_relative_file"] for arm in source["roles"]]}
    require(set(originals) == required, "Hardware source evidence set incomplete")
    require(expected["deploy_manifest.json"]["sha256"] == source["producer_seal_sha256"]
            and originals["processes/service.json"] == owner, "Source seal/owner evidence differs")
    require(set(partial.get("gates", {})) == set(source["run_ids"]),
            "Hardware prefix must contain exactly the two completed jobs")
    for arm in source["roles"]:
        original = originals[bindings[arm]["gate_relative_file"]]
        receipt = partial["gates"][runs[arm]["run_id"]]
        require(original == runs[arm] and
                receipt["sha256"] == record["job_gates"][arm]["sha256"] and
                receipt["path"] == bindings[arm]["remote_root"] + "/" + bindings[arm]["gate_relative_file"],
                "Hardware prefix completed gate differs")

    generations = partial["registered_generations"]
    names = {"root_wrapper", "service", "controller", "supervisor", "watchdog",
             "capacity_watchdog", "capacity_monitor"}
    require(set(generations) == names and
            all(g.get("generation_absent") is True and g.get("actual_identity") is None
                and isinstance(g.get("pid"), int) and g.get("expected_identity", {}).get("start_ticks")
                for g in generations.values()), "Exact old process generations are not all absent")
    launch = originals["audit/ATTEMPT1_LAUNCH.json"]
    for name, process in (("service", owner), ("root_wrapper", launch)):
        require(generations[name]["pid"] == process["pid"] and
                generations[name]["expected_identity"] == process["identity"],
                "Hardware release uses another registered process generation")
    monitor = originals[attempt + "CAPACITY_MONITOR_EXIT.json"]
    require(monitor.get("exit_code") == 0 and monitor.get("exact_generation_absent") is True
            and monitor.get("pid") == generations["capacity_monitor"]["pid"]
            and monitor.get("identity") == generations["capacity_monitor"]["expected_identity"],
            "Capacity monitor exact release differs")
    failure = originals[attempt + "FAILURE.json"]
    cleanup_failure = originals[attempt + "CLEANUP_FAILURE.json"]
    diagnosis = originals[attempt + "GPU5_FAILURE_DIAGNOSIS.json"]
    require(failure.get("error") and cleanup_failure.get("primary") == failure["error"]
            and owner["gpu_uuid"] in cleanup_failure.get("cleanup", "")
            and "[N/A]" in cleanup_failure["cleanup"]
            and diagnosis.get("gpu5_health", {}).get("returncode") == 0
            and "GPU requires reset" in diagnosis["gpu5_health"].get("stdout", "")
            and diagnosis.get("pids", {}).get(str(owner["pid"])) is False
            and diagnosis["pids"].get(str(launch["pid"])) is False,
            "Original hardware failure and cleanup failure must remain explicit")
    rows = [list(map(str.strip, line.split(","))) for line in evidence["cuda_raw"].splitlines()]
    require([owner["gpu_uuid"], "[N/A]", "[N/A]"] in rows,
            "Original unqueryable GPU telemetry missing")
    require(manifest["failure"]["failed_run"] == target["run_ids"][0]
            and manifest["failure"]["replay_from_original_noise"] is True
            and originals["logs/" + target["run_ids"][0] + "_job.json"].get("status") != "success",
            "Failed split must remain failed and restart from the original noise")
