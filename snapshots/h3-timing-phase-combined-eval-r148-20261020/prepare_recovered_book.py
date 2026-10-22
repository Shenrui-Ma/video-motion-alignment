"""Accept the separately verified final-only decode; preserve the interrupted run."""
import argparse
from fractions import Fraction
from pathlib import Path, PurePosixPath

from prepare_comparison import ROOT, bound, dimensions, inspect, read, render, require, validate_media

BINDING_SHA = "dbd3c9a1080f0ecc971b5d0015d7ffc5a5b824622e3cffb7ad6428b9d5ba6fc2"
SCRIPT_SHA = "3d09e52b8e71162bac2a6f1d4744dc0b471c5d09c87b1ab1006dd4934cc5bcef"
FINAL_SHA = "1e9107ee6c8ea82cfc34e9222601bcec61f0131a7f261c1f2f32b609a5a655f9"


def validate_recovery(case, video, gate_path, result_path, release_path, binding_path):
    require(case["source_id"] == "long_0039", "Only the explicitly reviewed book recovery is supported")
    require(bound(binding_path)["sha256"] == BINDING_SHA, "Recovery source binding differs")
    d, gate, result, release = map(read, (binding_path, gate_path, result_path, release_path))
    producer = Path(case["R148"]["producer_case"])
    seal = bound(producer / "deploy_manifest.json")
    contract = read(producer / "configs/scientific_contract.json")
    spec = contract["cases"][0]
    require(spec["prompt_sha256"] == case["prompt_sha256"]
            and contract["parent_noise_sha256"] == case["historical_initial_noise"]["sha256"]
            and spec["video_sha256"] == case["media"]["source"]["sha256"], "Historical inputs differ")
    run = case["R148"]["run_id"]
    require(d["schema"] == "r148-book-final-decode-binding-v1" and d["run_id"] == run
            and d["producer_seal_sha256"] == seal["sha256"] and d["new_dit_forwards"] == 0,
            "Recovery lineage differs")
    require(gate["schema"] == "r148-book-final-decode-recovery-gate-v1" and gate["passed"] is True
            and gate["run_id"] == run and gate["role"] == "fixed_phase"
            and gate["producer_seal_sha256"] == seal["sha256"]
            and gate["binding_sha256"] == BINDING_SHA
            and gate["source_attempt"] == d["source_attempt"]
            and gate["source_attempt_complete"] is False
            and gate["new_dit_forwards"] == 0 and gate["valid_frames"] == 106,
            "Recovery gate or interrupted-attempt status differs")
    require(bound(result_path)["sha256"] == gate["decode_result"]["sha256"]
            and bound(release_path)["sha256"] == gate["release"]["sha256"], "Recovery receipt changed")
    require(result["schema"] == "r148-book-final-decode-result-v1" and result["passed"] is True
            and result["run_id"] == run and result["role"] == "fixed_phase"
            and result["binding_sha256"] == BINDING_SHA
            and result["recovery_script_sha256"] == SCRIPT_SHA
            and result["producer_seal_sha256"] == seal["sha256"], "Decode result differs")
    owner = gate["decoder_owner"]
    require(owner["uid"] == 1004 and owner["pid"] > 0
            and all(owner.get(k) for k in ("start_ticks", "cmdline_sha256", "boot_id"))
            and result["decoder_owner"] == release["decoder_owner"] == owner, "Decoder generation differs")
    require(release["schema"] == "r148-book-decode-release-v1" and release["exit_code"] == 0
            and release["process_absent"] is True and release["own_cuda_absent"] is True
            and release["released"] is True and release["failure"] is None, "Decoder release incomplete")
    source = gate["source"]
    require(source == result["source"], "Decode source proof differs")
    for key, rel in (
        ("snapshot", f"audit/x0/{run}/sampler_final.pt"),
        ("manifest", f"audit/x0/{run}/manifest.json"),
        ("router", f"audit/router/{run}.json"),
    ):
        require(source[key] == d["files"][rel], "Original sampler artifact differs: " + key)
    require(source["snapshot"]["sha256"] == FINAL_SHA
            and source["original_nfe"] == 20 and source["original_routed_calls"] == 450
            and source["original_attention_calls"] == 1000 and source["new_dit_forwards"] == 0,
            "Original sampling or new computation count differs")
    meta = source["metadata"]
    require(meta["snapshot_kind"] == "sampler_final"
            and meta["sigma_video"] == meta["sigma_audio"] == 0
            and meta["normalization_stage"] == "after_process_latent_out"
            and meta["run_id"] == run and meta["seed"] == case["seed"]
            and meta["total_steps"] == 20 and meta["geometry"] == d["geometry"],
            "True normalized sampler endpoint required")
    actual = gate["video"]
    remote_file = PurePosixPath(actual["file"])
    recovery_root = PurePosixPath(d["case_root"]) / "audit/recovery_decode"
    require(".." not in remote_file.parts and remote_file.is_relative_to(recovery_root)
            and remote_file.name == run + "_recovered.mp4", "Unrelated recovered output")
    require(actual == result["video"] and actual["bytes"] > 0
            and actual["bytes"] == Path(video).stat().st_size
            and actual["sha256"] == bound(video)["sha256"], "Recovered video differs")
    props = actual["properties"]
    require((props["width"], props["height"], props["frames"], Fraction(props["fps"])) ==
            (1312, 736, 107, Fraction(24)), "Recovered geometry differs")
    require(dimensions(inspect(video)) == (1312, 736, 107, Fraction(24)), "Actual video geometry differs")
    require(result["native_audio_preserved"] is True and result["valid_frames"] == 106
            and result["crop"] is None, "Native decode output domain differs")
    return dict(validation_mode="independent_final_decode_recovery",
                combined_video=bound(video), gate=bound(gate_path), decode_result=bound(result_path),
                release=bound(release_path), source_binding=bound(binding_path), seal=seal,
                run_id=run, source_attempt_complete=False, new_dit_forwards=0,
                run_record=dict(run_id=run, video=actual, NFE=20, Euler_updates=20,
                                routed_blocks=450, original_rope_table_blocks=1000,
                                valid_frames=106, evaluation_crop_xywh=[16, 8, 1280, 720],
                                execution_note="20 historical sampler steps; independently released final-only decode; 0 new DiT",
                                recovery_decode_seconds=result["finished_unix"] - result["started_unix"]))


def main():
    p = argparse.ArgumentParser()
    for flag in ("video", "gate", "result", "release", "source-binding"):
        p.add_argument("--" + flag, type=Path, required=True)
    p.add_argument("--validate-only", action="store_true")
    a = p.parse_args()
    case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"] if c["source_id"] == "long_0039")
    proof = validate_recovery(case, a.video, a.gate, a.result, a.release, a.source_binding)
    if a.validate_only:
        validate_media(case, a.video)
        print({"passed": True, "validation_mode": proof["validation_mode"], "new_dit_forwards": 0})
    else:
        render(case, a.video, proof)


if __name__ == "__main__":
    main()
