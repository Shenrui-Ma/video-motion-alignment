"""Bind already verified official MF results into this display; no scoring or GPU."""
import argparse
import json
import math
from pathlib import Path

from prepare_comparison import ROOT, bound, read, require


def validate_score(case, role, video_sha, value, inputs):
    g = case["geometry"]
    require(value["case"] == case["source_id"] and value["role"] == role, "Wrong score role/case")
    require(value["actual_generated_video_sha256"] == video_sha, "Wrong score video")
    require(value["source_full_sha256"] == case["media"]["source"]["sha256"], "Wrong score source")
    require(value["valid_frames"] == value["evaluation_frames"] == g["valid_frames"]
            and value["evaluation_fps"] == g["fps"]
            and inputs["crop_xywh"] == g["crop_xywh"], "Wrong score frame domain")
    require(value["official_numerics_unchanged"] is True and value["cuda_initialized"] is False,
            "Official CPU scoring proof required")
    score = value.get("score", value.get("motion_fidelity"))
    require(type(score) in (float, int) and math.isfinite(score), "Non-finite official score")
    return score


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--package", type=Path, required=True)
    a = p.parse_args()
    package = a.package.resolve()
    require(package.is_relative_to(ROOT), "Only this evaluation's MF package may be imported")
    release_path = package / "audit/FINAL_RELEASE_VERIFIED.json"
    released = read(release_path)
    require(released["passed"] is True and released["fresh_task_cuda_absent"] is True
            and released["exact_processes_absent"] is True
            and released["exact_CUDA_allocations_absent"] is True, "Final tracker release required")
    require(released["seal"]["sha256"] == bound(package / "SEAL.json")["sha256"], "Scoring seal changed")
    verified = read(package / "audit/RESULTS_VERIFIED.json")
    require(verified["completed_targets"] == verified["requested_targets"], "MF batch incomplete")
    cases = {c["source_id"]: c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]}
    outputs = []
    for row in verified["results"]:
        case, role = cases[row["case"]], row["role"]
        path = package / "results" / row["case"] / (role + ".json")
        require(bound(path)["sha256"] == row["result_sha256"], "Result receipt changed")
        value = read(path)
        cp = package / "cases" / row["case"] / "INPUTS.json"
        require(bound(cp)["sha256"] == value["case_input"]["sha256"], "Scoring input changed")
        if role == "fixed_phase":
            media = read(ROOT / "review" / row["case"] / "PRESENTATION.json")["inputs"][role]
        else:
            require(case["source_id"] == "05_real_megumi_v" and role in ("native", "fixed"),
                    "Do not replace existing historical scores")
            media = case["media"][role]
        score = validate_score(case, role, media["sha256"], value, read(cp))
        g = case["geometry"]
        record = dict(schema="r148-display-official-mf-v1", role=role, score=score,
                      actual_generated_video_sha256=media["sha256"],
                      source_full_sha256=case["media"]["source"]["sha256"],
                      valid_frames=g["valid_frames"], fps=g["fps"], crop_xywh=g["crop_xywh"],
                      result=bound(path), input_binding=bound(cp), final_release=bound(release_path),
                      official_numerics_unchanged=True)
        out = ROOT / "scores" / row["case"] / (role + ".json")
        if out.exists():
            require(read(out) == record, "Preserve an existing differing score")
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        outputs.append(bound(out))
    (ROOT / "audit/MF_DISPLAY_IMPORT.json").write_text(
        json.dumps(dict(package=str(package), scores=outputs), indent=2) + "\n")
    print(json.dumps(dict(imported=len(outputs))))


if __name__ == "__main__":
    main()
