"""Ten-task source/media-verified showcase; existing media stays in place."""
import argparse
import base64
import html
import json
import sys
from pathlib import Path
from common import ROOT, bound, read, write, require, verify_record, resolve_controls

OLD = ROOT.with_name("h3-guidance-schedule-eval-r149-20261020")
sys.path.append(str(OLD))
ARMS = ("early", "late", "split", "global_weak")
ROLES = ("source", "native", "early", "fixed", "late", "split", "global_weak")
TITLES = {
    "short_0252": "角色替换 — 机舱男性替换年长女性",
    "short_0358": "外观编辑 — 给饮酒男子戴眼镜",
    "05_real_megumi_v": "角色替换 — Sam Altman复现书记舞",
    "long_0039": "物体改色 — 书本封面改蓝",
    "long_0059": "物体添加 — 手中添加白手帕",
    "short_0085": "外观编辑 — 将窗边女子的头发改红",
    "short_0274": "角色替换 — 将宇航员替换为外星人",
    "musk05": "角色替换 — Musk复现书记舞",
    "firefly06": "角色替换 — 流萤复现动画书记舞",
    "sam07": "角色替换 — Sam Altman复现床边书记舞",
}
OLD_PROMPTS = {
    "short_0252": "沿用 R141b 三段 generic_retention 实验提示词",
    "short_0358": "沿用 R123 六段 full_context 实验提示词",
    "05_real_megumi_v": "沿用历史 Sam 人像参考＋真人舞蹈实验提示词",
}


def schedule_svg():
    rows = [
        ("早段 1–9", set(range(1, 10)), 1),
        ("原固定 7–15", set(range(7, 16)), 1),
        ("晚段 12–20", set(range(12, 21)), 1),
        ("分段 1–4＋16–20", {1, 2, 3, 4, 16, 17, 18, 19, 20}, 1),
        ("全程弱引导", set(range(1, 21)), .25),
    ]
    parts = ['<svg viewBox="0 0 1060 222" role="img" aria-label="二十步引导区间；颜色深浅表示实际引导强度">',
             '<style>text{font-family:system-ui,sans-serif;fill:#293546;font-size:13px}</style>']
    for step in range(1, 21):
        parts.append(f'<text x="{192 + (step-1)*38}" y="18" text-anchor="middle">{step}</text>')
    for index, (label, steps, alpha) in enumerate(rows):
        y = 32 + index * 36
        parts.append(f'<text x="0" y="{y+18}">{html.escape(label)}</text>')
        for step in range(1, 21):
            fill = "#276ea8" if alpha == 1 else "#b8d5ec"
            parts.append(f'<rect x="{176+(step-1)*38}" y="{y}" width="32" height="25" rx="3" '
                         f'fill="{fill if step in steps else "#edf0f3"}" '
                         f'data-step="{step}" data-alpha="{alpha if step in steps else 0}"/>')
        parts.append(f'<text x="952" y="{y+18}">α={alpha:g}</text>')
    parts.append("</svg>")
    return "".join(parts)


def media_url(record, embed):
    verify_record(record)
    path = Path(record["file"])
    if not embed:
        return path.as_uri()
    mime = "video/mp4" if path.suffix.lower() == ".mp4" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def number_score(value):
    return value.get("score") if isinstance(value, dict) else value


def collect_case(base, case, embed, final, evidence):
    if base == ROOT:
        case = resolve_controls(case)
    sid = case["source_id"]
    task_id = case.get("candidate_id", sid)
    row = dict(id=task_id, source_id=sid, title=TITLES.get(task_id, TITLES.get(sid, case["title"])),
               dataset=case.get("dataset") or ("IVEBench" if sid.startswith(("short_", "long_")) else "自有素材"),
               geometry=case["geometry"], seed=case["seed"], prompt=case["prompt"],
               prompt_source_label=OLD_PROMPTS.get(sid, case.get("prompt_source_label", "沿用历史实际实验提示词")),
               reference_image=bool(case.get("reference_image")), events=case["events"],
               old_MF={r: number_score(case["official_MF"][r]) for r in ("native", "fixed")},
               control_verdicts={r: "历史已审阅" for r in ("native", "fixed")},
               control_reviews={},
               arms={}, overview=None, pending=False,
               preservation=case.get("native_timing_status") == "no_clear_delay_preservation_control")
    if any(case["media"].get(r) is None for r in ("native", "fixed")):
        require(not final, "Current-cache controls missing")
        return dict(row, pending=True, reason="等待同缓存普通编辑与固定 7–15 对照成片")
    for role in ("native", "fixed"):
        if role in case.get("new_control_roles", []):
            row["control_verdicts"][role] = None
            review_path = base / "review" / sid / role / "REVIEW.json"
            if review_path.exists():
                review = read(review_path)
                require(review["actual_video"] == case["media"][role], "Control review differs")
                if review.get("review_completed"):
                    row["control_verdicts"][role] = review["task_verdict"]
                    row["control_reviews"][role] = review
                    evidence.append(bound(review_path))
            if final:
                require(row["control_verdicts"][role] is not None,
                        "Current-cache control requires completed quality review")
        score_path = base / "scores" / sid / (role + ".json")
        if score_path.exists():
            score = read(score_path)
            require(score["actual_generated_video_sha256"] == case["media"][role]["sha256"]
                    and score["role"] == role
                    and score["valid_frames"] == case["geometry"]["valid_frames"],
                    "Control score differs from the displayed current-cache media")
            row["old_MF"][role] = score["score"]
            evidence.append(bound(score_path))
        if final and sid in {"musk05", "firefly06", "sam07"}:
            require(score_path.exists(), "Dance control MF is missing")
    labels = read(ROOT / "EVENT_DISPLAY_LABELS.json")["cases"].get(sid, {})
    for event in row["events"]:
        event["label"] = labels.get(event["id"], event["label"])
    overview_path = base / "overview" / sid / "PRESENTATION.json"
    if overview_path.exists():
        overview = read(overview_path)
        require(overview["roles"] == list(ROLES) and overview["full_decode_passed"]
                and overview["valid_frames"] == case["geometry"]["valid_frames"]
                and overview["fps"] == case["geometry"]["fps"], "Overview order or frame domain differs")
        expected = []
        for role in ROLES:
            if role in ("source", "native", "fixed"):
                expected.append(case["media"][role])
            else:
                expected.append(read(base / "review" / sid / role / "PRESENTATION.json")["new_video"])
        require(overview["inputs"] == expected, "Overview contains different condition media")
        grid_path = ROOT / "overview_grid_controls" / sid / "PRESENTATION.json"
        require(grid_path.exists(), "Missing three-row display video")
        grid = read(grid_path)
        require(grid["schema"] == "r150-native-controls-bottom-space-v3"
                and grid["control_padding_bottom"] == 80
                and grid["source_presentation"] == bound(overview_path)
                and grid["source_video"] == overview["video"]
                and grid["roles"] == list(ROLES)
                and grid["full_decode_passed"]
                and grid["valid_frames"] == overview["valid_frames"]
                and grid["fps"] == overview["fps"], "Grid video differs from the verified comparison")
        selection_path = ROOT / "DEFAULT_SCREENSHOT_FRAMES.json"
        default_frame = read(selection_path)["cases"][sid]["frame"]
        require(default_frame in [x["frame"] for x in overview["screenshots"]], "Default screenshot is unavailable")
        row["overview"] = dict(video=media_url(grid["video"], embed), default_frame=default_frame,
            frames=[dict(frame=x["frame"], url=media_url(x, embed)) for x in overview["screenshots"]])
        evidence.extend([bound(grid_path), bound(selection_path)])
        evidence.append(bound(overview_path))
    for arm in ARMS:
        folder = base / "review" / sid / arm
        entry = dict(status="待生成", review=None, score=None, sampling_seconds=None)
        if (folder / "PRESENTATION.json").exists():
            presentation = read(folder / "PRESENTATION.json")
            require(presentation["source_id"] == sid and presentation["schedule"] == arm,
                    "Wrong per-arm presentation")
            proof = presentation["validated_execution"]
            for key in ("gate", "binding"):
                verify_record(proof[key])
            require(proof["run_record"] == read(proof["gate"]["file"])
                    and proof["run_record"]["video"]["sha256"] == presentation["new_video"]["sha256"],
                    "Rendered video differs from actual gate")
            verify_record(presentation["new_video"])
            entry["status"] = "已生成 · 待审阅"
            entry["sampling_seconds"] = proof["run_record"]["sampler_timing"]["sampler_wall_seconds"]
            entry["schedule_parameters"] = {
                key: proof["run_record"].get(key)
                for key in ("alpha", "physical_query_window",
                            "actual_routed_steps_zero_based", "sigma_selected",
                            "sum_abs_delta_sigma")
            }
            review_path = folder / "REVIEW.json"
            if review_path.exists():
                review = read(review_path)
                require(review["actual_video"] == presentation["new_video"], "Review media mismatch")
                entry["review"] = review
                entry["status"] = "已审阅 · 待评分"
                evidence.append(bound(review_path))
            score_path = base / "scores" / sid / (arm + ".json")
            if score_path.exists():
                score = read(score_path)
                require(score["actual_generated_video_sha256"] == presentation["new_video"]["sha256"]
                        and score["role"] == arm and score["valid_frames"] == case["geometry"]["valid_frames"],
                        "Score media or frame-domain mismatch")
                entry["score"] = score["score"]
                if entry["review"]:
                    entry["status"] = "已审阅 · 已评分"
                evidence.append(bound(score_path))
            batch = base / "actual" / sid / "BATCH_RELEASE.json"
            if batch.exists():
                if base == ROOT:
                    from finalize_batch import verify_batch_record
                    verify_batch_record(batch, case, read(proof["binding"]["file"]), proof["run_record"])
                else:
                    # Old completed R149 media/releases were independently audited before export.
                    require(read(batch).get("passed") is True, "Historical release not passed")
                evidence.append(bound(batch))
            if final:
                require(batch.exists() and entry["review"] and entry["review"].get("review_completed")
                        and entry["score"] is not None, "Final output missing review, score or release")
            evidence.append(bound(folder / "PRESENTATION.json"))
        elif final:
            raise ValueError(f"Missing final output: {sid}/{arm}")
        row["arms"][arm] = entry
    if final:
        require(row["overview"], "Missing seven-column final media")
    return row


def build(embed=False, final=False):
    evidence = []
    for record in read(ROOT / "EVALUATION_FREEZE.json")["files"]:
        verify_record(record)
    for record in read(ROOT / "audit/REUSE_ADAPTER.json")["records"]:
        verify_record(dict(file=record.get("file", record["source"]),
                           sha256=record.get("sha256", record["source_sha256"])))
    selected = read(ROOT / "SELECTED_TASKS.json")
    old, new = read(OLD / "EVALUATION_MANIFEST.json"), read(ROOT / "EVALUATION_MANIFEST.json")
    data = dict(title="引导步区间对照 · 10 项任务 / 9 条参考视频",
                roles=ROLES, cases=[], final=final, tasks=10, independent_sources=9)
    from summarize_tasks import collect as collect_outcomes
    data["outcomes"] = collect_outcomes()
    if final:
        require(data["outcomes"]["status"] == "complete", "Final outcome reviews are incomplete")
    evidence.append(bound(ROOT / "audit/TASK_OUTCOME_SUMMARY.json"))
    for case in old["cases"]:
        data["cases"].append(collect_case(OLD, case, embed, final, evidence))
    for task in selected["selected"]:
        case = next((x for x in new["cases"]
                     if x.get("candidate_id", x["source_id"]) == task["candidate_id"]), None)
        if case is None:
            case = next((x for x in new["cases"] if x["source_id"] == task["source_id"]), None)
        if case:
            data["cases"].append(collect_case(ROOT, case, embed, final, evidence))
        else:
            require(not final, "A selected task has no actual producer/evaluation binding")
            data["cases"].append(dict(id=task["candidate_id"], title=task["task"],
                                     source_id=task["source_id"], pending=True,
                                     reason="准备相同输入条件的普通编辑与各引导版本"))
    require(len(data["cases"]) == 10 and len({c["id"] for c in data["cases"]}) == 10,
            "Ten distinct tasks required")
    from display_metrics import add_display_metrics
    source_scores = ROOT / "SOURCE_SELF_MF.json"
    control_verdicts = ROOT / "HISTORICAL_CONTROL_VERDICTS.json"
    ranking = add_display_metrics(data, read(source_scores), read(control_verdicts))
    evidence.extend([bound(source_scores), bound(control_verdicts)])
    write(ROOT / "audit/DISPLAY_RANKING.json", ranking)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    template = (ROOT / "showcase_template.html").read_text()
    require(template.count("__DATA__") == template.count("__SCHEDULE_SVG__") == 1, "Template markers differ")
    output = ROOT / ("R150_十组引导区间对照_单文件.html" if embed else "index.html")
    output.write_text(template.replace("__DATA__", payload).replace("__SCHEDULE_SVG__", schedule_svg()))
    write(ROOT / "audit/SHOWCASE_SOURCE_QA.json",
          dict(html=bound(output), tasks=10, independent_sources=9, order=ROLES, final=final,
               embedded=embed, media_evidence=evidence, browser_rendered=False,
               scope="HTML source structure, SHA bindings and existing full-decode records; no browser rendering QA."))
    print(output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--embed", action="store_true")
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    build(args.embed, args.final)
