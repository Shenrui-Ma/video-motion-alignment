"""Bind existing controls without copying their media or changing prior reports."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / "h3-guidance-schedule-eval-r149-20261020"


def read(path):
    return json.loads(path.read_text())


def bind(path):
    return {"file": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def prepare():
    parent = read(OLD / "EVALUATION_MANIFEST.json")
    plan = read(OLD / "EVALUATION_PLAN.json")
    titles = {
        "short_0252": "角色替换 — 机舱男子替换为年长女性",
        "short_0358": "外观编辑 — 给饮酒男子添加眼镜",
        "05_real_megumi_v": "角色替换 — Sam Altman 跳书记舞",
    }
    cases = []
    for source_id in ("short_0252", "short_0358", "05_real_megumi_v"):
        case = next(c for c in parent["cases"] if c["source_id"] == source_id)
        early = OLD / "review" / source_id / "early"
        presentation = read(early / "PRESENTATION.json")
        review = read(early / "REVIEW.json")
        event_summary = early / "EVENT_SUMMARY.json"
        source_plan = next(c for c in plan["cases"] if c["source_id"] == source_id)
        cases.append({
            "source_id": source_id,
            "title": titles[source_id],
            "dataset": case.get("dataset", "IVEBench"),
            "seed": case["seed"],
            "geometry": case["geometry"],
            "prompt": case["prompt"],
            "prompt_sha256": case["prompt_sha256"],
            "reference_image": case.get("reference_image"),
            "controls": {
                "source": case["media"]["source"],
                "native": case["media"]["native"],
                "forward": presentation["new_video"],
            },
            "events": case["events"],
            "event_rules": case["event_rules"],
            "representative_frames": source_plan["representative_frames"],
            "native_MF": case["official_MF"]["native"],
            "forward_MF": read(OLD / "scores" / source_id / "early.json"),
            "forward_review": bind(early / "REVIEW.json"),
            "forward_events": bind(event_summary) if event_summary.exists() else None,
            "forward_pose_timing": review.get("posthoc_pose_result"),
            "parent_presentation": bind(early / "PRESENTATION.json"),
            "parent_batch_release": bind(OLD / "actual" / source_id / "BATCH_RELEASE.json"),
        })
    manifest = {
        "schema": "r151-evaluation-v1",
        "status": "controls_bound_new_results_pending",
        "parent_manifest": bind(OLD / "EVALUATION_MANIFEST.json"),
        "roles": ["source", "native", "forward", "reverse", "combined"],
        "role_labels": {
            "source": "参考视频",
            "native": "普通编辑",
            "forward": "编辑＋正向引导",
            "reverse": "编辑＋反向引导",
            "combined": "编辑＋双向引导",
        },
        "display_step_interval": [1, 9],
        "total_steps": 20,
        "block_interval_half_open": [0, 50],
        "alpha": 1,
        "beta": 1,
        "cases": cases,
        "measurement_rules": [
            "Judge completion of the requested identity/appearance edit and scene preservation first.",
            "Reuse source event definitions and valid-frame/crop domains from R149.",
            "Measure time error, event existence and visual artifacts separately.",
            "Official MF is reported beside event timing; it is not an edit-success score.",
            "Compare combined primarily against matched forward-only, and retain all outcomes.",
        ],
    }
    for case in cases:
        for item in case["controls"].values():
            assert bind(Path(item["file"]))["sha256"] == item["sha256"]
    (ROOT / "EVALUATION_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"Bound {len(cases)} cases and {len(cases) * 3} existing media files.")


if __name__ == "__main__":
    prepare()
