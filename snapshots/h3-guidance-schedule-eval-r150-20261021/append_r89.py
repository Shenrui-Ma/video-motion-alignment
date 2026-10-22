"""Append the two root-selected R89 controls; preserve the existing case records."""
import copy
import hashlib
from pathlib import Path
from common import ROOT, read, write, bound, verify_record, require


def main():
    manifest_path = ROOT / "EVALUATION_MANIFEST.json"
    old = read(manifest_path)
    new = copy.deepcopy(old)
    mfroot = ROOT.parent / "h3-display-pending-mf-20261019"
    mfremote = Path("/data4/researcher/h3_runs/display_pending_mf_20261019")
    release = mfroot / "audit/FINAL_RELEASE_VERIFIED.json"
    require(read(release)["passed"] is True, "Historical MF release missing")
    additions = []
    for sid, title in [
        ("short_0085", "外观编辑 — 将窗边女子的头发改红"),
        ("short_0274", "角色替换 — 将宇航员替换为外星人"),
    ]:
        source_path = ROOT / "selected_history" / f"r89_{sid}.json"
        c = read(source_path)
        producer = ROOT.parent / "h3-guidance-schedule-r150-20261021/host9/cases" / sid
        contract_path = producer / "configs/scientific_contract.json"
        contract = read(contract_path)
        original = c["scientific_contract_case"][0]
        fixed_graph = c["graphs"]["forced"]["graph"]
        router = read(fixed_graph["file"])["50"]["inputs"]
        require((router["step_start"], router["step_end"]) == (6, 15), "Wrong historical schedule")
        require(contract["parent_graph_sha256"] == c["graphs"]["native"]["graph"]["sha256"]
                if "parent_graph_sha256" in contract else
                contract["cases"][0]["parent_graph_sha256"] == c["graphs"]["native"]["graph"]["sha256"],
                "New producer refers to a different historical Native graph")
        prompt = c["prompt"]
        require(prompt == contract["cases"][0]["prompt"], "Prompt mismatch")
        result_path = Path(c["official_MF"]["actual_score_bindings"]["native"]["result_file"])
        result = read(result_path)
        report_path = mfroot / Path(result["source_report"]["file"]).relative_to(mfremote)
        tracks_path = report_path.with_name("tracks.npz")
        input_path = mfroot / Path(result["case_input"]["file"]).relative_to(mfremote)
        report, inputs = read(report_path), read(input_path)
        require(
            bound(result_path)["sha256"] == c["official_MF"]["actual_score_bindings"]["native"]["sha256"]
            and result["actual_generated_video_sha256"] == c["media"]["native"]["sha256"]
            and result["source_full_sha256"] == c["media"]["source"]["sha256"]
            and bound(report_path)["sha256"] == result["source_report"]["sha256"]
            and bound(input_path)["sha256"] == result["case_input"]["sha256"]
            and report["passed"] is True
            and bound(tracks_path)["sha256"] == report["tracks_sha256"]
            and inputs["source_frame_md5"] == report["decoded_frame_md5"]
            and len(inputs["source_frame_md5"]) == c["valid_frames"],
            "Historical MF source or generated-video binding differs",
        )
        media = {role: {"file": rec["file"], "sha256": rec["sha256"]}
                 for role, rec in c["media"].items()}
        for rec in media.values():
            verify_record(rec)
        events = [{
            "id": e["id"], "label": e["label"], "source": None, "native": None, "fixed": None,
            **{arm: None for arm in new["schedules"]},
            "measurement_kind": e["measurement_kind"],
            "source_phase_interval": e["source_interval_inclusive"],
            "native_phase_interval": e["native_interval_inclusive"],
            "precision_note": e["precision_note"],
        } for e in c["frozen_events"]["events"]]
        row = {
            "source_id": sid, "candidate_id": c["candidate_id"], "title": title,
            "dataset": "IVEBench", "seed": c["seed"],
            "producer_contract_schema": "r150-r89-schedule-extension-v1",
            "geometry": {
                "width": original["geometry"]["width"], "height": original["geometry"]["height"],
                "sampled_frames": original["geometry"]["frames"], "valid_frames": c["valid_frames"],
                "fps": c["fps"], "crop_xywh": original["evaluation_crop_xywh"],
            },
            "media": media, "prompt": prompt,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "prompt_source_label": "沿用 R89 完整实验提示词，固定新旧对照",
            "historical_runs": {
                role: {
                    "run_id": c["actual_runs"][oldrole]["run_id"],
                    "graph": c["graphs"][oldrole]["graph"],
                    "router_node_50": read(c["graphs"][oldrole]["graph"]["file"])["50"],
                } for role, oldrole in [("native", "native"), ("fixed", "forced")]
            },
            "historical_initial_noise": {
                "file": contract["parent_noise_file"], "sha256": contract["parent_noise_sha256"],
                "binding": bound(contract_path), "local_tensor_copy": False,
            },
            "historical_pair_gate": c["pair_gate"],
            "historical_review": c["frozen_events"]["evidence"][0],
            "historical_record": bound(source_path),
            "historical_MF_receipt": bound(result_path),
            "official_MF": {"native": c["official_MF"]["native"], "fixed": c["official_MF"]["guided"]},
            "fixed_schedule": {"label": "时序引导 7–15", "steps_0based": list(range(6,15)),
                               "steps_1based": list(range(7,16))},
            "invariant_router": {k: router[k] for k in [
                "mode", "alpha", "radius", "time_offset", "start_frame", "end_frame", "block_start", "block_end"]},
            "phase_offset": 0, "events": events, "phases": [],
            "native_timing_status": "no_clear_delay_preservation_control",
            "event_rules": ["沿用旧宽阶段作保持性审查；精确动作边界尚未标注，不计算阶段中点时差。",
                            "全片检查编辑、场景、动作顺序；未出现的同一动作记 null。"],
            "MF_source_cache": {
                "historical_inputs": bound(input_path), "report": bound(report_path),
                "tracks": bound(tracks_path), "remote_report": result["source_report"]["file"],
                "remote_tracks": str(Path(result["source_report"]["file"]).with_name("tracks.npz")),
                "source_full_sha256": result["source_full_sha256"],
                "source_score_sha256": result["source_score_sha256"],
                "source_frame_md5": inputs["source_frame_md5"],
                "selection_sha256": inputs["selection_sha256"],
                "official_commit": report["official_commit"], "checkpoint_sha256": report["checkpoint_sha256"],
                "tracker": report["tracker"], "prior_release": bound(release),
            },
        }
        prior = next((x for x in new["cases"] if x["source_id"] == sid), None)
        if prior is not None:
            require(prior == row, "Existing R89 case differs")
        else:
            new["cases"].append(row)
            additions.append(sid)
    if additions:
        archive = ROOT / "audit/manifest_history" / bound(manifest_path)["sha256"]
        for name in ("EVALUATION_MANIFEST.json", "EVALUATION_PLAN.json", "EVALUATION_FREEZE.json"):
            write(archive / name, read(ROOT / name))
        write(manifest_path, new)
        plan = read(ROOT / "EVALUATION_PLAN.json")
        plan["source_event_manifest"] = bound(manifest_path)
        plan["cases"] += [{
            "source_id": c["source_id"], "valid_frames": c["geometry"]["valid_frames"],
            "events": c["events"], "phases": c["phases"], "full_frame_review": True,
        } for c in new["cases"] if c["source_id"] in additions]
        write(ROOT / "EVALUATION_PLAN.json", plan)
        write(ROOT / "audit/R89_APPEND.json", {
            "added_cases": additions, "prior_manifest": bound(archive / "EVALUATION_MANIFEST.json"),
            "new_manifest": bound(manifest_path), "old_case_records_unchanged": new["cases"][:len(old["cases"])] == old["cases"],
            "new_outputs_observed": 0, "media_copied": False,
        })
    print("R89 history and exact cached MF source tracks bound:", ["short_0085", "short_0274"])


if __name__ == "__main__":
    main()
