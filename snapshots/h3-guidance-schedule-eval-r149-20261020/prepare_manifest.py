"""Freeze pointers to historical controls and existing official MF caches."""
import argparse
import copy
from pathlib import Path
from common import ROOT, PREVIOUS, bound, read, require, verify_record, write, prompt_sha

SCHEDULES = {
    "early": {"label": "早段 1–9", "steps_1based": list(range(1, 10)),
              "steps_0based": list(range(9))},
    "late": {"label": "晚段 12–20", "steps_1based": list(range(12, 21)),
             "steps_0based": list(range(11, 20))},
    "split": {"label": "分段 1–4＋16–20", "steps_1based": [1, 2, 3, 4, 16, 17, 18, 19, 20],
              "steps_0based": [0, 1, 2, 3, 15, 16, 17, 18, 19]},
    "global_weak": {"label": "全局弱引导", "steps_1based": list(range(1, 21)),
                    "steps_0based": list(range(20)), "alpha": 0.25,
                    "physical_window": "full_valid_video",
                    "description": "全有效视频、全部二十步；引导强度为原来的1/4（α=0.25）。"},
}


def main(append_case=None):
    manifest_path = ROOT / "EVALUATION_MANIFEST.json"
    existing = read(manifest_path) if manifest_path.exists() else None
    if append_case:
        require(existing and append_case not in [c["source_id"] for c in existing["cases"]],
                "Append requires an existing evaluation and one new case")
        require(existing["schedules"] == SCHEDULES, "Existing schedules must remain unchanged")
        require((ROOT / "audit/amendments" / ("add_" + append_case) /
                 "before/EVALUATION_FREEZE.json").is_file(), "Archive prior freeze before appending")
    elif (ROOT / "EVALUATION_FREEZE.json").exists():
        for record in read(ROOT / "EVALUATION_FREEZE.json")["files"]:
            verify_record(record)
        print("Existing frozen evaluation verified; use --append-case for an authorized addition.")
        return
    old_path = PREVIOUS / "EVALUATION_MANIFEST.json"
    old = read(old_path)
    mf = PREVIOUS / "mf_preparation"
    mf_remote = read(mf / "configs/RUNTIME.json")["remote_root"]
    release = mf / "audit/FINAL_RELEASE_VERIFIED.json"
    require(read(release)["passed"] is True, "Historical MF batch was not released")
    cases, jobs, checked = [], [], []
    keys = ("source_id", "title", "dataset", "seed", "geometry", "media", "prompt",
            "prompt_sha256", "prompt_source_label", "reference_image", "historical_pair_gate",
            "historical_review", "historical_full_review", "historical_initial_noise",
            "historical_source_remote", "task_checks", "historical_window_diagnostics")
    for original in old["cases"]:
        sid = original["source_id"]
        if sid not in ((append_case,) if append_case else ("short_0252", "05_real_megumi_v")):
            continue
        case = {k: copy.deepcopy(original[k]) for k in keys if k in original}
        if sid == "short_0358":
            case["title"] = "外观编辑 — 给饮酒男子戴眼镜"
        require(prompt_sha(case["prompt"]) == case["prompt_sha256"], "Prompt SHA differs")
        case["historical_runs"] = {
            role: {k: original["historical_runs"][role][k] for k in
                   ("run_id", "graph", "router_node_50", "history")
                   if k in original["historical_runs"][role]}
            for role in ("native", "fixed")
        }
        router = case["historical_runs"]["fixed"]["router_node_50"]["inputs"]
        require((router["step_start"], router["step_end"]) == (6, 15), "Old fixed schedule differs")
        case["fixed_schedule"] = {"label": "时序引导 7–15",
                                  "steps_0based": list(range(6, 15)), "steps_1based": list(range(7, 16))}
        case["invariant_router"] = {k: router[k] for k in
            ("mode", "alpha", "radius", "time_offset", "start_frame", "end_frame", "block_start", "block_end")}
        case["phase_offset"] = 0
        case["events"] = [{k: v for k, v in e.items() if k != "fixed_phase"}
                          for e in original["events"]]
        for e in case["events"]:
            for schedule in SCHEDULES:
                e[schedule] = None
        for window in (case.get("historical_window_diagnostics") or {}).get("windows", []):
            window.pop("fixed_phase", None)
            for schedule in SCHEDULES:
                window[schedule] = None
        case["event_rules"] = [
            "先核编辑完成、人物和场景，再比较同一动作事件。",
            "沿用历史事件定义及区间，缺失事件记 null，所有相邻阶段均保留。",
            "Sam 的既有 arm_direction lag 是离线姿态窗口诊断，不是人工事件起止标注。",
            "失败编辑、缺失动作和负时序结果均保留。"
        ]
        case["official_MF"] = {}
        for role in ("native", "fixed"):
            score_path = PREVIOUS / "scores" / sid / (role + ".json")
            score = read(score_path) if score_path.exists() else original["official_MF"][role]
            require(score is not None, "Completed historical score is required")
            case["official_MF"][role] = score
        inputs_path = mf / "cases" / sid / "INPUTS.json"
        inputs = read(inputs_path)
        g = case["geometry"]
        require(inputs["source_full_sha256"] == case["media"]["source"]["sha256"] and
                inputs["valid_frames"] == g["valid_frames"] and
                inputs["evaluation_frames"] == g["valid_frames"] and
                inputs["evaluation_fps"] == g["fps"] and inputs["crop_xywh"] == g["crop_xywh"],
                "Historical source MF frame/pixel domain differs")
        result = read(mf / "results" / sid / "fixed_phase.json")
        report_path = mf / Path(result["source_report"]["file"]).relative_to(mf_remote)
        report = read(report_path)
        require(report["passed"] is True and bound(report_path)["sha256"] ==
                result["source_report"]["sha256"], "Source tracking report mismatch")
        require(report["official_commit"] == "2dcf8900ee65197f43854c76f61c66a32bb8dbfc" and
                report["checkpoint_sha256"] == "da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df",
                "Official metric implementation or checkpoint differs")
        tracks = report_path.parent / "tracks.npz"
        require(bound(tracks)["sha256"] == report["tracks_sha256"], "Source tracks mismatch")
        case["MF_source_cache"] = {
            "historical_inputs": bound(inputs_path), "report": bound(report_path),
            "tracks": bound(tracks), "remote_report": result["source_report"]["file"],
            "remote_tracks": str(Path(result["source_report"]["file"]).with_name("tracks.npz")),
            "source_full_sha256": inputs["source_full_sha256"],
            "source_score_sha256": inputs["source_score_sha256"],
            "source_frame_md5": inputs["source_frame_md5"],
            "selection_sha256": inputs["selection_sha256"],
            "official_commit": report["official_commit"], "checkpoint_sha256": report["checkpoint_sha256"],
            "tracker": report["tracker"], "prior_release": bound(release),
        }
        refs = list(case["media"].values())
        if case.get("reference_image"):
            refs.append(case["reference_image"])
        refs += [run["graph"] for run in case["historical_runs"].values()]
        refs += [case[k] for k in ("historical_review", "historical_full_review")
                 if case.get(k)]
        refs += [score["result"] for score in case["official_MF"].values()]
        if case.get("historical_window_diagnostics"):
            refs.append(case["historical_window_diagnostics"]["record"])
        for ref in refs:
            verify_record(ref)
            checked.append(ref)
        for schedule in SCHEDULES:
            jobs.append({"case": sid, "schedule": schedule, "status": "PENDING_GENERATION",
                         "new_trackers": 1, "reuse_source_tracks": True})
            binding = ROOT / "runtime" / sid / (schedule + ".json")
            if not binding.exists() or read(binding).get("status") == "PENDING_PRODUCER_CONTRACT":
                write(binding, {"status": "PENDING_PRODUCER_CONTRACT", "source_id": sid,
                    "schedule": schedule, "phase_offset": 0,
                    "steps_0based": SCHEDULES[schedule]["steps_0based"],
                    "historical_prompt_sha256": case["prompt_sha256"],
                    "historical_noise_sha256": case["historical_initial_noise"]["sha256"],
                    "historical_fixed_graph_sha256": case["historical_runs"]["fixed"]["graph"]["sha256"],
                    "run_id": f"r149_{sid}_seed{case['seed']}_{schedule}",
                    "role": schedule, "producer_seal": None,
                    "gate_schema": "r149-fixed-schedule-runtime-gate-v1",
                    "complete_schema": "r149-schedule-completion-v1",
                    "remote_root": f"/data4/researcher/h3_runs/guidance_schedule_r149_20261020/cases/{sid}"})
        cases.append(case)
    manifest = {"schema": "r149-schedule-evaluation-v1", "status": "PREPARED_NO_NEW_OUTPUT",
        "historical_manifest": bound(old_path), "display_index_base": 1, "code_index_base": 0,
        "roles": ["source", "native", "fixed", "selected_schedule"],
        "schedules": SCHEDULES, "total_sampling_steps": 20,
        "active_steps": {arm: len(row["steps_0based"]) for arm, row in SCHEDULES.items()},
        "phase_offset": 0,
        "scientific_variable": "early/late/split change only the nine active steps. global_weak additionally uses all effective video frames and alpha=0.25 across all 20 steps.",
        "invariants": ["historical prompt", "actual initial AV noise", "reference conditions",
            "mass_preserve", "radius/time_offset",
            "all 50 transformer blocks", "20 Euler sampling steps", "no additional RoPE phase"],
        "global_weak_meaning": "引导强度为原来的1/4（α=0.25）：在原 all-reference 输出与同时间 bin 读数之间混合，参考总概率质量保持。全局指全有效视频与二十个去噪步，仍只作用输出视频 query。",
        "cases": cases}
    sigma_source = ROOT.parent / "h3-guidance-schedule-audit-r149-20261020/PLAN_REVIEW.json"
    sigma_plan = read(sigma_source)
    spans = {}
    indices = {"historical_middle": list(range(6, 15)),
               **{key: value["steps_0based"] for key, value in SCHEDULES.items()}}
    for sid, source in sigma_plan["sources"].items():
        sigmas = source["sample_sigmas"]
        require(len(sigmas) == 21, "Expected 21 sigma boundaries")
        spans[sid] = {key: sum(abs(sigmas[i + 1] - sigmas[i]) for i in steps)
                      for key, steps in indices.items()}
    manifest["sigma_spans"] = {"source": bound(sigma_source), "values": spans,
        "meaning": "sum(abs(sigma[i+1]-sigma[i])) over the active steps; not equal intervention strength.",
        "note_zh": "前三个方案均启用九步，但 Euler 积分覆盖的 sigma 跨度不同；全局弱引导启用全部二十步。"}
    mf_plan = {"schema": "r149-mf-preparation-v1", "status": "CPU_PREPARED_NOT_LAUNCHED",
        "new_target_trackers": len(jobs), "new_source_trackers": 0, "jobs": jobs,
        "reuse_runtime": "/data4/researcher/h3_runs/timing_phase_combined_mf_r148_20261020/runtime",
        "baseline_package": str(mf),
        "cache_rule": "Reuse only exact source full SHA, scored frame pixels, crop/fps/domain, checkpoint and tracker settings.",
        "gpu_authorization": "REDACTED_CREDENTIAL"}
    checks = {"passed": True, "historical_files_verified": checked,
        "source_cache_tracks_verified": len(cases), "old_scores_reused": 2 * len(cases),
        "new_GPU_jobs": 0, "large_assets_copied": 0,
        "shared_helper": bound(PREVIOUS / "prepare_comparison.py")}
    if append_case:
        require(len(cases) == 1 and cases[0]["source_id"] == append_case, "New case not found")
        new_case = cases[0]
        manifest = copy.deepcopy(existing)
        manifest["cases"].append(new_case)
        graph_record = new_case["historical_runs"]["fixed"]["graph"]
        graph = read(graph_record["file"])
        sigma_nodes = [(key, value) for key, value in graph.items()
                       if value.get("class_type") == "ManualSigmas"]
        require(len(sigma_nodes) == 1, "Historical sigma node ambiguous")
        node, value = sigma_nodes[0]
        sigmas = [float(x) for x in value["inputs"]["sigmas"].split(",")]
        require(len(sigmas) == 21, "Expected 21 actual historical sigma boundaries")
        manifest["sigma_spans"]["values"][append_case] = {
            key: sum(abs(sigmas[i + 1] - sigmas[i]) for i in steps)
            for key, steps in indices.items()}
        manifest["sigma_spans"].setdefault("additional_case_sources", {})[append_case] = {
            "graph": graph_record, "node_id": node, "sample_sigmas": sigmas}
        old_mf = read(ROOT / "MF_PLAN.json")
        mf_plan = copy.deepcopy(old_mf)
        mf_plan["jobs"] += jobs
        mf_plan["new_target_trackers"] = len(mf_plan["jobs"])
        old_checks = read(ROOT / "audit/PREPARATION_CHECKS.json")
        checks["historical_files_verified"] = old_checks["historical_files_verified"] + checked
        checks["source_cache_tracks_verified"] += old_checks["source_cache_tracks_verified"]
        checks["old_scores_reused"] += old_checks["old_scores_reused"]
        require(manifest["cases"][:-1] == existing["cases"], "Historical cases changed")
    write(manifest_path, manifest)
    write(ROOT / "MF_PLAN.json", mf_plan)
    write(ROOT / "audit/PREPARATION_CHECKS.json", checks)
    print(f"Prepared {len(manifest['cases'])} cases, {mf_plan['new_target_trackers']} pending outputs; source caches verified.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--append-case", choices=("short_0358",))
    main(p.parse_args().append_case)
