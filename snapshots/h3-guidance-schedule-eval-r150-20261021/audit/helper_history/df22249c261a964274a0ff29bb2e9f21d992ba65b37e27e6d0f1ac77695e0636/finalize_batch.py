"""Add actual batch completion/release evidence without re-rendering any media."""
import argparse
from pathlib import Path
from common import ROOT, bound, read, write, require, case_and_schedule, verify_record
from ingest import validate_batch, validate_job


def verify_batch_record(path, case, binding, run):
    record = read(path)
    if record.get("schema") == "r149-evaluation-composite-release-v1":
        from finalize_composite import verify_composite_record
        return verify_composite_record(record, case, binding, run)
    for name in ("gate", "complete", "release"):
        verify_record(record[name])
    validate_batch(case, binding, run, read(record["gate"]["file"]),
                   read(record["complete"]["file"]), read(record["release"]["file"]),
                   record["gate"]["sha256"])
    return record


def batch_evidence_records(record):
    if record.get("schema") == "r149-evaluation-composite-release-v1":
        from finalize_composite import evidence_records
        return evidence_records(record)
    return {name: record[name] for name in ("gate", "complete", "release")}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    for name in ("gate", "complete", "release"):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    gate, complete, release = (read(a.gate), read(a.complete), read(a.release))
    record = {"schema": "r149-evaluation-batch-release-v1", "passed": True,
              "gate": bound(a.gate), "complete": bound(a.complete), "release": bound(a.release)}
    _, case, _ = case_and_schedule(a.case, "early")
    for arm in case.get("expected_output_roles", ("early", "late", "split", "global_weak")):
        _, case, schedule = case_and_schedule(a.case, arm)
        binding = read(ROOT / "runtime" / a.case / (arm + ".json"))
        run = gate["runs"][arm]
        validate_job(case, dict(schedule, id=arm), binding, run)
        validate_batch(case, binding, run, gate, complete, release, record["gate"]["sha256"])
        pres_path = ROOT / "review" / a.case / arm / "PRESENTATION.json"
        if pres_path.exists():
            require(read(pres_path)["validated_execution"]["run_record"] == run,
                    "Rendered media belongs to another per-job record")
    path = ROOT / "actual" / a.case / "BATCH_RELEASE.json"
    if path.exists():
        require(read(path) == record, "Conflicting batch release")
    write(path, record)
    print(str(path))


if __name__ == "__main__":
    main()
