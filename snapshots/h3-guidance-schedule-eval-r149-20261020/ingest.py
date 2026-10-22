"""Validate one explicit completed producer run, then make its four-column media."""
import argparse
from fractions import Fraction
from pathlib import Path, PurePosixPath
import subprocess
from common import (ROOT, FFMPEG, FONT, bound, read, write, require, verify_record,
                    inspect, dimensions, case_and_schedule, expected_router)


def validate_job(case, schedule, binding, run):
    require(binding.get("status") == "READY", "Actual producer contract is not bound yet")
    require(binding["source_id"] == case["source_id"] and
            binding["schedule"] == schedule["id"], "Wrong case or schedule")
    require(binding["steps_0based"] == schedule["steps_0based"] and
            binding["phase_offset"] == 0, "Schedule/phase differs from frozen evaluation")
    require(binding["historical_prompt_sha256"] == case["prompt_sha256"] and
            binding["historical_noise_sha256"] == case["historical_initial_noise"]["sha256"] and
            binding["historical_fixed_graph_sha256"] ==
            case["historical_runs"]["fixed"]["graph"]["sha256"], "Historical controls differ")
    verify_record(binding["producer_seal"])
    verify_record(binding["producer_verifier"])
    verify_record(binding["producer_runtime"])
    require(run.get("schema") == "r149-schedule-job-gate-v1" and run.get("passed") is True,
            "Successful per-job R149 gate required")
    require(run.get("producer_seal_sha256") == binding["producer_seal"]["sha256"] and
            run.get("run_id") == binding["run_id"] and run.get("role") == schedule["id"],
            "Gate producer/run/role differs")
    router = expected_router(case, schedule)
    expected = {"NFE": 20, "Euler_updates": 20,
                "routed_blocks": len(schedule["steps_0based"]) * 50, "alpha": router["alpha"],
                "phase_displacement": 0, "actual_routed_steps_zero_based": schedule["steps_0based"],
                "valid_frames": case["geometry"]["valid_frames"],
                "evaluation_crop_xywh": case["geometry"]["crop_xywh"],
                "physical_query_window": [router["start_frame"], router["end_frame"]],
                "noise_sha256": case["historical_initial_noise"]["sha256"]}
    for key, value in expected.items():
        require(run.get(key) == value, "Scientific execution field differs: " + key)
    timing = run["sampler_timing"]
    require(timing["passed"] is True and timing["run_id"] == binding["run_id"] and
            timing["sampler_wall_seconds"] > 0 and
            [x["step_zero_based"] for x in timing["callback_steps"]] == list(range(20)),
            "Actual sampler timing incomplete")
    require(run.get("binding_artifacts") and run.get("final_latent") and
            run.get("service_owner"), "Runtime evidence is incomplete")
    require(run["service_owner"].get("gpu_uuid") == binding["gpu_uuid"] and
            run["service_owner"].get("port") == binding["port"], "Actual owner differs from sealed runtime")
    remote = PurePosixPath(binding["remote_root"]) / "output"
    actual = PurePosixPath(run["video"]["file"])
    require(actual.is_relative_to(remote) and ".." not in actual.parts,
            "Actual video must belong to this producer output directory")
    return run


def validate_batch(case, binding, run, gate, complete, release, gate_sha):
    require(gate.get("schema") == "r149-fixed-schedule-runtime-gate-v1" and
            gate.get("passed") is True and gate.get("source_id") == case["source_id"] and
            gate.get("producer_seal_sha256") == binding["producer_seal"]["sha256"] and
            gate.get("same_persistent_service") is True and gate.get("phase_displacement") == 0,
            "Successful batch gate required")
    arms = ("early", "late", "split", "global_weak")
    require(set(gate["runs"]) == set(arms) and
            gate["runs"][binding["role"]] == run, "Batch does not bind this exact per-job record")
    owner = run["service_owner"]
    require(gate["service_owner"] == owner and all(
        row.get("passed") is True and row.get("service_owner") == owner
        for row in gate["runs"].values()), "Batch service generation differs")
    order = [f"r149_{case['source_id']}_seed{case['seed']}_{arm}" for arm in arms]
    require(complete.get("schema") == "r149-schedule-completion-v1" and
            complete.get("passed") is True and complete.get("jobs") == order and
            complete.get("remaining") == [] and complete.get("GPU_released") is True and
            complete.get("runtime_gate_sha256") == gate_sha and complete.get("service_owner") == owner,
            "Batch completion does not bind the gate/owner/four jobs")
    cleanup = release.get("cleanup", {})
    require(release.get("owner") == owner and release.get("passed") is True and
            release.get("process_absent") is True and release.get("CUDA_allocation_absent") is True and
            cleanup.get("pid") == owner["pid"] and cleanup.get("process_absent") is True and
            cleanup.get("own_compute_absent") is True, "Exact service release incomplete")


def validate(case, schedule, video, gate_path, binding_path):
    binding = read(binding_path)
    run = validate_job(case, schedule, binding, read(gate_path))
    require(bound(video)["sha256"] == run["video"]["sha256"], "Actual output SHA differs")
    g = case["geometry"]
    expected = (g["width"], g["height"], g["sampled_frames"], Fraction(g["fps"]))
    require(dimensions(run["video"]["properties"]) == expected and dimensions(inspect(video)) == expected,
            "Output geometry, frame count or fps differs")
    for item in case["media"].values():
        verify_record(item)
        require(dimensions(inspect(item["file"])) == expected, "Historical geometry differs")
    return {"run_id": run["run_id"], "role": binding["role"], "run_record": run,
            "video": bound(video), "gate": bound(gate_path), "binding": bound(binding_path),
            "status": "PER_JOB_VERIFIED_BATCH_RELEASE_PENDING"}


def render(case, schedule, proof):
    from PIL import Image, ImageDraw, ImageFont
    g = case["geometry"]
    dest = ROOT / "review" / case["source_id"] / schedule["id"]
    dest.mkdir(parents=True, exist_ok=False)
    media = [case["media"][r] for r in ("source", "native", "fixed")] + [proof["video"]]
    new_label = "全局弱引导 α=0.25" if schedule["id"] == "global_weak" else "时序引导 " + schedule["label"]
    labels = ["参考视频", "普通编辑", "时序引导 7–15", new_label]
    footer = Image.new("RGB", (2560, 64), "black")
    font = ImageFont.truetype(FONT, 28)
    draw = ImageDraw.Draw(footer)
    for i, text in enumerate(labels):
        draw.text((i * 640 + (640 - draw.textlength(text, font=font)) / 2, 13),
                  text, font=font, fill="white")
    caption = dest / "caption.png"
    footer.save(caption)
    x, y, w, h = g["crop_xywh"]
    vf = (f"crop={w}:{h}:{x}:{y},scale=640:360:force_original_aspect_ratio=decrease:"
          "force_divisible_by=2:flags=lanczos,pad=640:360:(ow-iw)/2:(oh-ih)/2:black")
    cmd = [FFMPEG, "-v", "error", "-nostdin", "-n"]
    for item in media:
        cmd += ["-threads", "1", "-i", item["file"]]
    cmd += ["-loop", "1", "-framerate", "24", "-i", str(caption)]
    filters = [f"[{i}:v]{vf},trim=end_frame={g['valid_frames']},setpts=PTS-STARTPTS,setsar=1[v{i}]"
               for i in range(4)]
    filters += ["[v0][v1][v2][v3]hstack=inputs=4:shortest=1[images]",
                "[images][4:v]vstack=inputs=2:shortest=1[out]"]
    output = dest / "comparison.mp4"
    cmd += ["-filter_complex_threads", "2", "-filter_complex", ";".join(filters), "-map", "[out]",
            "-frames:v", str(g["valid_frames"]), "-an", "-c:v", "libx264", "-crf", "18",
            "-preset", "fast", "-pix_fmt", "yuv420p", "-threads", "2", "-movflags", "+faststart", str(output)]
    subprocess.run(cmd, check=True, timeout=600)
    require(int(inspect(output)["nb_read_frames"]) == g["valid_frames"], "Comparison frame count differs")
    subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-n", "-threads", "1", "-i", str(output),
                    "-fps_mode", "passthrough", "-start_number", "0", "-q:v", "2",
                    str(dest / "frame_%03d.jpg")], check=True, timeout=90)
    result = {"schema": "r149-fourway-media-v1", "source_id": case["source_id"],
        "schedule": schedule["id"], "labels": labels, "evaluation_manifest": bound(ROOT / "EVALUATION_MANIFEST.json"),
        "validated_execution": proof, "video": bound(output), "new_video": proof["video"],
        "screenshots": [{**bound(dest / f"frame_{i:03d}.jpg"), "frame": i}
                        for i in range(g["valid_frames"])], "valid_frames": g["valid_frames"],
        "fps": g["fps"], "full_frame_review_complete": False}
    write(dest / "PRESENTATION.json", result)
    write(dest / "REVIEW_TEMPLATE.json", {"status": "PENDING_FULL_FRAME_REVIEW",
        "review_completed": False, "actual_video": proof["video"], "task_verdict": None, "events": case["events"],
        "historical_window_diagnostics": case.get("historical_window_diagnostics"),
        "summary_zh": None, "identity_pose_ghosting_observations": [],
        "additional_whole_video_observations": [], "sampling_seconds_actual": None})
    print(str(dest / "PRESENTATION.json"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--schedule", choices=("early", "late", "split", "global_weak"), required=True)
    for key in ("video", "gate"):
        p.add_argument("--" + key, type=Path, required=True)
    p.add_argument("--binding", type=Path)
    p.add_argument("--validate-only", action="store_true")
    a = p.parse_args()
    _, case, schedule = case_and_schedule(a.case, a.schedule)
    schedule = dict(schedule, id=a.schedule)
    binding = a.binding or ROOT / "runtime" / a.case / (a.schedule + ".json")
    proof = validate(case, schedule, a.video, a.gate, binding)
    if a.validate_only:
        print("Validated " + proof["run_id"])
    else:
        render(case, schedule, proof)


if __name__ == "__main__":
    main()
