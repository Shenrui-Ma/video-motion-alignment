"""Read completed evidence; write only this R148 evaluation directory."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT.parent


def read(path):
    return json.loads(Path(path).read_text())


def bound(path):
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return {"file": str(p), "sha256": h.hexdigest()}


def phases(events):
    result = []
    for a, b in zip(events, events[1:]):
        p = {"from": a["id"], "to": b["id"], "fixed_phase": None}
        for role in ("source", "native", "fixed"):
            p[role] = {"duration_frames_range": [b[role][0] - a[role][1], b[role][1] - a[role][0]],
                       "midpoint_frames": (sum(b[role]) - sum(a[role])) / 2}
        result.append(p)
    return result


def main():
    previous = PROJECTS / "h3-reference-origin-positive-eval-r146-20261020/EVALUATION_MANIFEST.json"
    cases = copy.deepcopy(read(previous)["cases"])
    for c in cases:
        c.pop("R146")
        # Pose is historical evidence only; the new experiment has no online observer.
        c.pop("source_pose", None)
        c["official_MF"].pop("reference_origin")
        c["sampling_seconds"].pop("reference_origin")
        for e in c["events"]:
            e.pop("reference_origin")
    for sid, title, mfdir, fixed_role, checks in [
        ("long_0039", "书本：将封面改为蓝色", "h3-ive-context-mf-host41-20261020", "forced",
         ["蓝色书封成立", "人物、桌面、电脑和拿书动作链保留"]),
        ("long_0059", "手帕：在手中添加白手帕", "h3-ive-reference-phase-mf-host41-20261020", "guided",
         ["白手帕编辑成立", "原人物、场景、擦眼与撤手动作保留"])]:
        bp = PROJECTS / f"h3-threecase-auto-r144-20261020/input_audit/{sid}_BINDING.json"
        b = read(bp)
        cp = Path(b["consumer"])
        rp = cp / f"audit/full_frame_review/{sid}/paired/REVIEW.json"
        review = read(rp)
        events = []
        for e in review["events"]:
            events.append({"id": e.get("id", e["name"]), "label": e["name"],
                           **{r: e[old]["frames"] for r, old in
                              (("source", "source"), ("native", "native"), ("fixed", "forced"))}})
        mf = PROJECTS / mfdir / "audit/RESULTS_VERIFIED.json"
        scores = {}
        for role, old in (("native", "native"), ("fixed", fixed_role)):
            s = next(x for x in read(mf)["results"] if x["case"] == sid and x["role"] == old)
            assert s["actual_generated_video_sha256"] == b["runs"]["native" if role == "native" else "forced"]["local_video"]["sha256"]
            scores[role] = {"score": s["score"], "actual_role": old, "result": bound(s["result_file"])}
        cases.append({"source_id": sid, "title": title, "seed": b["seed"],
                      "historical_consumer": str(cp), "geometry": b["geometry"],
                      "media": {"source": b["source"],
                                **{r: dict(b["runs"][old]["local_video"],
                                           producer_remote_file=b["runs"][old]["remote_video"]["file"])
                                   for r, old in (("native", "native"), ("fixed", "forced"))}},
                      "remote41_media_cache_pointers": b["remote41_cache_candidates"],
                      "prompt": b["prompt"], "prompt_sha256": b["prompt_sha256"],
                      "events": events, "historical_review": bound(rp),
                      "historical_pair_gate": b["actual_pair_gate"], "historical_MF_receipt": bound(mf),
                      "official_MF": scores, "historical_input_binding": bound(bp), "task_checks": checks,
                      "sampling_seconds": {"native": None, "fixed": None}})
    for c in cases:
        sid, cp = c["source_id"], Path(c["historical_consumer"])
        gate = read(c["historical_pair_gate"]["file"])
        assert bound(c["historical_pair_gate"]["file"]) == c["historical_pair_gate"]
        graphs = {}
        for role, old in (("native", "native"), ("fixed", "forced")):
            run = gate["runs"][old]
            gp = cp / "configs/graphs" / (run["run_id"] + ".json")
            graph = read(gp)
            graphs[role] = {"run_id": run["run_id"], "graph": bound(gp),
                            "router_node_50": graph["50"], "actual_run": run}
            assert graph["5"]["inputs"]["prompt"] == c["prompt"]
            assert bound(c["media"][role]["file"])["sha256"] == c["media"][role]["sha256"]
        assert bound(c["media"]["source"]["file"])["sha256"] == c["media"]["source"]["sha256"]
        assert hashlib.sha256(c["prompt"].encode()).hexdigest() == c["prompt_sha256"]
        noise = [{"file": gate["runtime_profile"]["remote_root"] + "/" + rel, "sha256": sha}
                 for rel, sha in gate["runs"]["native"]["binding_artifacts"].items()
                 if rel.endswith("_noise.pt")]
        assert len(noise) == 1
        c["historical_runs"] = graphs
        c["historical_initial_noise"] = noise[0]
        c["historical_source_remote"] = gate["runtime_profile"]["remote_root"] + "/input/" + sid + "_video.mp4"
        c["official_MF"]["fixed_phase"] = None
        c["sampling_seconds"]["fixed_phase"] = None
        c["timing"] = {"historical_job_wall_seconds": {r: gate["runs"][old]["job_wall_seconds"]
                       for r, old in (("native", "native"), ("fixed", "forced"))},
                      "historical_capture_seconds": {r: gate["runs"][old].get("capture_seconds")
                       for r, old in (("native", "native"), ("fixed", "forced"))}}
        c["timing_rule"] = "Measure sampling from actual timestamps, separately from loading, capture and decode; do not divide job wall by 20."
        for e in c["events"]:
            e["fixed_phase"] = None
        c["phases"] = phases(c["events"])
        c["R148"] = {"status": "PENDING_NOT_GENERATED", "role": "fixed_phase",
                     "run_id": f"r148_{sid}_seed{c['seed']}_fixed_phase",
                     "producer_case": str(PROJECTS / "h3-timing-phase-combined-r148-20261020/cases" / sid),
                     "runtime_binding": str(ROOT / "runtime" / (sid + ".json")),
                     "producer_seal": None, "completion": None}
    manifest = {"schema": "r148-fourway-evaluation-v1", "status": "PREDECLARED_AWAITING_R148",
                "prior_preparation": bound(previous), "prior_R146_status": "DEPRECATED_BEFORE_LAUNCH_0_NFE",
                "roles": ["source", "native", "fixed", "fixed_phase"],
                "method_labels": {"source": "参考视频", "native": "普通编辑", "fixed": "时序引导",
                                  "fixed_phase": "时序引导＋相位对齐"},
                "method": "Combined output retains each historical fixed router's exact window/bin/alpha/step/block parameters; only the auxiliary reference-attention Q gains actual-origin temporal phase alignment. Original joint attention remains unchanged.",
                "index_base": 0, "interval_semantics": "Inclusive observed event transition frames.",
                "evaluation_rules": ["Task completion and preserved scene/action before timing.",
                    "Use frozen event definitions; missing events remain null.",
                    "Compare event errors and all adjacent phase durations using shared source event times.",
                    "Reuse old MF values and only evaluate new completed output once.",
                    "No per-step VAE/RGB/pose observer and no added observer metrics.",
                    "No user-report, old inventory or producer mutation."],
                "cases": cases}
    out = ROOT / "EVALUATION_MANIFEST.json"
    if out.exists():
        raise FileExistsError(out)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(bound(out)))


if __name__ == "__main__":
    main()
