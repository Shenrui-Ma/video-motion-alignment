"""Attach the six verified, released R151 MF results to the display tables."""
import json
import math
from pathlib import Path

from prepare import ROOT, bind, read
from sam_pose import verify


def main():
    mf = ROOT.parent / "h3-reference-feedback-r151-20261021" / "mf"
    verified = mf / "audit" / "RESULTS_VERIFIED.json"
    release = mf / "audit" / "FINAL_RELEASE_VERIFIED.json"
    results = read(verified)
    release_data = read(release)
    if results["completed_targets"] != 6 or results["requested_targets"] != 6:
        raise ValueError("All six requested MF results are required.")
    if not release_data.get("passed"):
        raise ValueError("Final tracker release verification is required.")
    manifest = read(ROOT / "EVALUATION_MANIFEST.json")
    cases = {c["source_id"]: c for c in manifest["cases"]}
    expected = {(sid, role) for sid in cases for role in ("reverse_only", "combined")}
    actual = {(r["case"], r["role"]) for r in results["results"]}
    if actual != expected or len(results["results"]) != 6:
        raise ValueError("Duplicate, extra or missing result.")
    tables = {sid: read(ROOT / "reviews" / f"{sid}.json") for sid in cases}
    bindings = {}
    for result in results["results"]:
        sid = result["case"]
        role = "reverse" if result["role"] == "reverse_only" else "combined"
        generation = read(ROOT / "results" / sid / f"{role}.json")
        if result["actual_generated_video_sha256"] != generation["video"]["sha256"]:
            raise ValueError("Score belongs to a different generated video.")
        if result["valid_frames"] != cases[sid]["geometry"]["valid_frames"]:
            raise ValueError("Valid-frame domain differs.")
        if result["evaluation_fps"] != 24 or not math.isfinite(result["score"]):
            raise ValueError("Invalid MF result.")
        for file_key, hash_key in (("result_file", "result_sha256"), ("release_file", "release_sha256")):
            verify({"file": result[file_key], "sha256": result[hash_key]})
        score = read(Path(result["result_file"]))
        if not score["official_numerics_unchanged"]:
            raise ValueError("Official MF numerical implementation differs.")
        bindings.setdefault(sid, {})[role] = result
        row_index = 2 if role == "reverse" else 3
        tables[sid]["table"][row_index]["MF"] = f'{result["score"]:.4f}'
    for sid, table in tables.items():
        table.update(MF_complete=True, MF_evidence={
            "verified_results": bind(verified),
            "final_release": bind(release),
            "new_scores": bindings[sid],
        })
        (ROOT / "reviews" / f"{sid}.json").write_text(
            json.dumps(table, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"bound_scores": 6, "tables": list(tables)}))


if __name__ == "__main__":
    main()
