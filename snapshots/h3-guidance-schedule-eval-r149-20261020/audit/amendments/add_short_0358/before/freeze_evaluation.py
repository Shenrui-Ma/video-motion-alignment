"""Freeze the pre-existing event definitions before any R149 output is reviewed."""
from common import ROOT, bound, read, require, write


def main():
    path = ROOT / "EVALUATION_MANIFEST.json"
    manifest = read(path)
    cases = []
    for case in manifest["cases"]:
        sid = case["source_id"]
        cases.append({
            "source_id": sid, "fps": case["geometry"]["fps"],
            "valid_frames": case["geometry"]["valid_frames"],
            "frame_index_base": 0, "interval_endpoints": "inclusive",
            "events": case["events"],
            "adjacent_phase_pairs": [
                [a["id"], b["id"]] for a, b in zip(case["events"], case["events"][1:])],
            "frozen_pose_windows": (case.get("historical_window_diagnostics") or {}).get("windows", []),
            "primary_window": [50, 65] if sid == "05_real_megumi_v" else None,
            "representative_frames": [43, 50, 72] if sid == "short_0252" else [50, 57, 65, 75, 86, 105],
            "full_video_observation": "All effective frames; additional observations are labeled separately.",
        })
    plan = {
        "schema": "r149-preregistered-evaluation-v1",
        "status": "FROZEN_BEFORE_NEW_OUTPUT_REVIEW",
        "historical_manifest": manifest["historical_manifest"],
        "evaluation_manifest": bound(path),
        "cases": cases,
        "rules": [
            "先验收实际编辑任务、身份、场景和动作链，再解释时差。",
            "四种新方案使用相同的旧评价事件和窗口，结果出来后不另选评价主窗。",
            "事件时间按同一物理帧轴比较；缺失记 null，不以全局最佳 lag 替代人工事件。",
            "Sam 的历史 arm_direction lag 仍按原窗口与置信度分别报告，未知保留 null。",
            "所有相邻事件的阶段时长均报告，整体平移与阶段伸缩分开。",
            "失败编辑与负效果保留；MF 与动作事件、姿态和身份变化并列。",
            "采样耗时使用实际记录，并说明是否包含 x0 捕获/审计；不以总运行时间除二十冒充步速。",
        ],
        "event_arithmetic": {
            "event_error": "abs(generated_frame-source_frame)",
            "event_range": "Enumerate all integer frames in each inclusive annotation interval.",
            "paired_change": "abs(new-source)-abs(old_fixed-source), sharing the same source frame.",
            "phase_duration": "next_event_frame-current_event_frame; enumerate intervals with shared source endpoints.",
            "milliseconds": "frames * 1000 / fps",
        },
        "sigma_spans": manifest["sigma_spans"],
        "allowed_analysis": "Offline final-media review/MF; no denoising-time observer or new generation.",
    }
    plan_path = ROOT / "EVALUATION_PLAN.json"
    freeze_path = ROOT / "EVALUATION_FREEZE.json"
    if freeze_path.exists():
        require(read(plan_path) == plan, "Evaluation already frozen; do not replace definitions")
        for item in read(freeze_path)["files"]:
            require(bound(item["file"]) == item, "Frozen file changed")
        print("Existing evaluation freeze verified.")
        return
    require(not list((ROOT / "review").glob("**/PRESENTATION.json")), "Freeze must precede new review")
    write(plan_path, plan)
    write(freeze_path, {"schema": "r149-evaluation-freeze-v1",
        "files": [bound(path), bound(plan_path)],
        "new_outputs_consumed": 0,
        "historical_media_are_pointers": True})
    print(str(freeze_path))


if __name__ == "__main__":
    main()
