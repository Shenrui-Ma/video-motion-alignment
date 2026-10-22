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
    return manifest, case, manifest["schedules"][schedule]


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
