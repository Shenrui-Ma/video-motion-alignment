"""Firefly's completed Native plus five separately completed guidance outputs."""
import argparse
from pathlib import Path

from common import ROOT, bound, read, write, require, verify_record, schedule_spec
from ingest import validate_job
from finalize_parallel import validate_segment

SCHEMA = "r150-evaluation-native-recovery-release-v1"
ROLES = ("native", "fixed", "early", "late", "split", "global_weak")
PARTITION = {"prefix": ["native"], "recovery": list(ROLES[1:])}


def evidence_records(record):
    result = {k: record[k] for k in
              ("migration", "deployment", "partial_release", "source_evidence",
               "gate", "complete", "release")}
    for category in ("bindings", "job_gates", "prefix_artifacts"):
        result.update({category + "/" + k: v for k, v in record[category].items()})
    return result


def validate_binding_set(manifest, deployment, record, case, bindings):
    require(case["source_id"] == manifest.get("source_id") ==
            deployment.get("source_id") == "firefly06"
            and manifest.get("schema") == "r150-completed-native-recovery-v1"
            and manifest.get("stop_kind") == "administrative_idle_review_expired"
            and deployment.get("schema") == "r150-completed-native-recovery-deployment-v1"
            and deployment.get("migration_manifest_sha256") == record["migration"]["sha256"]
            and deployment.get("prefix_partial_release_sha256") ==
            record["partial_release"]["sha256"]
            and manifest.get("original_six_role_COMPLETE_absent") is True,
            "Explicit completed-Native recovery lineage required")
    require(set(manifest["segments"]) == set(deployment["segments"]) == set(PARTITION)
            and set(bindings) == set(ROLES) == set(case["expected_output_roles"]),
            "Six unique roles must be covered")
    science = manifest["science"]
    require(science["noise_file_sha256"] == case["historical_initial_noise"]["sha256"],
            "Original noise differs")
    for name, roles in PARTITION.items():
        segment, deployed = manifest["segments"][name], deployment["segments"][name]
        require(segment["roles"] == deployed["roles"] == roles
                and segment["run_ids"] == deployed["run_ids"] ==
                [bindings[r]["run_id"] for r in roles], "Segment partition differs")
        for role in roles:
            binding = bindings[role]
            require(binding["host"] == segment["host"] == deployed["host"]
                    and binding["remote_root"] == segment["remote_root"] == deployed["remote_root"]
                    and binding["producer_seal"]["sha256"] == deployed["producer_seal_sha256"]
                    and binding["scientific_contract"]["sha256"] == science["scientific_contract_sha256"]
                    and binding["graph"]["sha256"] == science[
                        "source_graph_sha256" if name == "prefix" else "target_graph_sha256"][role],
                    "Actual producer binding differs")
            root = Path(binding["producer_seal"]["file"]).parent
            seal = read(binding["producer_seal"]["file"])["files"]
            require(bound(root / "configs/CONDITION_CACHE.json")["sha256"] ==
                    seal["configs/CONDITION_CACHE.json"]["sha256"] == science["condition_cache_sha256"],
                    "Shared condition cache differs")
            if name == "recovery":
                require(binding["migration_manifest"] == record["migration"]
                        and binding["migration_deployment"] == record["deployment"]
                        and binding["execution_segment_id"] == segment["segment_id"]
                        and seal["configs/MIGRATION_MANIFEST.json"]["sha256"] ==
                        record["migration"]["sha256"], "Recovery migration not sealed")


def validate_prefix(manifest, deployment, partial, evidence, record, native):
    prefix, recovery = manifest["segments"]["prefix"], manifest["segments"]["recovery"]
    owner = prefix["service_owner"]
    require(partial.get("schema") == "r150-native-partial-release-v1"
            and partial.get("passed") is True and partial.get("source_id") == "firefly06"
            and partial.get("stop_kind") == manifest["stop_kind"]
            and partial.get("source_root") == prefix["remote_root"]
            and partial.get("producer_seal_sha256") == prefix["producer_seal_sha256"]
            and partial.get("migration_manifest_sha256") == record["migration"]["sha256"]
            and partial.get("completed_roles") == ["native"]
            and partial.get("completed_runs") == prefix["run_ids"]
            and partial.get("remaining_runs") == recovery["run_ids"]
            and partial.get("service_owner") == owner == native["service_owner"]
            and partial.get("original_full_COMPLETE") is False
            and partial.get("exact_generations_absent") is True
            and partial.get("CUDA_allocation_absent") is True
            and partial.get("native_visual_review_passed") is True,
            "Native partial release must remain one output with exact release")
    expected = manifest["source_evidence"]
    require(partial["source_evidence"] == expected
            and set(evidence["files"]) == set(expected) == set(record["prefix_artifacts"])
            and evidence["owner"] == owner and evidence["exact_generations_absent"] is True
            and evidence["CUDA_allocation_absent"] is True,
            "Original source evidence differs")
    originals = {}
    for relative, ref in expected.items():
        item, embedded = record["prefix_artifacts"][relative], evidence["files"][relative]
        verify_record(item)
        require(item["sha256"] == ref["sha256"] == embedded["sha256"]
                and ref["path"] == embedded["path"] == prefix["remote_root"] + "/" + relative
                and read(item["file"]) == embedded["content"], "Original evidence bytes differ")
        originals[relative] = embedded["content"]
    gate_path = record["bindings"]["native"]
    gate_path = read(gate_path["file"])["gate_relative_file"]
    require(originals[gate_path] == native
            and expected[gate_path]["sha256"] == record["job_gates"]["native"]["sha256"]
            and expected["deploy_manifest.json"]["sha256"] == prefix["producer_seal_sha256"]
            and originals["processes/service.json"] == owner, "Native actual job differs")
    cleanup = originals["processes/cleanup.json"]
    require(cleanup["pid"] == owner["pid"] and cleanup["service_record"] == owner
            and all(cleanup.get(k) is True for k in
                    ("process_absent", "own_compute_absent", "child_compute_absent")),
            "Original service/CUDA release missing")
    review = originals["audit/NATIVE_VISUAL_REVIEW.json"]
    request = originals["audit/NATIVE_VISUAL_REVIEW_REQUEST.json"]
    require(review.get("passed") is True and review.get("task_completed") is True
            and all(review[k] == request[k] == value for k, value in {
                "source_id": "firefly06", "run_id": native["run_id"],
                "native_gate_sha256": record["job_gates"]["native"]["sha256"],
                "video_sha256": native["video"]["sha256"],
                "producer_seal_sha256": native["producer_seal_sha256"]}.items()),
            "Native task review belongs to another output")
    stop = originals["audit/watchdog_runtime_v2/STOP_REASON.json"]
    require(stop["owner"] == owner and stop["reason"] == "bounded_idle_review_expired"
            and originals["audit/" + prefix["attempt"] + "/FAILURE.json"].get("error"),
            "Actual administrative termination must remain recorded")


def verify_native_recovery_record(record, case, selected_binding=None, selected_run=None):
    require(record.get("schema") == SCHEMA and record.get("passed") is True
            and record.get("source_id") == "firefly06"
            and record.get("same_persistent_service") is False
            and record.get("original_full_COMPLETE") is False
            and set(record["bindings"]) == set(record["job_gates"]) == set(ROLES),
            "Complete six-output composite required")
    for item in evidence_records(record).values():
        verify_record(item)
    m, d, p, e = (read(record[k]["file"]) for k in
                  ("migration", "deployment", "partial_release", "source_evidence"))
    bindings = {r: read(record["bindings"][r]["file"]) for r in ROLES}
    runs = {r: read(record["job_gates"][r]["file"]) for r in ROLES}
    validate_binding_set(m, d, record, case, bindings)
    evaluation = read(ROOT / "EVALUATION_MANIFEST.json")
    for role in ROLES:
        validate_job(case, schedule_spec(evaluation, role), bindings[role], runs[role])
    validate_prefix(m, d, p, e, record, runs["native"])
    owner = validate_segment(m["segments"]["recovery"], d["segments"]["recovery"], runs,
                             *(read(record[k]["file"]) for k in ("gate", "complete", "release")),
                             record["gate"]["sha256"], record["migration"]["sha256"],
                             source_id="firefly06")
    require(owner != runs["native"]["service_owner"], "Recovery must have its own actual owner")
    if selected_run is not None:
        role = selected_run["role"]
        require(runs[role] == selected_run and bindings[role] == selected_binding,
                "Presentation differs from completed composite")
    return record


def main():
    parser = argparse.ArgumentParser()
    for key in ("migration", "deployment", "partial_release", "source_evidence",
                "prefix_evidence_dir", "gate", "complete", "release"):
        parser.add_argument("--" + key.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]
                if c["source_id"] == "firefly06")
    manifest = read(args.migration)
    record = {"schema": SCHEMA, "passed": True, "source_id": "firefly06",
              "same_persistent_service": False, "original_full_COMPLETE": False,
              **{k: bound(getattr(args, k)) for k in
                 ("migration", "deployment", "partial_release", "source_evidence",
                  "gate", "complete", "release")},
              "prefix_artifacts": {k: bound(args.prefix_evidence_dir / k)
                                   for k in manifest["source_evidence"]},
              "bindings": {r: bound(ROOT / "runtime/firefly06" / (r + ".json")) for r in ROLES},
              "job_gates": {r: bound(ROOT / "actual/firefly06" / r / "GATE.json") for r in ROLES}}
    verify_native_recovery_record(record, case)
    for role in ROLES:
        p = ROOT / "review/firefly06" / role / "PRESENTATION.json"
        if p.exists():
            proof = read(p)["validated_execution"]
            require(proof["binding"] == record["bindings"][role]
                    and proof["gate"] == record["job_gates"][role], "Rendered output differs")
    output = ROOT / "actual/firefly06/BATCH_RELEASE.json"
    require(not output.exists() or read(output) == record, "Preserve previous release")
    write(output, record)
    print(output)


if __name__ == "__main__":
    main()
