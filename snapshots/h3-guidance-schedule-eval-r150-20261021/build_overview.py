"""Reuse the seven-column renderer with frozen source-derived representative frames."""
import argparse
import importlib.util
import sys
from common import ROOT, bound, read, require, verify_record, resolve_controls

OLD = ROOT.with_name("h3-guidance-schedule-eval-r149-20261020")
PINS = read(ROOT / "OVERVIEW_FRAME_PLAN.json")
verify_record(PINS["renderer"])
verify_record(PINS["events"])
spec = importlib.util.spec_from_file_location("r149_seven_column_renderer", OLD / "build_overview.py")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
require(renderer.ROOT == ROOT, "Renderer write scope differs")


def read_with_frame_plan(path):
    value = read(path)
    if str(path) == str(ROOT / "EVALUATION_PLAN.json"):
        for case in value["cases"]:
            case["representative_frames"] = PINS["cases"][case["source_id"]]["frames"]
    return value


renderer.read = read_with_frame_plan


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    args = parser.parse_args()
    for case in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]:
        if args.case is None or case["source_id"] == args.case:
            print(renderer.render(resolve_controls(case)) or f"{case['source_id']}: waiting for completed outputs")
