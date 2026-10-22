"""Render five matched conditions, with captions below the same-frame canvas."""
import argparse
import json
import subprocess
from pathlib import Path

from prepare import ROOT, bind, read

FFMPEG = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"
FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"


def verify(record):
    if bind(Path(record["file"]))["sha256"] != record["sha256"]:
        raise ValueError(f"Evidence changed: {record['file']}")


def render(case, manifest):
    from PIL import Image, ImageDraw, ImageFont
    sid = case["source_id"]
    inputs = [case["controls"][role] for role in ("source", "native", "forward")]
    for role in ("reverse", "combined"):
        result_path = ROOT / "results" / sid / f"{role}.json"
        if not result_path.exists():
            return f"{sid}: awaiting {role}"
        result = read(result_path)
        if result["source_id"] != sid or result["role"] != role or not result["execution_verified"]:
            raise ValueError("Unverified or mismatched result.")
        verify(result["execution_evidence"])
        inputs.append(result["video"])
    for item in inputs:
        verify(item)
    folder = ROOT / "overview" / sid
    presentation_path = folder / "PRESENTATION.json"
    if presentation_path.exists():
        old = read(presentation_path)
        if old["inputs"] != inputs:
            raise ValueError("Existing comparison has different inputs.")
        verify(old["video"])
        return str(presentation_path)
    folder.mkdir(parents=True, exist_ok=True)
    labels = [manifest["role_labels"][role] for role in manifest["roles"]]
    caption = Image.new("RGB", (3200, 64), "black")
    draw = ImageDraw.Draw(caption)
    font = ImageFont.truetype(FONT, 28)
    for i, label in enumerate(labels):
        x = i * 640 + (640 - draw.textlength(label, font=font)) / 2
        draw.text((x, 12), label, font=font, fill="white")
    caption_path = folder / "caption.png"
    caption.save(caption_path)
    g = case["geometry"]
    x, y, w, h = g["crop_xywh"]
    geometry_filter = (
        f"crop={w}:{h}:{x}:{y},scale=640:360:"
        "force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos,"
        f"pad=640:360:(ow-iw)/2:(oh-ih)/2:black,trim=end_frame={g['valid_frames']},"
        "setpts=PTS-STARTPTS,setsar=1"
    )
    command = [FFMPEG, "-v", "error", "-nostdin", "-n"]
    for item in inputs:
        command += ["-threads", "1", "-i", item["file"]]
    command += ["-loop", "1", "-framerate", str(g["fps"]), "-i", str(caption_path)]
    filters = [f"[{i}:v]{geometry_filter}[v{i}]" for i in range(5)]
    filters += ["[v0][v1][v2][v3][v4]hstack=inputs=5:shortest=1[row]",
                "[row][5:v]vstack=inputs=2:shortest=1[out]"]
    output = folder / "comparison.mp4"
    command += ["-filter_complex_threads", "2", "-filter_complex", ";".join(filters),
                "-map", "[out]", "-frames:v", str(g["valid_frames"]), "-an",
                "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
                "-threads", "2", "-movflags", "+faststart", str(output)]
    subprocess.run(command, check=True, timeout=600)
    inspected = json.loads(subprocess.check_output([
        FFPROBE, "-v", "error", "-select_streams", "v:0", "-count_frames",
        "-show_entries", "stream=width,height,nb_read_frames,r_frame_rate",
        "-of", "json", str(output)]))["streams"][0]
    assert (int(inspected["width"]), int(inspected["height"])) == (3200, 424)
    assert int(inspected["nb_read_frames"]) == g["valid_frames"]
    assert inspected["r_frame_rate"] == f"{g['fps']}/1"
    screenshots = []
    for frame in case["representative_frames"]:
        path = folder / f"frame_{frame:03d}.jpg"
        subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-n", "-threads", "1",
                        "-i", str(output), "-vf", f"select=eq(n\\,{frame})", "-frames:v", "1",
                        "-q:v", "2", str(path)], check=True, timeout=60)
        screenshots.append({**bind(path), "frame": frame})
    subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-threads", "1", "-i",
                    str(output), "-f", "null", "-"], check=True, timeout=90)
    presentation_path.write_text(json.dumps({
        "schema": "r151-five-condition-overview-v1",
        "source_id": sid, "roles": manifest["roles"], "labels": labels,
        "inputs": inputs, "video": bind(output), "screenshots": screenshots,
        "valid_frames": g["valid_frames"], "fps": g["fps"],
        "width": 3200, "height": 424, "full_decode_passed": True,
    }, ensure_ascii=False, indent=2) + "\n")
    return str(presentation_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    args = parser.parse_args()
    manifest = read(ROOT / "EVALUATION_MANIFEST.json")
    for case in manifest["cases"]:
        if args.case is None or args.case == case["source_id"]:
            print(render(case, manifest))
