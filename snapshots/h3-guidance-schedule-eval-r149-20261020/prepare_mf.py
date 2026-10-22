"""Make only completed targets' lossless score views; never load a model or launch."""
import argparse
import importlib.util
from pathlib import Path
from common import ROOT, PREVIOUS, bound, read, write, require, verify_record, case_and_schedule
from ingest import validate
from finalize_batch import verify_batch_record


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--schedule", choices=("early", "late", "split", "global_weak"), required=True)
    a = p.parse_args()
    _, case, schedule = case_and_schedule(a.case, a.schedule)
    pres_path = ROOT / "review" / a.case / a.schedule / "PRESENTATION.json"
    pres = read(pres_path)
    proof = pres["validated_execution"]
    validate(case, dict(schedule, id=a.schedule), proof["video"]["file"], proof["gate"]["file"],
             proof["binding"]["file"])
    batch_path = ROOT / "actual" / a.case / "BATCH_RELEASE.json"
    verify_batch_record(batch_path, case, read(proof["binding"]["file"]), proof["run_record"])
    for key in ("report", "tracks", "historical_inputs"):
        verify_record(case["MF_source_cache"][key])
    helper = PREVIOUS / "mf_preparation/audit/prepare_queue.py"
    spec = importlib.util.spec_from_file_location("r148_score_view", helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    dest = ROOT / "mf_inputs" / a.case / a.schedule
    dest.mkdir(parents=True, exist_ok=True)
    score = dest / "score.mp4"
    hashes = module.score_view(proof["video"]["file"], score, case["geometry"])
    g = case["geometry"]
    write(dest / "INPUTS.json", {"schema": "r149-new-target-mf-input-v1", "case": a.case,
        "role": a.schedule, "run_id": proof["run_id"], "full_video": proof["video"],
        "score_video": bound(score), "frame_md5": hashes,
        "valid_frames": g["valid_frames"], "fps": g["fps"], "crop_xywh": g["crop_xywh"],
        "source_cache": case["MF_source_cache"], "presentation": bound(pres_path),
        "batch_release": bound(batch_path),
        "official_score_view_helper": bound(helper), "status": "CPU_INPUT_READY_GPU_NOT_STARTED"})
    print(str(dest / "INPUTS.json"))


if __name__ == "__main__":
    main()
