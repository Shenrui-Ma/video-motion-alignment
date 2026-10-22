"""Local CPU helpers; no producer mutation, network or GPU entry points."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PREVIOUS = ROOT.parent / "h3-timing-phase-combined-eval-r148-20261020"
spec = importlib.util.spec_from_file_location("r148_media_helpers", PREVIOUS / "prepare_comparison.py")
legacy = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(legacy)
bound, read, require = legacy.bound, legacy.read, legacy.require
inspect, dimensions = legacy.inspect, legacy.dimensions
FFMPEG, FONT = legacy.FFMPEG, legacy.FONT


def write(path, value):
    path = Path(path).resolve()
    require(path.is_relative_to(ROOT), "Writes are restricted to the R150 evaluation directory")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def case_and_schedule(sid, schedule):
    manifest = read(ROOT / "EVALUATION_MANIFEST.json")
    case = next(c for c in manifest["cases"] if c["source_id"] == sid)
    labels = read(ROOT / "EVENT_DISPLAY_LABELS.json")["cases"].get(sid, {})
    for event in case["events"]:
        event["label"] = labels.get(event["id"], event["label"])
    return manifest, resolve_controls(case), schedule_spec(manifest, schedule)


def schedule_spec(manifest, role):
    if role == "native":
        return {"id": role, "label": "普通编辑", "steps_0based": []}
    if role == "fixed":
        return {"id": role, "label": "7–15", "steps_0based": list(range(6, 15))}
    return dict(manifest["schedules"][role], id=role)


def resolve_controls(case):
    """Resolve only explicitly validated new controls; never fall back to old weight3/cache."""
    import copy
    result = copy.deepcopy(case)
    for role in case.get("new_control_roles", []):
        path = ROOT / "actual" / case["source_id"] / role / "CONTROL.json"
        if not path.exists():
            continue
        control = read(path)
        for key in ("gate", "binding", "video"):
            verify_record(control[key])
        binding, gate = read(control["binding"]["file"]), read(control["gate"]["file"])
        from ingest import validate_job
        validate_job(case, schedule_spec({}, role), binding, gate)
        require(control["role"] == role and control["run_id"] == binding["run_id"] and
                control["video"]["sha256"] == gate["video"]["sha256"],
                "New control does not bind its actual run/video")
        result["media"][role] = control["video"]
        review_path = ROOT / "review" / case["source_id"] / role / "REVIEW.json"
        if review_path.exists():
            review = read(review_path)
            require(review["actual_video"] == control["video"], "Control review video differs")
            if review.get("review_completed"):
                by_id = {x["id"]: x for x in review["events"]}
                for event in result["events"]:
                    event[role] = by_id[event["id"]].get(role)
    return result


def verify_record(record):
    require(bound(record["file"])["sha256"] == record["sha256"],
            "File SHA changed: " + record["file"])


def prompt_sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def expected_router(case, schedule):
    result = dict(case["invariant_router"])
    if schedule["id"] == "global_weak":
        result.update(alpha=0.25, start_frame=0, end_frame=case["geometry"]["valid_frames"] - 1)
    return result
