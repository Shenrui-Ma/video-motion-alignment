"""Validate explicit R148 receipts, then render four columns with Chinese footer."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parent
FFMPEG = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"
FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"


def read(path):
    return json.loads(Path(path).read_text())


def bound(path):
    path = Path(path).resolve()
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


def screenshot_selection(indices, total):
    # ffmpeg's expression parser has a finite nesting depth; full coverage needs no sum.
    return "1" if indices == list(range(total)) else "+".join(f"eq(n\\,{n})" for n in indices)


def validate(case, video, gate_path, complete_path, release_path, binding_path):
    b = read(binding_path)
    require(b.get("status") == "READY", "Runtime binding is pending; use the actual approved R148 contract")
    require(b["source_id"] == case["source_id"] and b["role"] == "fixed_phase"
            and b["run_id"] == case["R148"]["run_id"], "Wrong case, role or run")
    require(b["historical_prompt_sha256"] == case["prompt_sha256"]
            and b["historical_noise_sha256"] == case["historical_initial_noise"]["sha256"]
            and b["historical_fixed_graph_sha256"] == case["historical_runs"]["fixed"]["graph"]["sha256"],
            "Historical scientific binding differs")
    require(bound(b["producer_seal"]["file"]) == b["producer_seal"], "Producer seal changed")
    for field, path in (("gate", gate_path), ("complete", complete_path), ("release", release_path)):
        require(Path(path).name == PurePosixPath(b["receipt_files"][field]).name,
                field + " filename differs from explicit manifest")
    gate, complete, release = map(read, (gate_path, complete_path, release_path))
    require(gate.get("schema") == b["gate_schema"] and gate.get("passed") is True
            and gate.get("source_id") == case["source_id"], "Successful matching gate required")
    require(gate.get("producer_seal_sha256") == b["producer_seal"]["sha256"], "Gate seal differs")
    require(gate.get("checks") and all(v is True for v in gate["checks"].values()),
            "Scientific/runtime check failed")
    require(set(gate["runs"]) == {b["role"]}, "Unexpected run roles")
    run = gate["runs"][b["role"]]
    require(run.get("run_id") == b["run_id"], "Output run differs")
    require(b.get("expected_run_fields"), "Explicit execution checks are required")
    for key, value in b["expected_run_fields"].items():
        require(run.get(key) == value, "Execution field differs: " + key)
    g = case["geometry"]
    require(run.get("valid_frames") == g["valid_frames"]
            and run.get("evaluation_crop_xywh") == g["crop_xywh"], "Effective frame domain differs")
    require(complete.get("schema") == b["complete_schema"] and complete.get("passed") is True
            and complete.get("jobs") == [b["run_id"]] and complete.get("remaining") == []
            and complete.get("GPU_released") is True
            and complete.get("runtime_gate_sha256") == bound(gate_path)["sha256"],
            "Completion does not bind this successful gate")
    owner = gate["service_owner"]
    require(complete.get("service_owner") == owner and release.get("owner") == owner,
            "Service generation differs")
    cleanup = release.get("cleanup", {})
    require(release.get("passed") is True and release.get("process_absent") is True
            and release.get("CUDA_allocation_absent") is True
            and cleanup.get("pid") == owner["pid"] and cleanup.get("process_absent") is True
            and cleanup.get("own_compute_absent") is True, "Exact release incomplete")
    require(gate["runtime_profile"]["remote_root"] == b["remote_root"], "Producer root differs")
    expected_video = PurePosixPath(b["remote_root"]) / b["output_relative_file"]
    require(".." not in expected_video.parts and expected_video.is_relative_to(PurePosixPath(b["remote_root"]))
            and run["video"]["file"] == str(expected_video), "Output path differs")
    record = bound(video)
    require(record["sha256"] == run["video"]["sha256"], "Combined video SHA differs")
    expected = (g["width"], g["height"], g["sampled_frames"], Fraction(g["fps"]))
    require(dimensions(run["video"]["properties"]) == expected and dimensions(inspect(video)) == expected,
            "Combined video geometry/timebase differs")
    return {"combined_video": record, "gate": bound(gate_path), "complete": bound(complete_path),
            "release": bound(release_path), "runtime_binding": bound(binding_path),
            "seal": b["producer_seal"], "run_id": b["run_id"], "run_record": run}


def main():
    manifest = read(ROOT / "EVALUATION_MANIFEST.json")
    p = argparse.ArgumentParser()
    p.add_argument("--case", choices=[c["source_id"] for c in manifest["cases"]], required=True)
    p.add_argument("--combined", type=Path, required=True)
    for key in ("gate", "complete", "release", "binding"):
        p.add_argument("--" + key, type=Path, required=True)
    p.add_argument("--frames", default="", help="Comma-separated frames; default all effective frames")
    p.add_argument("--validate-only", action="store_true")
    a = p.parse_args()
    case = next(c for c in manifest["cases"] if c["source_id"] == a.case)
    proof = validate(case, a.combined, a.gate, a.complete, a.release, a.binding)
    media = dict(case["media"], fixed_phase=bound(a.combined))
    g = case["geometry"]
    for role, item in media.items():
        require(bound(item["file"])["sha256"] == item["sha256"], role + " media changed")
        require(dimensions(inspect(item["file"])) ==
                (g["width"], g["height"], g["sampled_frames"], Fraction(g["fps"])),
                role + " geometry differs")
    if a.validate_only:
        print(json.dumps({"passed": True, "run_id": proof["run_id"]}))
        return
    indices = sorted(map(int, a.frames.split(","))) if a.frames else list(range(g["valid_frames"]))
    require(indices and len(set(indices)) == len(indices) and
            all(0 <= n < g["valid_frames"] for n in indices), "Invalid selected frame indices")
    from PIL import Image, ImageDraw, ImageFont
    dest = ROOT / "review" / a.case
    dest.mkdir(parents=True, exist_ok=False)
    roles = manifest["roles"]
    font = ImageFont.truetype(FONT, 24)
    footer = Image.new("RGB", (1920, 54), "black")
    draw = ImageDraw.Draw(footer)
    for i, role in enumerate(roles):
        label = manifest["method_labels"][role]
        draw.text((i * 480 + (480 - draw.textlength(label, font=font)) / 2, 12),
                  label, font=font, fill="white")
    caption = dest / "caption.png"
    footer.save(caption)
    crop = g["crop_xywh"]
    vf = (f"crop={crop[2]}:{crop[3]}:{crop[0]}:{crop[1]},"
          "scale=480:270:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos,"
          "pad=480:270:(ow-iw)/2:(oh-ih)/2:black")
    cmd = [FFMPEG, "-v", "error", "-nostdin", "-n"]
    for role in roles:
        cmd += ["-threads", "1", "-i", media[role]["file"]]
    cmd += ["-loop", "1", "-framerate", "24", "-i", str(caption)]
    filters = [f"[{i}:v]{vf},trim=end_frame={g['valid_frames']},setpts=PTS-STARTPTS,setsar=1[v{i}]"
               for i in range(4)]
    filters += ["[v0][v1][v2][v3]hstack=inputs=4:shortest=1[images]",
                "[images][4:v]vstack=inputs=2:shortest=1[out]"]
    out = dest / "comparison.mp4"
    title = case["title"] + "｜" + " / ".join(manifest["method_labels"][r] for r in roles)
    cmd += ["-filter_complex_threads", "2", "-filter_complex", ";".join(filters), "-map", "[out]",
            "-frames:v", str(g["valid_frames"]), "-an", "-c:v", "libx264", "-crf", "19",
            "-preset", "fast", "-pix_fmt", "yuv420p", "-threads", "2", "-metadata", "title=" + title,
            "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, timeout=300)
    require(int(inspect(out)["nb_read_frames"]) == g["valid_frames"], "Comparison frame count differs")
    select = screenshot_selection(indices, g["valid_frames"])
    subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-n", "-threads", "1", "-i", str(out),
                    "-vf", "select=" + select, "-fps_mode", "vfr", "-q:v", "2",
                    str(dest / "selected_%03d.jpg")], check=True, timeout=60)
    screenshots = []
    for i, n in enumerate(indices, 1):
        target = dest / f"frame_{n:03d}.jpg"
        (dest / f"selected_{i:03d}.jpg").rename(target)
        screenshots.append({**bound(target), "physical_frame": n, "seconds": n / 24})
    result = {"schema": "r148-fourway-media-v1", "title": title, "roles": roles, "inputs": media,
              "validated_execution": proof, "evaluation_manifest": bound(ROOT / "EVALUATION_MANIFEST.json"),
              "video": bound(out), "screenshots": screenshots, "valid_frames": g["valid_frames"], "fps": 24,
              "all_frames_inspected": False, "task_verdict": None, "events": case["events"],
              "phases": case["phases"], "official_MF": case["official_MF"],
              "sampling_seconds": case["sampling_seconds"]}
    (dest / "PRESENTATION.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"case": a.case, "presentation": str(dest / "PRESENTATION.json")}))


if __name__ == "__main__":
    main()
