"""Prepare final-video MF inputs; reuse Sam05 source tracks only after pixel checks."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from common import bound, read, require, verify_record, write, case_and_schedule
from ingest import validate
from finalize_batch import verify_batch_record

HELPER = ROOT.parent / "h3-timing-phase-combined-eval-r148-20261020/mf_preparation/audit/prepare_queue.py"
spec = importlib.util.spec_from_file_location("existing_score_views", HELPER)
views = importlib.util.module_from_spec(spec)
spec.loader.exec_module(views)
ROLES = ("native", "fixed", "early", "late", "split", "global_weak")
CASES = ("musk05", "firefly06", "sam07")


def source_inputs(case, dest):
    sid, geometry = case["source_id"], case["geometry"]
    verify_record(case["media"]["source"])
    views.link(case["media"]["source"]["file"], dest / "source_full.mp4")
    pixels = views.score_view(dest / "source_full.mp4", dest / "source_score.mp4", geometry)
    evidence = {
        "source": case["media"]["source"], "geometry": geometry,
        "score_video": bound(dest / "source_score.mp4"),
        "frame_md5": pixels, "official_score_view_helper": bound(HELPER),
    }
    cache = None
    canonical_id = case.get("original_source_id", sid)
    if sid == "musk05":
        prior_manifest = ROOT.parent / "h3-guidance-schedule-eval-r149-20261020/EVALUATION_MANIFEST.json"
        old_case = next(c for c in read(prior_manifest)["cases"] if c["source_id"] == "05_real_megumi_v")
        old_cache = old_case["MF_source_cache"]
        for key in ("historical_inputs", "report", "tracks", "prior_release"):
            verify_record(old_cache[key])
        old = read(old_cache["historical_inputs"]["file"])
        report = read(old_cache["report"]["file"])
        require(old["source_full_sha256"] == case["media"]["source"]["sha256"]
                and old["source_frame_md5"] == pixels == report["decoded_frame_md5"]
                and old["valid_frames"] == old["evaluation_frames"] == geometry["valid_frames"]
                and old["evaluation_fps"] == geometry["fps"]
                and old["crop_xywh"] == geometry["crop_xywh"], "Sam05 cached source domain differs")
        require(report["passed"] and report["tracks_sha256"] == old_cache["tracks"]["sha256"]
                and report["checkpoint_sha256"] == old_cache["checkpoint_sha256"]
                and report["official_commit"] == old_cache["official_commit"]
                and report["selection_sha256"] == old["selection_sha256"],
                "Sam05 cached tracker provenance differs")
        # Use the exact old lossless MP4 after independently comparing its pixels.
        old_score = Path(old_cache["historical_inputs"]["file"]).parent / "source_score.mp4"
        require(bound(old_score)["sha256"] == old["source_score_sha256"], "Old score MP4 changed")
        require(bound(dest / "source_score.mp4")["sha256"] == old["source_score_sha256"],
                "Lossless scoring MP4 differs; inspect before reusing cache")
        for key, name in (("report", "REPORT.json"), ("tracks", "tracks.npz")):
            views.link(old_cache[key]["file"], dest / "tracks/source" / name)
        cache = {"report_sha256": old_cache["report"]["sha256"],
                 "tracks_sha256": old_cache["tracks"]["sha256"]}
        evidence["reused_cache"] = old_cache
        selection_sha = old["selection_sha256"]
        canonical_id = old["canonical_id"]
    else:
        selection = dest / "SOURCE_SELECTION.json"
        value = {"source_id": sid, "source": case["media"]["source"], "geometry": geometry,
                 "protocol": "All 141 frames, 24 fps, full 1312x736; unchanged official IVEBench MF"}
        if selection.exists():
            require(read(selection) == value, "Source selection changed")
        else:
            write(selection, value)
        selection_sha = bound(selection)["sha256"]
        evidence["first_source_tracker_required"] = True
    write(dest / "SOURCE_BINDING.json", evidence)
    return {
        "schema": "r150-dance-official-mf-inputs-v1", "benchmark": "IVEBench",
        "dataset_scope": "Custom role replacement; unchanged IVEBench official MF implementation",
        "canonical_id": canonical_id, "valid_frames": geometry["valid_frames"],
        "evaluation_frames": geometry["valid_frames"], "evaluation_fps": geometry["fps"],
        "crop_xywh": geometry["crop_xywh"], "source_full_sha256": case["media"]["source"]["sha256"],
        "source_score_sha256": bound(dest / "source_score.mp4")["sha256"],
        "source_frame_md5": pixels, "selection_sha256": selection_sha,
        "source_cache": cache, "targets": [],
    }


def prepare(sid):
    manifest, case, _ = case_and_schedule(sid, "early")
    dest = ROOT / "mf_inputs" / sid
    dest.mkdir(parents=True, exist_ok=True)
    result = source_inputs(case, dest)
    pending = []
    for role in ROLES:
        historical = sid == "musk05" and role == "native"
        if historical:
            video = case["media"]["native"]
            verify_record(video)
            recovery_file = ROOT.parent / "h3-guidance-schedule-r150-20261021/condition_recovery/musk05/CACHE_RECOVERY_RESULT.json"
            recovery = read(recovery_file)
            require(recovery["passed"] and recovery["same_historical_embedding"] is True
                    and recovery["requires_shared_cache_native"] is False
                    and recovery["original_embedding_signature"] == recovery["actual_embedding_signature"],
                    "Historical Musk Native requires exact recovered embedding")
            proof = {"historical_manifest": bound(ROOT / "selected_history/musk05.json"),
                     "condition_recovery": bound(recovery_file),
                     "source_condition_requirement": "Producer recovered historical embedding exactly; old Native reused"}
            run_id = Path(video["file"]).stem
        else:
            presentation = ROOT / "review" / sid / role / "PRESENTATION.json"
            if not presentation.exists():
                pending.append(role)
                continue
            execution = read(presentation)["validated_execution"]
            _, _, schedule = case_and_schedule(sid, role)
            validate(case, schedule, execution["video"]["file"], execution["gate"]["file"],
                     execution["binding"]["file"])
            batch = ROOT / "actual" / sid / "BATCH_RELEASE.json"
            if not batch.exists():
                pending.append(role)
                continue
            verify_batch_record(batch, case, read(execution["binding"]["file"]), execution["run_record"])
            video, run_id = execution["video"], execution["run_id"]
            proof = {"presentation": bound(presentation), "generation_release": bound(batch),
                     "gate": execution["gate"], "binding": execution["binding"]}
        target = dest / role
        views.link(video["file"], target / "full.mp4")
        pixels = views.score_view(target / "full.mp4", target / "score.mp4", case["geometry"])
        write(target / "EVIDENCE.json", proof)
        result["targets"].append({
            "role": role, "full_file": role + "/full.mp4", "full_sha256": video["sha256"],
            "score_file": role + "/score.mp4", "score_sha256": bound(target / "score.mp4")["sha256"],
            "score_frame_md5": pixels, "evaluation_indices": list(range(case["geometry"]["valid_frames"])),
            "inventory_bindings": [{"id": run_id, "field": role}], "historical_media": historical,
        })
    write(dest / "DANCE_INPUTS.json", result)
    write(dest / "PREPARATION.json", {
        "case": sid, "source_cache_reused": bool(result["source_cache"]),
        "new_source_trackers": int(result["source_cache"] is None),
        "target_count_expected": len(ROLES), "ready_targets": [t["role"] for t in result["targets"]],
        "pending_targets": pending, "GPU_started": False, "inputs": bound(dest / "DANCE_INPUTS.json"),
    })
    print(sid, "ready", [t["role"] for t in result["targets"]], "pending", pending)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=CASES, required=True)
    prepare(parser.parse_args().case)
