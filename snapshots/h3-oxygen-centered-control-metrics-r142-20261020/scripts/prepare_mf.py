"""Prepare one official MF target after intake. Existing tracker source/cache are reused."""
import argparse
import subprocess
from common import *


def prepare(remote_root):
    actual()
    require(remote_root.startswith("/data4/researcher/h3_runs/") and ".." not in Path(remote_root).parts,
            "explicit host41 task root required")
    old = Path(CONTRACT["mf_template"])
    template_seal=read(CONTRACT["mf_template_seal"]["file"])
    for rel,digest in template_seal["files"].items():
        require(sha(old/rel)==digest,"R138 MF template changed: "+rel)
    dest = ROOT / "mf"
    require(not dest.exists(), "MF inputs already prepared")
    dest.mkdir()
    for p in (old / "scripts").glob("*.py"):
        link(p, dest / "scripts" / p.name)
    for name in ("verify_inputs.py", "final_release.py", "collect.py"):
        link(old / "audit" / name, dest / "audit" / name)
    (dest / "runtime").symlink_to((old / "runtime").resolve(), target_is_directory=True)
    for name in ("ive_NUMERIC.json", "EXISTING_SERVICES.json"):
        link(old / "configs" / name, dest / "configs" / name)
    runtime = read(old / "configs/RUNTIME.json")
    runtime.update(remote_root=remote_root, gpu=None, peer_roots=[],
                   status="CPU_INPUT_READY_FRESH_RESOURCE_REVIEW_REQUIRED")
    save(dest / "configs/RUNTIME.json", runtime)
    case = dest / "cases/short_0252"
    prior_case = old / "cases/short_0252"
    prior = read(prior_case / "INPUTS.json")
    mp = read(ROOT / "prepared/MF_INPUTS.json")
    require(mp["full_videos"]["source"]["sha256"] == prior["source_full_sha256"], "MF source differs")
    for rel in ("source_full.mp4", "source_score.mp4", "tracks/source/REPORT.json", "tracks/source/tracks.npz"):
        link(prior_case / rel, case / rel)
    full = Path(mp["full_videos"]["centeredauto"]["file"])
    link(full, case / "centeredauto/full.mp4")
    score = case / "centeredauto/score.mp4"
    crop = "crop=1280:720:16:8,trim=end_frame=98,setsar=1"
    subprocess.run(["/opt/homebrew/bin/ffmpeg", "-v", "error", "-nostdin", "-n", "-threads", "2",
        "-i", str(full), "-an", "-vf", crop, "-fps_mode", "passthrough", "-c:v", "libx264",
        "-qp", "0", "-preset", "fast", "-pix_fmt", "yuv420p", "-threads", "2", str(score)],
        check=True, timeout=300)
    adapter = load_helper("mf_adapter")
    pixels = adapter.frame_hashes(score, "/opt/homebrew/bin/ffmpeg")
    require(pixels == adapter.frame_hashes(full, "/opt/homebrew/bin/ffmpeg", crop), "MF crop pixels changed")
    adapter.validate_time_view(adapter.media_info(score, "/opt/homebrew/bin/ffprobe"), 98)
    require(adapter.frame_hashes(case / "source_score.mp4", "/opt/homebrew/bin/ffmpeg")
            == prior["source_frame_md5"], "source cache pixel domain differs")
    manifest = {k:prior[k] for k in ("schema", "benchmark", "canonical_id", "valid_frames",
        "evaluation_frames", "evaluation_fps", "source_full_sha256", "source_score_sha256",
        "source_frame_md5", "source_cache", "selection_sha256", "crop_xywh")}
    manifest.update(schema="r142-centered-actual-mf-v1",
        source_cache_domain_proof=bound(ROOT/"historical/MF_SOURCE_CACHE_VERIFIED.json"),
        historical_reused_scores=read(ROOT/"prepared/MF_ROUTE.json")["historical_scores"],
        targets=[dict(role="centeredauto", full_file="centeredauto/full.mp4", full_sha256=sha(full),
            score_file="centeredauto/score.mp4", score_sha256=sha(score), score_frame_md5=pixels,
            evaluation_indices=list(range(98)), inventory_bindings=[dict(id=CONTRACT["run_id"],field="centeredauto")],
            actual_consumer_input=bound(ROOT/"prepared/MF_INPUTS.json"),
            actual_runtime_gate=bound(ROOT/"incoming/actual/ONLINE_RUNTIME_GATE.json"),
            actual_producer_release=bound(ROOT/"incoming/actual/ROOT_EXIT_RECEIPT.json"))])
    save(case/"INPUTS.json",manifest)
    save(dest/"configs/PLAN.json",dict(groups=["short_0252"],jobs=[dict(case="short_0252",role="centeredauto")],
         unique_targets=1,source_cache_count=1,status="ONE_ACTUAL_R142_TARGET_ONLY"))
    for p in (ROOT/"prepared/MF_INPUTS.json",ROOT/"incoming/actual/COLLECTION.json",
              ROOT/"incoming/actual/ONLINE_RUNTIME_GATE.json",ROOT/"incoming/actual/ROOT_EXIT_RECEIPT.json",
              ROOT/"historical/MF_SOURCE_CACHE_VERIFIED.json"):
        link(p,dest/"configs/evidence"/p.name)
    files={}
    for top in ("scripts","configs","cases","audit"):
        for p in (dest/top).rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                files[str(p.relative_to(dest))]=sha(p)
    for rel,digest in read(old/"SEAL.json")["files"].items():
        if rel.startswith("runtime/"):
            require(sha(dest/rel)==digest,"official runtime changed")
            files[rel]=digest
    save(dest/"SEAL.json",dict(schema="r142-one-actual-output-official-mf-v1",files=files))
    # Reuse runtime/source cache already on host41; only score view and small bindings need transfer.
    reuse=read(old/"audit/REMOTE_REUSE_PLAN.json")
    reuse={k:v for k,v in reuse.items() if k=="runtime" or k.startswith("cases/short_0252/source")
           or k.startswith("cases/short_0252/tracks/source")}
    save(dest/"audit/REMOTE_REUSE_PLAN.json",reuse)
    upload=[rel for rel in files if not rel.startswith("runtime/") and rel not in reuse]
    upload+=["SEAL.json","audit/REMOTE_REUSE_PLAN.json"]
    (dest/"audit/DEPLOY_FILES.txt").write_text("\n".join(upload)+"\n")
    save(dest/"audit/CPU_PREPARED.json",dict(passed=True,seal=bound(dest/"SEAL.json"),
         new_trackers=1,source_cache_reused=True,historical_scores_reused=True,GPU_started=False,
         upload_bytes=sum((dest/rel).stat().st_size for rel in upload),
         remaining="Root fresh resource/coexistence review, GPU admission, one tracker, exact release, result collection"))
    return bound(dest/"audit/CPU_PREPARED.json")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--remote-root",required=True);a=p.parse_args()
    print(json.dumps(prepare(a.remote_root)))
