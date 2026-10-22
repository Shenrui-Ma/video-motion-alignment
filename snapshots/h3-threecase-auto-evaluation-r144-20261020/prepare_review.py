"""Render matched physical frames from the registered inputs and a finished auto run."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FFMPEG = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"
FONT = "/System/Library/Fonts/PingFang.ttc"


def bound(path):
    path = Path(path)
    return {"file": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def inspect(path):
    return json.loads(subprocess.check_output([
        FFPROBE, "-v", "error", "-select_streams", "v:0", "-count_frames",
        "-show_entries", "stream=width,height,nb_read_frames,avg_frame_rate",
        "-of", "json", str(path),
    ]))["streams"][0]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_automatic(case, automatic, run_receipt, runtime_gate, root_exit):
    """Verify the local copies of the producer's completion and release chain."""
    run_receipt, runtime_gate, root_exit = map(Path, (run_receipt, runtime_gate, root_exit))
    exit_reference = runtime_gate.with_name("ROOT_EXIT_REFERENCE.json")
    records = {name: bound(path) for name, path in (
        ("completion", run_receipt), ("runtime_gate", runtime_gate),
        ("root_exit", root_exit), ("exit_reference", exit_reference),
    )}
    complete, gate, release, reference = (
        json.loads(path.read_text())
        for path in (run_receipt, runtime_gate, root_exit, exit_reference)
    )
    run = f"r144_{case['source_id']}_seed{case['seed']}_visible_only"
    require(complete.get("passed") is True and complete.get("run_id") == run
            and complete.get("no_followup_submission") is True,
            "Completed R144 run receipt required")
    require(complete.get("gate_sha256") == records["runtime_gate"]["sha256"],
            "Completion receipt does not bind this runtime gate")
    require(gate.get("schema") == "r86-online-runtime-gate-v1"
            and gate.get("status") == "pass" and gate.get("passed") is True
            and gate.get("cleanup_verified") is True and gate.get("partial_batch") is False,
            "Successful complete online runtime gate required")
    require(gate.get("verified_runs") == [run] and len(gate.get("cases", [])) == 1,
            "Runtime gate belongs to another run or batch")
    result = gate["cases"][0]
    require(result.get("run") == run and result.get("arm") == "visible_only"
            and result.get("updates") == 20 and result.get("observations") == 20,
            "Runtime gate lacks the complete automatic run")

    owner = gate["service_record"]
    require(release.get("passed") is True and release.get("service") == owner,
            "Root exit receipt belongs to another service generation")
    cleanup = release["service_cleanup"]
    require(cleanup.get("pid") == owner["pid"] and cleanup.get("service_record") == owner
            and cleanup.get("process_absent") is True
            and cleanup.get("own_compute_absent") is True,
            "Main service release incomplete")
    children = release["observer_children"]
    require(children.get("all_exact_generations_absent") is True
            and children.get("all_registered_CUDA_pids_absent") is True,
            "Observer child release incomplete")
    if "cached_conditioning" in gate:
        require(gate["cached_conditioning"].get("actual_tensors_exact") is True
                and gate["capacity_trial"].get("normal_monitor_exit") is True
                and gate["capacity_trial"].get("samples", 0) > 0,
                "Cached-condition capacity gate incomplete")
        monitor = release["capacity_monitor"]
        require(monitor.get("exit_code") == 0
                and monitor.get("exact_generation_absent") is True,
                "Capacity monitor release incomplete")

    command = owner["command"]
    require(command.count("--base-directory") == 1, "Ambiguous producer root")
    remote_root = PurePosixPath(command[command.index("--base-directory") + 1])
    attempt = owner["root_attempt_token"]
    require(remote_root.is_absolute() and ".." not in remote_root.parts
            and isinstance(attempt, str) and re.fullmatch(r"root_[A-Za-z0-9_]+", attempt),
            "Invalid producer root or attempt identity")
    require(reference.get("sha256") == records["root_exit"]["sha256"]
            and reference.get("file") == str(remote_root / "audit" / attempt / "ROOT_EXIT_RECEIPT.json"),
            "Runtime exit reference does not bind this attempt's release")

    video = gate["video"]
    remote_video = PurePosixPath(video["file"])
    require(".." not in remote_video.parts and remote_video.is_relative_to(remote_root / "output")
            and remote_video.name.startswith(run + "_") and remote_video.suffix == ".mp4",
            "Gate video is outside the completed run")
    automatic_record = bound(automatic)
    require(automatic_record["sha256"] == video.get("sha256"),
            "Automatic video SHA differs from runtime gate")
    geometry = case["geometry"]
    expected = (geometry["width"], geometry["height"], geometry["sampled_frames"],
                Fraction(str(geometry["fps"])))
    actual = inspect(automatic)
    for label, properties in (("gate", video["properties"]), ("actual", actual)):
        dimensions = (int(properties["width"]), int(properties["height"]),
                      int(properties["nb_read_frames"]), Fraction(properties["avg_frame_rate"]))
        require(dimensions == expected, f"{label} automatic geometry/timebase differs from plan")
    require(gate.get("valid_frames") == geometry["valid_frames"],
            "Automatic valid-frame domain differs from plan")
    return {**records, "run_id": run, "attempt": attempt, "producer_root": str(remote_root),
            "automatic": {**automatic_record, "producer_file": video["file"], "properties": actual},
            "verified_before_render": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--automatic", required=True, type=Path)
    parser.add_argument("--run-receipt", required=True, type=Path,
                        help="Local COMPLETE_REVIEW_HOLD.json from the successful attempt")
    parser.add_argument("--runtime-gate", required=True, type=Path,
                        help="Local ONLINE_RUNTIME_GATE.json; keep ROOT_EXIT_REFERENCE.json beside it")
    parser.add_argument("--root-exit", type=Path,
                        help="Local ROOT_EXIT_RECEIPT.json (defaults beside --run-receipt)")
    args = parser.parse_args()
    plan = json.loads((ROOT / "EVALUATION_PLAN.json").read_text())
    case = next(c for c in plan["cases"] if c["source_id"] == args.case)
    binding = Path(case["input_binding"])
    assert bound(binding)["sha256"] == case["input_binding_sha256"]
    automatic_binding = validate_automatic(
        case, args.automatic.resolve(), args.run_receipt, args.runtime_gate,
        args.root_exit or args.run_receipt.with_name("ROOT_EXIT_RECEIPT.json"),
    )
    media = [Path(case[r]["file"]) for r in ("source", "native", "fixed")]
    for role, path in zip(("source", "native", "fixed"), media):
        assert bound(path)["sha256"] == case[role]["sha256"], role
    media.append(args.automatic.resolve())
    g = case["geometry"]
    for path in media:
        info = inspect(path)
        assert (int(info["width"]), int(info["height"])) == (g["width"], g["height"])
        assert int(info["nb_read_frames"]) >= g["valid_frames"]
        n, d = map(int, info["avg_frame_rate"].split("/"))
        assert n / d == g["fps"]
    dest = ROOT / "review" / args.case
    dest.mkdir(parents=True, exist_ok=False)
    crop = g["crop_xywh"]
    crop_filter = f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]}"
    frames, fps = g["valid_frames"], g["fps"]
    font = ImageFont.truetype(FONT, 26)
    videos = []
    for label, last in (("fixed", 2), ("automatic", 3)):
        captions = ("1.参考视频", "2.普通编辑", "3.固定时序引导" if last == 2 else "3.自动时序引导")
        cap = Image.new("RGB", (1920, 52), "black")
        draw = ImageDraw.Draw(cap)
        for i, text in enumerate(captions):
            draw.text((i * 640 + (640 - draw.textlength(text, font=font)) / 2, 10), text, font=font, fill="white")
        cp = dest / f"{label}_caption.png"
        cap.save(cp)
        out = dest / f"source_native_{label}.mp4"
        cmd = [FFMPEG, "-v", "error", "-nostdin", "-n"]
        for path in (media[0], media[1], media[last]):
            cmd += ["-threads", "1", "-i", str(path)]
        cmd += ["-framerate", str(fps), "-loop", "1", "-i", str(cp)]
        filters = [f"[{i}:v]{crop_filter},trim=end_frame={frames},setpts=PTS-STARTPTS,scale=640:360:flags=lanczos,setsar=1[v{i}]" for i in range(3)]
        filters += ["[v0][v1][v2]hstack=inputs=3:shortest=1[images]", "[images][3:v]vstack=inputs=2:shortest=1[out]"]
        cmd += ["-filter_complex_threads", "2", "-filter_complex", ";".join(filters), "-map", "[out]", "-frames:v", str(frames), "-an", "-fps_mode", "vfr", "-c:v", "libx264", "-crf", "19", "-preset", "fast", "-pix_fmt", "yuv420p", "-threads", "2", "-movflags", "+faststart", str(out)]
        subprocess.run(cmd, check=True, timeout=300)
        info = inspect(out)
        assert int(info["nb_read_frames"]) == frames
        videos.append({"role": label, **bound(out), "properties": info})

    readers = []
    pages = []
    width, height, row_height = 320, 180, 204
    labels = ("参考视频", "普通编辑", "固定引导", "自动引导")
    face = ImageFont.truetype(FONT, 14)
    try:
        for path in media:
            readers.append(subprocess.Popen([FFMPEG, "-v", "error", "-nostdin", "-threads", "1", "-i", str(path), "-vf", f"{crop_filter},scale={width}:{height}:flags=lanczos", "-frames:v", str(frames), "-f", "rawvideo", "-pix_fmt", "rgb24", "-threads", "1", "-"], stdout=subprocess.PIPE))
        for start in range(0, frames, 8):
            indices = list(range(start, min(start + 8, frames)))
            canvas = Image.new("RGB", (width * 4, row_height * len(indices)), "black")
            draw = ImageDraw.Draw(canvas)
            for row, index in enumerate(indices):
                for col, proc in enumerate(readers):
                    raw = proc.stdout.read(width * height * 3)
                    assert len(raw) == width * height * 3, "Missing physical frame"
                    canvas.paste(Image.frombytes("RGB", (width, height), raw), (col * width, row * row_height))
                    draw.text((col * width + 5, row * row_height + height + 3), f"{index:03d} | {index / fps:.3f}s | {labels[col]}", font=face, fill="white")
            out = dest / f"frames_{indices[0]:03d}_{indices[-1]:03d}.jpg"
            canvas.save(out, quality=91)
            pages.append({**bound(out), "physical_frames": indices})
        for proc in readers:
            assert not proc.stdout.read(1)
            assert proc.wait(timeout=30) == 0
    finally:
        for proc in readers:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=10)
    receipt = {"source_id": args.case, "evaluation_plan": bound(ROOT / "EVALUATION_PLAN.json"), "run_receipt": bound(args.run_receipt), "automatic_binding": automatic_binding, "inputs": [bound(p) for p in media], "columns": list(labels), "crop_xywh": crop, "valid_frames": frames, "fps": fps, "videos": videos, "pages": pages, "frames_prepared": True, "frames_inspected": False}
    (dest / "FRAME_LEDGER.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(json.dumps({"case": args.case, "frames": frames, "review": str(dest)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
