"""CPU manifests and lossless scoring views; no network, model load or GPU."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT.parent
PROJECTS = EVAL.parent
BASE = PROJECTS / "h3-oxygen-generic-retention-mf-r141b-20261020"
REMOTE = "/data4/researcher/h3_runs/timing_phase_combined_mf_r148_20261020"
RUNTIME = "/data4/researcher/h3_runs/ive_reference_phase_mf_20261020/runtime"
SAM = "05_real_megumi_v"
IVE = ["short_0252", "short_0358", "long_0039", "long_0059"]
LOCAL = {
    "short_0252": BASE,
    "short_0358": PROJECTS / "h3-ive-context-mf-host41-20261020",
    "long_0039": PROJECTS / "h3-ive-context-mf-host41-20261020",
    "long_0059": PROJECTS / "h3-ive-reference-phase-mf-host41-20261020",
}
REMOTE_OLD = {
    "short_0252": "/data4/researcher/h3_runs/ive_oxygen_generic_retention_mf_r141b_20261020",
    "short_0358": "/data4/researcher/h3_runs/ive_context_mf_20261020",
    "long_0039": "/data4/researcher/h3_runs/ive_context_mf_20261020",
    "long_0059": "/data4/researcher/h3_runs/ive_reference_phase_mf_20261020",
}
sys.path.insert(0, str(EVAL))
from prepare_comparison import bound, read, validate
sys.path.insert(0, str(ROOT / "runtime/ive/metric_runtime"))
from ive_mf_adapter import frame_hashes, media_info, validate_time_view

FFMPEG = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"


def sha(p):
    return bound(p)["sha256"]


def save(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def link(src, dest):
    src, dest = Path(src), Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        os.link(src, dest)
    assert sha(src) == sha(dest), str(dest)


def score_view(src, dest, geometry):
    n = geometry["valid_frames"]
    x, y, w, h = geometry["crop_xywh"]
    vf = f"crop={w}:{h}:{x}:{y},trim=end_frame={n},setsar=1"
    if not dest.exists():
        subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-n", "-threads", "2",
                        "-i", str(src), "-an", "-vf", vf, "-fps_mode", "passthrough",
                        "-c:v", "libx264", "-qp", "0", "-preset", "fast",
                        "-pix_fmt", "yuv420p", "-threads", "2", str(dest)],
                       check=True, timeout=120)
    pixels = frame_hashes(dest, FFMPEG)
    assert pixels == frame_hashes(src, FFMPEG, vf)
    info = media_info(dest, FFPROBE)
    if (w, h) == (1280, 720):
        validate_time_view(info, n)
    else:
        # Sam's registered original domain is the complete 1312x736 frame.
        assert (w, h, n) == (1312, 736, 141)
        assert (info["width"], info["height"], info["count"]) == (w, h, n)
        assert all(abs(t - i / 24) < 1e-6 for i, t in enumerate(info["pts_s"]))
    return pixels


def prepare_case(c, reuse):
    sid, g = c["source_id"], c["geometry"]
    complete_inputs = True
    dest = ROOT / "cases" / sid
    dest.mkdir(parents=True, exist_ok=True)
    if sid in IVE:
        old = LOCAL[sid] / "cases" / sid
        original = read(old / "INPUTS.json")
        assert c["media"]["source"]["sha256"] == original["source_full_sha256"]
        for name in ("source_full.mp4", "source_score.mp4"):
            link(old / name, dest / name)
            reuse[f"cases/{sid}/{name}"] = REMOTE_OLD[sid] + f"/cases/{sid}/{name}"
        track_rel = (f"audit/actual_context_mf_attempt1/tracks/{sid}/source"
                     if sid == "long_0039" else f"cases/{sid}/tracks/source")
        for name in ("REPORT.json", "tracks.npz"):
            link(LOCAL[sid] / track_rel / name, dest / "tracks/source" / name)
            reuse[f"cases/{sid}/tracks/source/{name}"] = REMOTE_OLD[sid] + f"/{track_rel}/{name}"
        report = read(dest / "tracks/source/REPORT.json")
        assert report["passed"] is True
        assert report["checkpoint_sha256"] == "da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df"
        assert report["official_commit"] == "2dcf8900ee65197f43854c76f61c66a32bb8dbfc"
        assert report["tracks_sha256"] == sha(dest / "tracks/source/tracks.npz")
        assert report["source_prepared_sha256"] == sha(dest / "source_full.mp4")
        assert report["source_score_sha256"] == sha(dest / "source_score.mp4")
        assert report["effective_frame_count"] == g["valid_frames"]
        assert report["selection_sha256"] == original["selection_sha256"]
        assert report["tracker"] == dict(grid_size=10, grid_query_frame=0,
                                        backward_tracking=False, offline=True, window_len=60)
        pixels = score_view(dest / "source_full.mp4", dest / "source_score.mp4", g)
        assert pixels == report["decoded_frame_md5"] == original["source_frame_md5"]
        m = {k: original[k] for k in ("benchmark", "canonical_id", "valid_frames", "evaluation_frames",
             "evaluation_fps", "crop_xywh", "source_full_sha256", "source_score_sha256",
             "source_frame_md5", "selection_sha256")}
        m["source_cache"] = dict(report_sha256=sha(dest / "tracks/source/REPORT.json"),
                                tracks_sha256=report["tracks_sha256"])
        save(ROOT / "audit" / (sid + "_SOURCE_CACHE.json"),
             dict(passed=True, original_input=bound(old / "INPUTS.json"), exact_crop_pixels=True,
                  exact_PTS=True, report=bound(dest / "tracks/source/REPORT.json"),
                  checkpoint_sha256=report["checkpoint_sha256"]))
        presentation = EVAL / "review" / sid / "PRESENTATION.json"
        if not presentation.exists():
            return False
        p = read(presentation)
        proof = p["validated_execution"]
        video = p["inputs"]["fixed_phase"]
        if proof.get("validation_mode") == "independent_final_decode_recovery":
            from prepare_recovered_book import validate_recovery
            validate_recovery(c, video["file"], proof["gate"]["file"], proof["decode_result"]["file"],
                              proof["release"]["file"], proof["source_binding"]["file"])
            evidence_keys = ("gate", "decode_result", "release", "source_binding")
        else:
            validate(c, video["file"], proof["gate"]["file"], proof["complete"]["file"],
                     proof["release"]["file"], proof["runtime_binding"]["file"])
            evidence_keys = ("gate", "complete", "release", "runtime_binding")
        roles = {"fixed_phase": video}
        for key in evidence_keys:
            link(proof[key]["file"], ROOT / "configs/evidence" / sid / (key + ".json"))
        reuse[f"cases/{sid}/fixed_phase/full.mp4"] = proof["run_record"]["video"]["file"]
    else:
        source = c["media"]["source"]
        assert sha(source["file"]) == source["sha256"]
        link(source["file"], dest / "source_full.mp4")
        reuse[f"cases/{sid}/source_full.mp4"] = (
            "/data4/researcher/h3_runs/timing_phase_combined_r148_20261020/cases/"
            + sid + "/inputs/05_real_megumi_v.mp4")
        pixels = score_view(dest / "source_full.mp4", dest / "source_score.mp4", g)
        m = dict(benchmark="IVEBench", dataset_scope="Sam custom task; IVEBench official MF implementation",
                 canonical_id=sid, valid_frames=g["valid_frames"], evaluation_frames=g["valid_frames"],
                 evaluation_fps=g["fps"], crop_xywh=g["crop_xywh"],
                 source_full_sha256=source["sha256"], source_score_sha256=sha(dest / "source_score.mp4"),
                 source_frame_md5=pixels, source_cache=None, selection_sha256=sha(EVAL / "EVALUATION_MANIFEST.json"))
        roles = {r: c["media"][r] for r in ("native", "fixed")}
        presentation = EVAL / "review" / sid / "PRESENTATION.json"
        complete_inputs = presentation.exists()
        if complete_inputs:
            p = read(presentation)
            proof = p["validated_execution"]
            video = p["inputs"]["fixed_phase"]
            validate(c, video["file"], proof["gate"]["file"], proof["complete"]["file"],
                     proof["release"]["file"], proof["runtime_binding"]["file"])
            roles["fixed_phase"] = video
            for key in ("gate", "complete", "release", "runtime_binding"):
                link(proof[key]["file"], ROOT / "configs/evidence" / sid / (key + ".json"))
            reuse[f"cases/{sid}/fixed_phase/full.mp4"] = proof["run_record"]["video"]["file"]
    targets = []
    for role, video in roles.items():
        assert sha(video["file"]) == video["sha256"]
        link(video["file"], dest / role / "full.mp4")
        pixels = score_view(dest / role / "full.mp4", dest / role / "score.mp4", g)
        targets.append(dict(role=role, full_file=role + "/full.mp4", full_sha256=video["sha256"],
                            score_file=role + "/score.mp4", score_sha256=sha(dest / role / "score.mp4"),
                            score_frame_md5=pixels, evaluation_indices=list(range(g["valid_frames"])),
                            inventory_bindings=[dict(id=c["R148"]["run_id"], field=role)],
                            historical_media=(sid == SAM and role != "fixed_phase")))
    m.update(schema="r148-official-mf-inputs-v1", targets=targets)
    save(dest / "INPUTS.json", m)
    return complete_inputs


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--finalize", action="store_true")
    p.add_argument("--gpu")
    p.add_argument("--peer-root", action="append", default=[])
    a = p.parse_args()
    assert not (ROOT / "SEAL.json").exists(), "Do not overwrite a frozen batch"
    cases = read(EVAL / "EVALUATION_MANIFEST.json")["cases"]
    reuse = {"runtime": RUNTIME}
    ready = [c["source_id"] for c in cases if prepare_case(c, reuse)]
    jobs = [dict(case=sid, role="fixed_phase") for sid in IVE]
    jobs += [dict(case=SAM, role=role) for role in ("source", "native", "fixed", "fixed_phase")]
    save(ROOT / "configs/PLAN.json", dict(groups=IVE + [SAM], jobs=jobs, unique_targets=7,
         source_cache_count=4, status="FINAL_READY" if a.finalize else "CPU_PREPARATION_PENDING_OUTPUTS",
         pending_inputs=[s for s in IVE + [SAM] if s not in ready]))
    save(ROOT / "audit/REMOTE_REUSE_PLAN.json", reuse)
    runtime = read(BASE / "configs/RUNTIME.json")
    runtime.update(remote_root=REMOTE, gpu=a.gpu, peer_roots=a.peer_root,
                   status="ROOT_REVIEW_REQUIRED")
    save(ROOT / "configs/RUNTIME.json", runtime)
    if a.finalize:
        assert set(ready) == set(IVE + [SAM]), "All five outputs/release receipts are required"
        assert a.gpu and a.gpu.startswith("GPU-")
        assert len(a.peer_root) <= 1 and all(x.startswith("/data4/researcher/h3_runs/")
                   and ".." not in Path(x).parts for x in a.peer_root)
        files = {}
        for top in ("scripts", "configs", "cases"):
            for f in (ROOT / top).rglob("*"):
                if f.is_file() and "__pycache__" not in f.parts:
                    files[str(f.relative_to(ROOT))] = sha(f)
        for rel, h in read(BASE / "SEAL.json")["files"].items():
            if rel.startswith("runtime/"):
                assert sha(ROOT / rel) == h
                files[rel] = h
        for f in (ROOT / "audit").glob("*.py"):
            files[str(f.relative_to(ROOT))] = sha(f)
        files["ADMIN_DIFF.json"] = sha(ROOT / "ADMIN_DIFF.json")
        save(ROOT / "SEAL.json", dict(schema="r148-official-mf-batch-v1", final_inputs_bound=True, files=files))
        upload = [rel for rel in files if not rel.startswith("runtime/") and rel not in reuse]
        upload += ["SEAL.json", "audit/REMOTE_REUSE_PLAN.json"]
        (ROOT / "audit/DEPLOY_FILES.txt").write_text("\n".join(upload) + "\n")
    assert "torch" not in sys.modules
    result = dict(passed=True, ready=ready, planned_trackers=8, generated_scores=7,
                  source_caches=4, final_inputs_bound=a.finalize, GPU_started=False)
    save(ROOT / "audit/CPU_PREPARATION.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
