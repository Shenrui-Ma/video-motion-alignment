"""Bind completed historical evidence only; no media copying or inference."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT.parent
PRODUCER = PROJECTS / "h3-reference-origin-positive-retest-r146-20261020"


def read(path):
    return json.loads(Path(path).read_text())


def bound(path):
    path = Path(path)
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return {"file": str(path), "sha256": h.hexdigest()}


def main():
    specs = [
        ("short_0252", "机舱：男性替换为年长女性",
         PROJECTS / "h3-oxygen-generic-retention-metrics-r141b-host9-20261020",
         "audit/independent_pair_review/INDEPENDENT_REVIEW.json",
         PROJECTS / "h3-oxygen-generic-retention-mf-r141b-20261020/audit/RESULTS_VERIFIED.json",
         {"native": "native", "fixed": "forced"}),
        ("short_0358", "饮酒：给左侧拿酒瓶男子添加眼镜",
         PROJECTS / "h3-ive-prompt-envelope-metrics-r123-20261020/variants/full_context",
         "audit/full_frame_review/short_0358/paired/INDEPENDENT_REVIEW.json",
         PROJECTS / "h3-ive-context-mf-host41-20261020/audit/RESULTS_VERIFIED.json",
         {"native": "full_native", "fixed": "full_forced"}),
    ]
    cases = []
    for sid, title, consumer, review_rel, mf_path, score_roles in specs:
        contract_path = PRODUCER / "cases" / sid / "configs/scientific_contract.json"
        contract = read(contract_path)
        c = contract["cases"][0]
        inputs_path = consumer / f"prepared/{sid}/paired/MF_INPUTS.json"
        inputs = read(inputs_path)
        gate = read(inputs["gate"]["file"])
        review_path = consumer / review_rel
        review = read(review_path)
        media = {}
        for role, historical_role in (("source", "source"), ("native", "native"), ("fixed", "forced")):
            item = inputs["raw_videos"][historical_role]
            assert bound(item["file"])["sha256"] == item["sha256"]
            remote = (gate["runtime_profile"]["remote_root"] + "/input/" + c["video"]
                      if role == "source" else gate["runs"][historical_role]["video"]["file"])
            media[role] = {**item, "producer_remote_file": remote}
        assert c["video_sha256"] == media["source"]["sha256"]
        assert bound(PRODUCER / "cases" / sid / c["parent_graph"])["sha256"] == c["parent_graph_sha256"]
        events = []
        for i, e in enumerate(review["events"]):
            if sid == "short_0252":
                event = {"id": e["id"], "label": e["label"], "source": e["source"],
                         "native": e["native"], "fixed": e["guided"]}
            else:
                event = {"id": ("bottle_lowered", "bottle_reaches_lips", "bottle_leaves_lips")[i],
                         "label": ("放低酒瓶", "瓶口到嘴、开始饮酒", "瓶口离嘴")[i],
                         "source": e["source_frames"], "native": e["native_frames"],
                         "fixed": e["forced_frames"]}
            event["reference_origin"] = None
            events.append(event)
        phases = []
        for a, b in zip(events, events[1:]):
            phase = {"from": a["id"], "to": b["id"], "reference_origin": None}
            for role in ("source", "native", "fixed"):
                phase[role] = {"duration_frames_range": [b[role][0] - a[role][1],
                                                        b[role][1] - a[role][0]],
                               "midpoint_frames": (sum(b[role]) - sum(a[role])) / 2}
            phases.append(phase)
        scores = {}
        results = read(mf_path)["results"]
        for role, saved_role in score_roles.items():
            r = next(r for r in results if r["case"] == sid and r["role"] == saved_role)
            assert r["actual_generated_video_sha256"] == media[role]["sha256"]
            scores[role] = {"score": r["score"], "actual_role": saved_role,
                            "result": bound(r["result_file"])}
        scores["reference_origin"] = None
        if sid == "short_0358":
            pose_binding_path = PROJECTS / "h3-threecase-auto-r144-20261020/input_audit/short_0358/SOURCE_PERSON_BINDING.json"
            pb = read(pose_binding_path)
            pose = {**bound(pb["source_pose"]), "remote_file": pb["source_pose_remote"],
                    "person_binding": bound(pose_binding_path), "selected_subject": pb["selected_subject"],
                    "selection_x_fraction": pb["selected_bbox_center_x_fraction"]}
        else:
            pose = {**bound(PROJECTS / "h3-source-temporal-observability-20261020/inputs/source.pose.json"),
                    "remote_file": None,
                    "note": "Existing full source pose, exact same MP4 SHA; target adult selection must retain historical subject binding."}
        pose_data = read(pose["file"])
        assert pose_data["video"]["sha256"] == media["source"]["sha256"]
        cases.append({
            "source_id": sid, "title": title, "seed": c["seed"],
            "historical_consumer": str(consumer), "geometry": {
                "width": 1312, "height": 736, "sampled_frames": 107, "valid_frames": inputs["valid_frames"],
                "fps": 24, "crop_xywh": inputs["crop_xywh"]},
            "media": media, "source_pose": pose, "events": events, "phases": phases,
            "prompt": c["prompt"], "prompt_sha256": c["prompt_sha256"],
            "parent_graph": bound(PRODUCER / "cases" / sid / c["parent_graph"]),
            "historical_pair_gate": inputs["gate"], "historical_review": bound(review_path),
            "historical_MF_receipt": bound(mf_path), "official_MF": scores,
            "task_checks": (["年长女性替换成立", "儿童、机舱、面罩与动作顺序保留", "不把抬带写成已戴稳面罩"]
                            if sid == "short_0252" else
                            ["仅左侧拿酒瓶男子添加眼镜", "另一男子、场景、构图与饮酒链保留"]),
            "R146": {"status": "PENDING_NOT_GENERATED", "run_id": c["run_id"],
                     "role": "reference_origin", "producer_case": str(PRODUCER / "cases" / sid),
                     "contract_at_preparation": bound(contract_path),
                     "remote_root": f"/data4/researcher/h3_runs/reference_origin_positive_retest_r146_20261020/cases/{sid}",
                     "parent_noise_file": contract["parent_noise_file"],
                     "parent_noise_sha256": contract["parent_noise_sha256"],
                     "producer_seal": None, "completion": None, "score": None},
            "timing": {"historical_job_wall_seconds": {
                role: gate["runs"][old].get("job_wall_seconds")
                for role, old in (("native", "native"), ("fixed", "forced"))}},
            "sampling_seconds": {"native": None, "fixed": None, "reference_origin": None},
            "timing_rule": "Use actual sampler timestamps/logs; job_wall/20 is not sampler seconds per step. Keep capture, loading and decoding separate.",
        })
    manifest = {
        "schema": "r146-reference-origin-evaluation-v1",
        "status": "PREDECLARED_AWAITING_VALIDATED_PHASE_OUTPUTS",
        "index_base": 0, "interval_semantics": "Inclusive observed transition intervals, not confidence intervals.",
        "method_labels": {"source": "参考视频", "native": "普通编辑",
                          "fixed": "固定引导｜同时间段 Value",
                          "reference_origin": "参考分支 RoPE 相位引导"},
        "comparison_note": "Old fixed and R146 both use steps6..14/all50blocks/alpha1. R146 rotates query only in the auxiliary reference branch; original joint RoPE remains unchanged.",
        "acceptance": ["Verify actual run/gate/COMPLETE/exact release and video SHA/107frames/geometry before rendering.",
                       "Inspect every valid frame for edit completion before event comparisons; missing events remain null.",
                       "Reuse frozen event definitions; compare signed and absolute event-time errors and adjacent phase durations.",
                       "Use shared source event intervals for paired differences; retain full integer-frame ranges.",
                       "Report official MF separately; reuse completed Native/fixed scores, score only new output later.",
                       "No online RGB observer; any optional final-video pose needs separate root authorization."],
        "cases": cases,
    }
    out = ROOT / "EVALUATION_MANIFEST.json"
    if out.exists():
        raise FileExistsError(out)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(bound(out)))


if __name__ == "__main__":
    main()
