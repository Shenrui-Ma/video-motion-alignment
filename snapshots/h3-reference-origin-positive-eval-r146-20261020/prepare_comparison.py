"""Render only a successfully completed, released and hash-bound R146 output."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parent
FFMPEG = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"


def read(path):
    return json.loads(Path(path).read_text())


def bound(path):
    path = Path(path)
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            h.update(block)
    return {"file": str(path), "sha256": h.hexdigest()}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def inspect(path):
    return json.loads(subprocess.check_output([
        FFPROBE, "-v", "error", "-select_streams", "v:0", "-count_frames",
        "-show_entries", "stream=width,height,nb_read_frames,avg_frame_rate",
        "-of", "json", str(path)]))["streams"][0]


def dimensions(p):
    return int(p["width"]), int(p["height"]), int(p["nb_read_frames"]), Fraction(p["avg_frame_rate"])


def validate(case, video, gate_path, complete_path, release_path, seal_path):
    gate, complete, release = map(read, (gate_path, complete_path, release_path))
    r = case["R146"]
    require(gate.get("schema") == "r132-reference-origin-runtime-gate-v1"
            and gate.get("passed") is True and gate.get("source_id") == case["source_id"],
            "Successful matching reference-origin gate required")
    require(gate.get("producer_seal_sha256") == bound(seal_path)["sha256"],
            "Actual producer seal differs")
    require(gate.get("checks") and all(v is True for v in gate["checks"].values()),
            "Every scientific/runtime check must pass")
    require(set(gate["runs"]) == {"reference_origin"}, "Unexpected run roles")
    run = gate["runs"]["reference_origin"]
    require(run.get("run_id") == r["run_id"] and run.get("NFE") == 20
            and run.get("Euler_updates") == 20 and run.get("routed_blocks") == 450
            and run.get("original_rope_table_blocks") == 1000,
            "Wrong run or incomplete reference-origin execution")
    g = case["geometry"]
    require(run.get("valid_frames") == g["valid_frames"]
            and run.get("evaluation_crop_xywh") == g["crop_xywh"], "Frame domain differs")
    require(complete.get("schema") == "r132-one-output-completion-v1"
            and complete.get("passed") is True and complete.get("jobs") == [r["run_id"]]
            and complete.get("remaining") == [] and complete.get("GPU_released") is True
            and complete.get("runtime_gate_sha256") == bound(gate_path)["sha256"],
            "Successful complete receipt must bind this gate")
    owner = gate["service_owner"]
    require(complete.get("service_owner") == owner and release.get("owner") == owner,
            "Service generation differs between receipts")
    cleanup = release.get("cleanup", {})
    require(release.get("passed") is True and release.get("process_absent") is True
            and release.get("CUDA_allocation_absent") is True
            and cleanup.get("pid") == owner["pid"] and cleanup.get("process_absent") is True
            and cleanup.get("own_compute_absent") is True, "Exact release incomplete")
    require(gate["runtime_profile"]["remote_root"] == r["remote_root"], "Producer root differs")
    remote_video = PurePosixPath(run["video"]["file"])
    require(".." not in remote_video.parts
            and remote_video.is_relative_to(PurePosixPath(r["remote_root"]) / "output")
            and remote_video.name.startswith(r["run_id"] + "_"), "Unexpected output path")
    record = bound(video)
    require(record["sha256"] == run["video"]["sha256"], "Phase video SHA differs")
    expected = (g["width"], g["height"], g["sampled_frames"], Fraction(g["fps"]))
    require(dimensions(run["video"]["properties"]) == expected
            and dimensions(inspect(video)) == expected, "Phase video geometry or timebase differs")
    return {"phase_video": record, "gate": bound(gate_path), "complete": bound(complete_path),
            "release": bound(release_path), "seal": bound(seal_path),
            "run_id": r["run_id"], "run_record": run}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case", choices=["short_0252", "short_0358"], required=True)
    p.add_argument("--phase", type=Path, required=True)
    p.add_argument("--gate", type=Path, required=True)
    p.add_argument("--complete", type=Path, required=True)
    p.add_argument("--release", type=Path, required=True)
    p.add_argument("--seal", type=Path, required=True)
    p.add_argument("--panels", choices=["3", "4"], default="3")
    p.add_argument("--frames", default="", help="Comma-separated physical frames; default full effective frame domain")
    p.add_argument("--validate-only", action="store_true")
    args = p.parse_args()
    manifest = read(ROOT / "EVALUATION_MANIFEST.json")
    case = next(c for c in manifest["cases"] if c["source_id"] == args.case)
    proof = validate(case, args.phase, args.gate, args.complete, args.release, args.seal)
    media = dict(case["media"], reference_origin=bound(args.phase))
    g = case["geometry"]
    for role, item in media.items():
        require(bound(item["file"])["sha256"] == item["sha256"], role + " media changed")
        require(dimensions(inspect(item["file"])) ==
                (g["width"], g["height"], g["sampled_frames"], Fraction(g["fps"])),
                role + " geometry differs")
    if args.validate_only:
        print(json.dumps({"passed": True, "run_id": proof["run_id"]}))
        return
    from PIL import Image, ImageDraw, ImageFont
    panels = int(args.panels)
    roles = ["source", "native", "reference_origin"] if panels == 3 else ["source", "native", "fixed", "reference_origin"]
    # 3x640 or 4x480 preserves a readable 1920px-wide comparison; captions only below.
    width, height = 1920 // panels, (1920 // panels) * 9 // 16
    dest = ROOT / "review" / args.case / f"{panels}panels"
    dest.mkdir(parents=True, exist_ok=False)
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 22)
    footer = Image.new("RGB", (1920, 54), "black")
    draw = ImageDraw.Draw(footer)
    for i, role in enumerate(roles):
        label = manifest["method_labels"][role]
        draw.text((i * width + (width - draw.textlength(label, font=font)) / 2, 12),
                  label, font=font, fill="white")
    caption = dest / "caption.png"
    footer.save(caption)
    crop = g["crop_xywh"]
    vf = f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]},scale={width}:{height}:flags=lanczos"
    cmd = [FFMPEG, "-v", "error", "-nostdin", "-n"]
    for role in roles:
        cmd += ["-threads", "1", "-i", media[role]["file"]]
    cmd += ["-loop", "1", "-framerate", "24", "-i", str(caption)]
    filters = [f"[{i}:v]{vf},trim=end_frame={g['valid_frames']},setpts=PTS-STARTPTS,setsar=1[v{i}]"
               for i in range(panels)]
    filters += ["".join(f"[v{i}]" for i in range(panels)) + f"hstack=inputs={panels}:shortest=1[images]",
                f"[images][{panels}:v]vstack=inputs=2:shortest=1[out]"]
    out = dest / "comparison.mp4"
    title = case["title"] + "｜" + " / ".join(manifest["method_labels"][r] for r in roles)
    cmd += ["-filter_complex_threads", "2", "-filter_complex", ";".join(filters), "-map", "[out]",
            "-frames:v", str(g["valid_frames"]), "-an", "-c:v", "libx264", "-crf", "19",
            "-preset", "fast", "-pix_fmt", "yuv420p", "-threads", "2", "-metadata", "title=" + title,
            "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, timeout=300)
    require(int(inspect(out)["nb_read_frames"]) == g["valid_frames"], "Comparison frame count differs")
    indices = list(map(int, args.frames.split(","))) if args.frames else list(range(g["valid_frames"]))
    require(indices and len(set(indices)) == len(indices)
            and all(0 <= n < g["valid_frames"] for n in indices), "Invalid requested frame indices")
    indices = sorted(indices)
    select = "+".join(f"eq(n\\,{n})" for n in indices)
    subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-n", "-threads", "1", "-i", str(out),
                    "-vf", "select=" + select, "-fps_mode", "vfr", "-q:v", "2",
                    str(dest / "selected_%03d.jpg")], check=True, timeout=60)
    screenshots = []
    for i, n in enumerate(indices, 1):
        target = dest / f"frame_{n:03d}.jpg"
        (dest / f"selected_{i:03d}.jpg").rename(target)
        screenshots.append({**bound(target), "physical_frame": n, "seconds": n / 24})
    receipt = {"schema": "r146-comparison-media-v1", "title": title, "inputs": media,
               "validated_execution": proof, "evaluation_manifest": bound(ROOT / "EVALUATION_MANIFEST.json"),
               "roles": roles, "video": bound(out), "screenshots": screenshots,
               "valid_frames": g["valid_frames"], "fps": 24, "all_frames_inspected": False,
               "task_verdict": None, "events": case["events"], "phases": case["phases"],
               "official_MF": case["official_MF"], "sampling_seconds": case["sampling_seconds"]}
    (dest / "PRESENTATION.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"case": args.case, "presentation": str(dest / "PRESENTATION.json")}))


if __name__ == "__main__":
    main()
