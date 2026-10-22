"""R150 manifests over the unchanged, hash-pinned R149 official MF packager."""
import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVAL = ROOT.parent
OLD = EVAL.with_name("h3-guidance-schedule-eval-r149-20261020")
sys.dont_write_bytecode = True
sys.path[:0] = [str(EVAL), str(OLD)]
import common
import ingest
import finalize_composite
import finalize_batch
from common import bound, read, require, verify_record

PINS = read(ROOT / "REUSE.json")
for item in PINS["helpers"]:
    verify_record(item)
require(common.ROOT == EVAL and ingest.ROOT == EVAL
        and finalize_composite.ROOT == EVAL and finalize_batch.ROOT == EVAL,
        "Evaluation modules must use R150")

spec = importlib.util.spec_from_file_location("r149_official_mf_packager", OLD / "mf_preparation/prepare_batch.py")
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)
packager.ROOT = ROOT
packager.EVAL = EVAL
packager.REMOTE = "/data4/researcher/h3_runs/guidance_schedule_mf_r150_20261021"
original_attach_source = packager.attach_source


def read_historical(path):
    result = read(path)
    for mapping in PINS["source_media"].values():
        proof_record = mapping.get("legacy_crop_proof")
        if not proof_record:
            continue
        verify_record(proof_record)
        proof = read(proof_record["file"])
        if str(Path(path).resolve()) == proof["historical_inputs"]["file"]:
            verify_record(proof["historical_inputs"])
            require(proof["passed"] and proof["decoded_crop_equals_cached_score"]
                    and "crop_xywh" not in result, "Legacy crop proof differs")
            result["crop_xywh"] = proof["crop_xywh"]
    return result


packager.read = read_historical


def attach_source(case, package, reuse):
    # Original checks still bind pixels, geometry, selection, checkpoint and tracks.
    result = original_attach_source(case, package, reuse)
    mapping = PINS["source_media"][case["source_id"]]
    verify_record(mapping["historical_runtime"])
    runtime = read(mapping["historical_runtime"]["file"])
    for filename, key in (("source_full.mp4", "source_full_sha256"),
                          ("source_score.mp4", "source_score_sha256")):
        target = f"cases/{case['source_id']}/{filename}"
        item = mapping[filename]
        require(item["sha256"] == result[key]
                and item["file"] == runtime["remote_root"] + "/" + item["relative_file"],
                "Existing remote source media mapping differs")
        reuse[target] = item["file"]
    return result


packager.attach_source = attach_source


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=tuple(PINS["source_media"]))
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--gpu")
    parser.add_argument("--peer-root", action="append", default=[])
    parser.add_argument("--existing-services", type=Path)
    parser.add_argument("--remote-full-map", type=Path)
    args = parser.parse_args()
    packager.prepare(args.case, args.finalize, args.gpu, args.peer_root,
                     args.existing_services, args.remote_full_map)
