"""Combine Sam07's two normally completed service segments into six outputs."""
import argparse
from pathlib import Path
from common import ROOT, bound, read, write, require, verify_record, schedule_spec
from ingest import validate_job

SCHEMA = "r150-evaluation-parallel-segment-release-v1"
PARTITION = {"prefix": ("native", "fixed", "early", "late"),
             "tail": ("split", "global_weak")}
ROLES = tuple(role for roles in PARTITION.values() for role in roles)
REBIND_SCHEMA = "r150-planned-parallel-tail-rebinding-v1"


def evidence_records(record):
    records = {key: record[key] for key in ("migration", "deployment")}
    records.update({key: record[key] for key in ("base_migration", "base_deployment")
                    if key in record})
    for category in ("bindings", "job_gates"):
        records.update({category + "/" + key: value for key, value in record[category].items()})
    for segment, receipts in record["segments"].items():
        records.update({segment + "/" + key: value for key, value in receipts.items()})
    return records


def segment_evidence(record, name):
    """An already running prefix remains bound to its original frozen manifest."""
    prefix = "base_" if name == "prefix" and "base_migration" in record else ""
    return record[prefix + "migration"], record[prefix + "deployment"]


def validate_partition(manifest, deployment, record, case, bindings):
    rebound = manifest.get("schema") == REBIND_SCHEMA
    require(case["source_id"] == manifest.get("source_id") == deployment.get("source_id") == "sam07"
            and manifest.get("schema") in {"r150-planned-parallel-segments-v1", REBIND_SCHEMA}
            and deployment.get("schema") == (
                "r150-planned-parallel-tail-rebinding-deployment-v1" if rebound else
                "r150-planned-parallel-deployment-v1")
            and deployment.get("migration_manifest_sha256") == record["migration"]["sha256"],
            "Actual planned Sam07 partition required")
    require(("base_migration" in record) == ("base_deployment" in record) == rebound,
            "Rebound tail requires both original frozen partition records")
    if rebound:
        for key in ("base_migration", "base_deployment"):
            verify_record(record[key])
        base = read(record["base_migration"]["file"])
        base_deployment = read(record["base_deployment"]["file"])
        require(base.get("schema") == "r150-planned-parallel-segments-v1"
                and base_deployment.get("schema") == "r150-planned-parallel-deployment-v1"
                and base.get("source_id") == base_deployment.get("source_id") == "sam07"
                and manifest["base_migration_manifest_sha256"] ==
                manifest["prefix_bound_manifest_sha256"] ==
                base_deployment["migration_manifest_sha256"] == record["base_migration"]["sha256"]
                and manifest["base_migration_deployment_sha256"] == record["base_deployment"]["sha256"]
                and manifest["segments"]["prefix"] == base["segments"]["prefix"]
                and deployment["segments"]["prefix"] == base_deployment["segments"]["prefix"]
                and manifest["prefix_producer_seal_sha256"] ==
                base_deployment["segments"]["prefix"]["producer_seal_sha256"]
                and manifest["replaces_unstarted_tail"] == base_deployment["segments"]["tail"]
                and manifest["all_roles"] == base["all_roles"]
                and manifest["all_run_ids"] == base["all_run_ids"],
                "Tail reassignment may not rewrite the running prefix or original partition")
        for key in ("scientific_contract_sha256", "condition_cache_sha256",
                    "condition_description_sha256", "noise_file_sha256",
                    "native_run_id", "source_graph_sha256"):
            require(manifest["science"][key] == base["science"][key],
                    "Rebound tail changed shared scientific inputs")
    require(set(manifest["segments"]) == set(deployment["segments"]) == set(PARTITION)
            and manifest["all_roles"] == case["expected_output_roles"] == list(ROLES)
            and manifest["all_run_ids"] == [bindings[r]["run_id"] for r in ROLES],
            "All six roles must be covered exactly once")
    science = manifest["science"]
    require(science["condition_description_sha256"] == case["conditioning_sha256"]
            and science["noise_file_sha256"] == case["historical_initial_noise"]["sha256"],
            "Shared Native/noise condition differs")
    for name, roles in PARTITION.items():
        segment, deployed = manifest["segments"][name], deployment["segments"][name]
        migration_ref, deployment_ref = segment_evidence(record, name)
        science_prefix = "tail_" if rebound and name == "tail" else ""
        require(segment["roles"] == list(roles)
                and {k: v for k, v in deployed.items() if k != "producer_seal_sha256"} == segment
                and segment["run_ids"] == [bindings[r]["run_id"] for r in roles],
                "Segment roles or run IDs differ")
        for role in roles:
            binding = bindings[role]
            require(binding["host"] == segment["host"]
                    and binding["remote_root"] == segment["remote_root"]
                    and binding["gpu_index"] == segment["gpu_index"]
                    and binding["execution_segment_id"] == segment["segment_id"]
                    and binding["producer_seal"]["sha256"] == deployed["producer_seal_sha256"]
                    and binding["migration_manifest"] == migration_ref
                    and binding["migration_deployment"] == deployment_ref
                    and binding["scientific_contract"]["sha256"] ==
                    science[science_prefix + "scientific_contract_sha256"], "Segment binding differs")
            graph_key = "source_graph_sha256" if name == "prefix" else "tail_graph_sha256"
            require(binding["graph"]["sha256"] == science[graph_key][role], "Actual graph differs")
            root = Path(binding["producer_seal"]["file"]).parent
            seal = read(binding["producer_seal"]["file"])["files"]
            for relative, digest in (
                    ("configs/MIGRATION_MANIFEST.json", migration_ref["sha256"]),
                    ("configs/CONDITION_CACHE.json", science[science_prefix + "condition_cache_sha256"])):
                require(seal[relative]["sha256"] == bound(root / relative)["sha256"] == digest,
                        "Segment seal does not bind the same migration/cache")
            if rebound:
                cache = read(root / "configs/CONDITION_CACHE.json")
                require(cache["conditioning"]["sha256"] == science["condition_description_sha256"]
                        and [t["sha256"] for t in cache["tensors"]] == science["tensor_sha256"],
                        "Rebound host must reuse the same actual condition tensors")


def validate_segment(segment, deployed, runs, gate, complete, release, gate_sha, migration_sha,
                     source_id="sam07"):
    roles = segment["roles"]
    owner = runs[roles[0]]["service_owner"]
    require(gate.get("schema") == segment["aggregate_schema"] ==
            "r149-fixed-schedule-segment-gate-v1" and gate.get("passed") is True
            and gate.get("source_id") == source_id
            and gate.get("segment_id") == segment["segment_id"]
            and gate.get("migration_manifest_sha256") == migration_sha
            and gate.get("producer_seal_sha256") == deployed["producer_seal_sha256"]
            and gate.get("phase_displacement") == 0
            and gate.get("same_persistent_service") is True
            and gate.get("service_owner") == owner
            and gate.get("runs") == {r: runs[r] for r in roles}
            and all(runs[r]["service_owner"] == owner for r in roles),
            "Segment gate must bind its own exact role set and service")
    require(complete.get("schema") == segment["COMPLETE_schema"] ==
            "r149-schedule-segment-completion-v1" and complete.get("passed") is True
            and complete.get("segment_id") == segment["segment_id"]
            and complete.get("migration_manifest_sha256") == migration_sha
            and complete.get("jobs") == segment["run_ids"] and complete.get("remaining") == []
            and complete.get("GPU_released") is True
            and complete.get("runtime_gate_sha256") == gate_sha
            and complete.get("service_owner") == owner,
            "Segment COMPLETE differs from actual jobs/gate/owner")
    cleanup = release.get("cleanup", {})
    require(release.get("passed") is True and release.get("owner") == owner
            and release.get("process_absent") is True
            and release.get("CUDA_allocation_absent") is True
            and cleanup.get("pid") == owner["pid"]
            and cleanup.get("process_absent") is True
            and cleanup.get("own_compute_absent") is True,
            "Segment service must be exactly released")
    return owner


def verify_parallel_record(record, case, selected_binding=None, selected_run=None):
    require(record.get("schema") == SCHEMA and record.get("passed") is True
            and record.get("source_id") == "sam07"
            and record.get("same_persistent_service") is False
            and record.get("segment_count") == 2
            and set(record.get("segments", {})) == set(PARTITION)
            and set(record.get("bindings", {})) == set(record.get("job_gates", {})) == set(ROLES),
            "Two real segment completions and all six unique jobs are required")
    for item in evidence_records(record).values():
        verify_record(item)
    manifest, deployment = (read(record[k]["file"]) for k in ("migration", "deployment"))
    bindings = {r: read(record["bindings"][r]["file"]) for r in ROLES}
    runs = {r: read(record["job_gates"][r]["file"]) for r in ROLES}
    validate_partition(manifest, deployment, record, case, bindings)
    evaluation = read(ROOT / "EVALUATION_MANIFEST.json")
    for role in ROLES:
        validate_job(case, schedule_spec(evaluation, role), bindings[role], runs[role])
    owners = []
    for name in PARTITION:
        receipts = record["segments"][name]
        require(set(receipts) == {"gate", "complete", "release"}, "Missing segment evidence")
        owners.append(validate_segment(
            manifest["segments"][name], deployment["segments"][name], runs,
            *(read(receipts[k]["file"]) for k in ("gate", "complete", "release")),
            receipts["gate"]["sha256"], segment_evidence(record, name)[0]["sha256"]))
    require(owners[0] != owners[1] and owners[0]["gpu_uuid"] != owners[1]["gpu_uuid"],
            "Planned separate GPU services may not be presented as one owner")
    if selected_run is not None:
        role = selected_run["role"]
        require(runs[role] == selected_run and bindings[role] == selected_binding,
                "Presentation differs from completed segment")
    return record


def main():
    parser = argparse.ArgumentParser()
    for name in ("migration", "deployment"):
        parser.add_argument("--" + name, required=True, type=Path)
        parser.add_argument("--base-" + name, type=Path)
    for segment in PARTITION:
        for receipt in ("gate", "complete", "release"):
            parser.add_argument("--" + segment + "-" + receipt, required=True, type=Path)
    args = parser.parse_args()
    case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]
                if c["source_id"] == "sam07")
    record = {"schema": SCHEMA, "passed": True, "source_id": "sam07",
              "same_persistent_service": False, "segment_count": 2,
              "migration": bound(args.migration), "deployment": bound(args.deployment),
              "bindings": {r: bound(ROOT / "runtime/sam07" / (r + ".json")) for r in ROLES},
              "job_gates": {r: bound(ROOT / "actual/sam07" / r / "GATE.json") for r in ROLES},
              "segments": {s: {k: bound(getattr(args, s + "_" + k))
                               for k in ("gate", "complete", "release")} for s in PARTITION}}
    for key in ("base_migration", "base_deployment"):
        if getattr(args, key):
            record[key] = bound(getattr(args, key))
    verify_parallel_record(record, case)
    for role in ROLES:
        path = ROOT / "review/sam07" / role / "PRESENTATION.json"
        if path.exists():
            proof = read(path)["validated_execution"]
            require(proof["binding"] == record["bindings"][role]
                    and proof["gate"] == record["job_gates"][role],
                    "Existing rendered media must use these exact bindings")
    output = ROOT / "actual/sam07/BATCH_RELEASE.json"
    require(not output.exists() or read(output) == record, "Preserve prior complete release")
    write(output, record)
    print(output)


if __name__ == "__main__":
    main()
