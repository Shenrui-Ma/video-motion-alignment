"""Build a local or embedded page from exact media pointers; no browser automation."""
import argparse
import base64
import json
import statistics
from pathlib import Path
from common import ROOT, bound, read, write, require, verify_record
from finalize_batch import verify_batch_record

DISPLAY_TITLES = {
    "short_0252": "角色替换 — 机舱男性替换年长女性",
    "05_real_megumi_v": "角色替换 — Sam Altman复现书记舞",
    "short_0358": "外观编辑 — 给饮酒男子戴眼镜",
}


def media_url(record, embed):
    verify_record(record)
    path = Path(record["file"])
    if embed:
        mime = "video/mp4" if path.suffix == ".mp4" else "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()
    return path.as_uri()


def build(embed=False, final=False):
    manifest = read(ROOT / "EVALUATION_MANIFEST.json")
    plan = read(ROOT / "EVALUATION_PLAN.json")
    for item in read(ROOT / "EVALUATION_FREEZE.json")["files"]:
        verify_record(item)
    data = {"title": "引导步区间与全局弱引导 · R149",
            "schedules": manifest["schedules"], "global_weak_meaning": manifest["global_weak_meaning"],
            "cases": [], "final": final}
    used = []
    for case in manifest["cases"]:
        sid = case["source_id"]
        source_plan = next(c for c in plan["cases"] if c["source_id"] == sid)
        row = {k: case.get(k) for k in ("source_id", "title", "dataset", "seed", "geometry",
                    "prompt", "prompt_source_label", "events", "historical_window_diagnostics")}
        row["title"] = DISPLAY_TITLES[sid]
        row["old_MF"] = {role: case["official_MF"][role]["score"] for role in ("native", "fixed")}
        row["reference_image"] = "使用 Sam 人像参考图" if case.get("reference_image") else "无人物参考图"
        row["sigma_spans"] = manifest["sigma_spans"]["values"][sid]
        row["arms"] = {}
        for arm in manifest["schedules"]:
            folder = ROOT / "review" / sid / arm
            pres_path = folder / "PRESENTATION.json"
            review_path = folder / "REVIEW.json"
            score_path = ROOT / "scores" / sid / (arm + ".json")
            entry = {"status": "等待实际新成片", "video": None, "frames": [], "review": None,
                     "score": None, "event_summary": None}
            if pres_path.exists():
                pres = read(pres_path)
                require(pres["source_id"] == sid and pres["schedule"] == arm, "Wrong presentation")
                entry["video"] = media_url(pres["video"], embed)
                entry["status"] = "单条已验收；整组释放待绑定"
                entry["sampling_seconds"] = pres["validated_execution"]["run_record"]["sampler_timing"]["sampler_wall_seconds"]
                entry["sampling_scope"] = "实际 sampler wall，含本次捕获/审计回调；与 job 装载/解码总耗时分列。"
                timing = pres["validated_execution"]["run_record"]["sampler_timing"]
                intervals = [step["callback_interval_seconds"] for step in timing["callback_steps"]]
                entry["step_seconds"] = {"first_callback_interval": intervals[0],
                    "later_callback_interval_median": statistics.median(intervals[1:]),
                    "later_callback_interval_range": [min(intervals[1:]), max(intervals[1:])],
                    "scope": "同步捕获后相邻 callback 的实际间隔，含先前 Euler 与当前预测/审计；首步含 sampler setup。"}
                entry["frames"] = [{"frame": item["frame"], "url": media_url(item, embed)}
                                   for item in pres["screenshots"] if item["frame"] in source_plan["representative_frames"]]
                batch = ROOT / "actual" / sid / "BATCH_RELEASE.json"
                if batch.exists():
                    proof = pres["validated_execution"]
                    verify_batch_record(batch, case, read(proof["binding"]["file"]), proof["run_record"])
                    entry["status"] = "成片已验收，整组已精确释放"
                    used.append(bound(batch))
                if review_path.exists():
                    review = read(review_path)
                    require(review["actual_video"] == pres["new_video"], "Review belongs to a different video")
                    entry["review"] = review
                    used.append(bound(review_path))
                summary_path = folder / "EVENT_SUMMARY.json"
                if summary_path.exists():
                    summary = read(summary_path)
                    require(summary["review"] == bound(review_path), "Event summary uses an outdated review")
                    entry["event_summary"] = summary
                    used.append(bound(summary_path))
                if score_path.exists():
                    score = read(score_path)
                    require(score["actual_generated_video_sha256"] == pres["new_video"]["sha256"] and
                            score["role"] == arm and score["valid_frames"] == case["geometry"]["valid_frames"],
                            "Official score belongs to another video/domain")
                    entry["score"] = score["score"]
                    used.append(bound(score_path))
                used.extend([bound(pres_path), pres["video"]])
                if final:
                    require(batch.exists() and entry["review"] and entry["review"].get("review_completed") is True
                            and entry["score"] is not None, "Final export requires review, score and release for " + sid + "/" + arm)
            elif final:
                raise ValueError("Final export requires every requested case/schedule output")
            row["arms"][arm] = entry
        data["cases"].append(row)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    template = (ROOT / "template.html").read_text()
    require(template.count("__DATA__") == 1, "Template data marker must be unique")
    html = template.replace("__DATA__", payload)
    output = ROOT / ("R149_引导步区间对照_单文件.html" if embed else "index.html")
    output.write_text(html)
    write(ROOT / "audit/HTML_SOURCE_QA.json", {
        "scope": "HTML source structure and exact asset hashes only; no browser execution or visual UI claim.",
        "html": bound(output), "cases": len(data["cases"]),
        "selector_options_per_case": len(manifest["schedules"]), "embedded": embed,
        "ready_videos": sum(bool(a["video"]) for c in data["cases"] for a in c["arms"].values()),
        "final": final, "evidence": used,
        "headless_browser_or_HTTP_workaround_used": False})
    print(str(output))
    return output


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--embed", action="store_true")
    p.add_argument("--final", action="store_true")
    a = p.parse_args()
    build(a.embed, a.final)
