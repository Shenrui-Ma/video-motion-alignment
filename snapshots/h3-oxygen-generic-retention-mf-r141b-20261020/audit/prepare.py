"""CPU-only manifest binding; reuse the deployed official MF runtime unchanged."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / "h3-oxygen-online-recovery-mf-host41-r138-20261020"
CONSUMER = ROOT.parent / "h3-oxygen-generic-retention-metrics-r141b-host9-20261020"
REMOTE = "/data4/researcher/h3_runs/ive_oxygen_generic_retention_mf_r141b_20261020"
EXPECTED_SEAL = "2039321f1b4fa9103fd6376ae2592f2c684c17669aaa36b002b858e3d9076590"
CHECKPOINT = "da09bbac871f7398e5b29c4de5213652658949737bc158840b101678ba8ad1df"
COMMIT = "2dcf8900ee65197f43854c76f61c66a32bb8dbfc"
CROP = "crop=1280:720:16:8,trim=end_frame=98,setsar=1"
FFMPEG = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def bound(p):
    return {"file": str(p), "sha256": sha(p)}


def save(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def link(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        os.link(src, dst)
    assert sha(src) == sha(dst), f"Existing binding changed: {dst}"


def bound_input(path, paired):
    m = read(path)
    assert m["producer_seal_sha256"] == EXPECTED_SEAL
    assert m["source_id"] == "short_0252"
    assert m["valid_frames"] == 98 and m["total_frames"] == 107
    assert m["fps"] == 24 and m["crop_xywh"] == [16, 8, 1280, 720]
    assert m["evaluation_indices"] == list(range(98))
    assert set(m["raw_videos"]) == ({"source", "native", "forced"} if paired else {"source", "native"})
    assert sha(m["gate"]["file"]) == m["gate"]["sha256"]
    assert sha(m["collection"]["file"]) == m["collection"]["sha256"]
    gate = read(m["gate"]["file"])
    assert gate["passed"] is True
    # R141b intentionally preserves the frozen R123 gate schema.
    assert gate["schema"] == ("r123-paired-runtime-gate-v1" if paired else "r123-native-runtime-gate-v1")
    for role in ("native", "forced") if paired else ("native",):
        run = gate["runs"][role]
        assert run["run_id"] == f"r141_short_0252_seed2026101703_{role}"
        assert run["NFE"] == run["Euler_updates"] == 20
        assert run["routed_blocks"] == (450 if role == "forced" else 0)
        assert run["valid_frames"] == 98
        assert run["video"]["sha256"] == m["raw_videos"][role]["sha256"]
    for value in m["raw_videos"].values():
        assert sha(value["file"]) == value["sha256"]
    return m, gate


def prepare(paired_path=None, release_path=None, complete_path=None, gpu=None, inventory_id=None, peer_roots=()):
    assert not (ROOT / "SEAL.json").exists(), "Final frozen package must not be overwritten"
    native_path = CONSUMER / "prepared/short_0252/native/MF_INPUTS.json"
    native, _ = bound_input(native_path, False)
    for p in (BASE / "scripts").glob("*.py"):
        link(p, ROOT / "scripts" / p.name)
    for name in ("verify_inputs.py", "collect.py", "final_release.py"):
        link(BASE / "audit" / name, ROOT / "audit" / name)
    if not (ROOT / "runtime").exists():
        (ROOT / "runtime").symlink_to(BASE / "runtime", target_is_directory=True)
    for name in ("ive_NUMERIC.json", "EXISTING_SERVICES.json"):
        link(BASE / "configs" / name, ROOT / "configs" / name)
    protected = read(ROOT / "configs/EXISTING_SERVICES.json")["processes"]
    assert len(protected) == 1
    assert protected[0]["pid"] == 1646285 and protected[0]["uid"] == 1004
    assert str(protected[0]["start_ticks"]) == "20299235"
    assert protected[0]["gpu_uuid"] == "GPU-REDACTED"
    assert "--port 8189" in protected[0]["cmdline"]
    runtime = read(BASE / "configs/RUNTIME.json")
    assert len(peer_roots) <= 1
    assert all(p.startswith("/data4/researcher/h3_runs/") and ".." not in Path(p).parts for p in peer_roots)
    runtime.update(remote_root=REMOTE, gpu=gpu, peer_roots=list(peer_roots), status="CPU_PREPARED_NOT_AUTHORIZED")
    save(ROOT / "configs/RUNTIME.json", runtime)
    sys.path.insert(0, str(ROOT / "runtime/ive/metric_runtime"))
    from ive_mf_adapter import frame_hashes, media_info, validate_time_view

    old_case = BASE / "cases/short_0252"
    old = read(old_case / "INPUTS.json")
    assert native["raw_videos"]["source"]["sha256"] == old["source_full_sha256"]
    case = ROOT / "cases/short_0252"
    for rel in ("source_full.mp4", "source_score.mp4", "tracks/source/REPORT.json", "tracks/source/tracks.npz"):
        link(old_case / rel, case / rel)
    report = read(case / "tracks/source/REPORT.json")
    assert report["passed"] and report["official_commit"] == COMMIT
    assert report["checkpoint_sha256"] == CHECKPOINT
    assert sha(case / "tracks/source/REPORT.json") == old["source_cache"]["report_sha256"]
    assert sha(case / "tracks/source/tracks.npz") == report["tracks_sha256"] == old["source_cache"]["tracks_sha256"]
    assert report["effective_frame_count"] == 98
    assert report["tracker"] == {"grid_size": 10, "grid_query_frame": 0, "backward_tracking": False, "offline": True, "window_len": 60}
    assert report["source_prepared_sha256"] == old["source_full_sha256"]
    assert report["source_score_sha256"] == old["source_score_sha256"]
    assert report["decoded_frame_md5"] == old["source_frame_md5"]
    assert report["selection_sha256"] == old["selection_sha256"]
    assert frame_hashes(case / "source_score.mp4", FFMPEG) == old["source_frame_md5"]
    assert frame_hashes(native["raw_videos"]["source"]["file"], FFMPEG, CROP) == old["source_frame_md5"]
    validate_time_view(media_info(case / "source_score.mp4", FFPROBE), 98)
    save(ROOT / "audit/SOURCE_CACHE_VERIFIED.json", {
        "passed": True, "consumer_input": bound(native_path),
        "source_full_sha256": old["source_full_sha256"],
        "cache": bound(old_case / "INPUTS.json"),
        "report": bound(case / "tracks/source/REPORT.json"),
        "tracks": bound(case / "tracks/source/tracks.npz"),
        "exact_98_frame_crop_pixels_and_PTS": True,
        "checkpoint_sha256": CHECKPOINT, "official_commit": COMMIT,
        "source_new_tracker_required": False,
    })
    mp, m = native_path, native
    if paired_path:
        assert release_path and complete_path and gpu and inventory_id
        assert gpu != protected[0]["gpu_uuid"], "Protected8189GPU cannot be selected"
        mp = Path(paired_path)
        m, gate = bound_input(mp, True)
        assert m["raw_videos"]["native"]["sha256"] == native["raw_videos"]["native"]["sha256"]
        assert m["raw_videos"]["source"]["sha256"] == old["source_full_sha256"]
        release, complete = read(release_path), read(complete_path)
        assert release["passed"] and release["process_absent"] and release["CUDA_allocation_absent"]
        assert {k: release["owner"][k] for k in ("pid", "identity")} == gate["service_owner"], "Producer owner/release generation mismatch"
        assert complete["passed"] is True and complete["all_sources_reviewed"] is True
        assert complete["GPU_released"] is True
        assert complete["remaining_sources"] == []
    targets = []
    for role in ("native", "forced") if paired_path else ("native",):
        v = m["raw_videos"][role]
        link(Path(v["file"]), case / role / "full.mp4")
        score = case / role / "score.mp4"
        if not score.exists():
            subprocess.run([FFMPEG, "-v", "error", "-threads", "2", "-i", v["file"],
                            "-an", "-vf", CROP, "-vsync", "0", "-c:v", "libx264",
                            "-qp", "0", "-preset", "fast", "-pix_fmt", "yuv420p",
                            "-threads", "2", str(score)], check=True)
        pixels = frame_hashes(score, FFMPEG)
        assert pixels == frame_hashes(v["file"], FFMPEG, CROP)
        validate_time_view(media_info(score, FFPROBE), 98)
        t = dict(role=role, full_file=f"{role}/full.mp4", full_sha256=v["sha256"],
                 score_file=f"{role}/score.mp4", score_sha256=sha(score),
                 score_frame_md5=pixels, evaluation_indices=list(range(98)),
                 inventory_bindings=[] if not inventory_id else [{"id": inventory_id, "field": "native" if role == "native" else "guided"}],
                 actual_consumer_input=bound(mp), actual_runtime_gate=m["gate"])
        if paired_path:
            t["actual_producer_release"] = bound(Path(release_path))
        targets.append(t)
    manifest = {k: old[k] for k in ("benchmark", "canonical_id", "valid_frames", "evaluation_frames",
        "evaluation_fps", "source_full_sha256", "source_score_sha256", "source_frame_md5",
        "source_cache", "selection_sha256", "crop_xywh")}
    manifest.update(schema="r141b-native-fixed-official-mf-inputs-v1",
                    source_cache_domain_proof=bound(ROOT / "audit/SOURCE_CACHE_VERIFIED.json"), targets=targets)
    save(case / "INPUTS.json", manifest)
    for tag, path in [("NATIVE_MF_INPUTS.json", native_path), ("CONSUMER_CONTRACT.json", CONSUMER / "configs/contract.json")]:
        link(path, ROOT / "configs/evidence" / tag)
    if paired_path:
        for tag, path in [("PAIRED_MF_INPUTS.json", mp), ("PAIR_RUNTIME_GATE.json", Path(m["gate"]["file"])),
                          ("COLLECTION.json", Path(m["collection"]["file"])),
                          ("ROOT_EXIT_RECEIPT.json", Path(release_path)), ("COMPLETE.json", Path(complete_path))]:
            link(path, ROOT / "configs/evidence" / tag)
    save(ROOT / "configs/PLAN.json", {
        "groups": ["short_0252"],
        "jobs": [{"case": "short_0252", "role": t["role"]} for t in targets],
        "unique_targets": len(targets), "source_cache_count": 1,
        "expected_final_roles": ["native", "forced"],
        "status": "ACTUAL_PAIR_READY_NOT_AUTHORIZED" if paired_path else "DRAFT_WAITING_FORCED_AND_RELEASE",
    })
    reuse = {"runtime": "/data4/researcher/h3_runs/ive_reference_phase_mf_20261020/runtime"}
    for rel in ("source_full.mp4", "source_score.mp4", "tracks/source/REPORT.json", "tracks/source/tracks.npz"):
        reuse["cases/short_0252/" + rel] = "/data4/researcher/h3_runs/ive_r113_seed_replication_mf_20261020/cases/short_0252/" + rel
    save(ROOT / "audit/REMOTE_REUSE_PLAN.json", reuse)
    files = {}
    for top in ("scripts", "configs", "cases"):
        for p in (ROOT / top).rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                files[str(p.relative_to(ROOT))] = sha(p)
    for rel, h in read(BASE / "SEAL.json")["files"].items():
        if rel.startswith("runtime/"):
            assert sha(ROOT / rel) == h
            files[rel] = h
    for name in ("prepare.py", "materialize_existing.py", "verify_inputs.py", "collect.py", "final_release.py"):
        files["audit/" + name] = sha(ROOT / "audit" / name)
    seal_path = ROOT / ("SEAL.json" if paired_path else "PREPARATION_SEAL.json")
    save(seal_path, {"schema": "r141b-official-mf-package-v1", "final_inputs_bound": bool(paired_path), "files": files})
    upload = [rel for rel in files if not rel.startswith("runtime/") and rel not in reuse]
    upload += ["SEAL.json", "audit/REMOTE_REUSE_PLAN.json"]
    (ROOT / "audit/DEPLOY_FILES_AFTER_FINALIZE.txt").write_text("\n".join(upload) + "\n")
    scripts = list((ROOT / "scripts").glob("*.py"))
    assert all(sha(p) == sha(BASE / "scripts" / p.name) for p in scripts)
    assert "torch" not in sys.modules
    save(ROOT / "audit/CPU_PREPARATION.json", {
        "passed": True, "final_inputs_bound": bool(paired_path), "seal": bound(seal_path),
        "identical_execution_scripts": len(scripts), "source_cache_reused": True,
        "available_target_roles": [t["role"] for t in targets],
        "required_final_target_roles": ["native", "forced"], "expected_new_trackers": 2,
        "protected_service_policy": bound(ROOT / "configs/EXISTING_SERVICES.json"),
        "runtime_reused_from": str(BASE / "runtime"), "local_checkpoint_absent_expected": True,
        "target_checkpoint_validation_required": True, "GPU_started": False,
        "network_access_used": False, "root_admission_and_authorization_required": True,
    })
    print(json.dumps(read(ROOT / "audit/CPU_PREPARATION.json")))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--paired-input")
    p.add_argument("--release")
    p.add_argument("--complete")
    p.add_argument("--gpu")
    p.add_argument("--inventory-id")
    p.add_argument("--peer-root", action="append", default=[])
    a = p.parse_args()
    prepare(a.paired_input, a.release, a.complete, a.gpu, a.inventory_id, a.peer_root)
