"""Render seven R149 conditions on the same physical-frame axis."""
import argparse
import subprocess

from common import ROOT, FFMPEG, FONT, bound, read, write, require, verify_record, inspect

ROLES = ("source", "native", "early", "fixed", "late", "split", "global_weak")
LABELS = ("参考视频", "普通编辑", "引导 1–9 步", "引导 7–15 步",
          "引导 12–20 步", "引导 1–4＋16–20 步", "全程弱引导 α=0.25")


def render(case):
    from PIL import Image, ImageDraw, ImageFont

    sid = case["source_id"]
    dest = ROOT / "overview" / sid
    inputs = []
    for role in ROLES:
        if role in ("source", "native", "fixed"):
            inputs.append(case["media"][role])
            continue
        presentation = ROOT / "review" / sid / role / "PRESENTATION.json"
        if not presentation.exists():
            return None
        inputs.append(read(presentation)["new_video"])
    for item in inputs:
        verify_record(item)
    manifest = dest / "PRESENTATION.json"
    if manifest.exists():
        old = read(manifest)
        require(old["inputs"] == inputs, "Overview inputs changed")
        verify_record(old["video"])
        for image in old["screenshots"]:
            verify_record(image)
        return manifest

    dest.mkdir(parents=True, exist_ok=True)
    g = case["geometry"]
    width, cell_width, image_height, footer_height = 4480, 640, 360, 64
    caption = Image.new("RGB", (width, footer_height), "black")
    draw = ImageDraw.Draw(caption)
    font = ImageFont.truetype(FONT, 28)
    for i, text in enumerate(LABELS):
        draw.text((i * cell_width + (cell_width - draw.textlength(text, font=font)) / 2, 13),
                  text, font=font, fill="white")
    caption_path = dest / "caption.png"
    caption.save(caption_path)
    x, y, w, h = g["crop_xywh"]
    vf = (f"crop={w}:{h}:{x}:{y},scale={cell_width}:{image_height}:"
          "force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos,"
          f"pad={cell_width}:{image_height}:(ow-iw)/2:(oh-ih)/2:black")
    command = [FFMPEG, "-v", "error", "-nostdin", "-n"]
    for item in inputs:
        command += ["-threads", "1", "-i", item["file"]]
    command += ["-loop", "1", "-framerate", str(g["fps"]), "-i", str(caption_path)]
    filters = [
        f"[{i}:v]{vf},trim=end_frame={g['valid_frames']},setpts=PTS-STARTPTS,setsar=1[v{i}]"
        for i in range(7)
    ]
    filters += [
        "".join(f"[v{i}]" for i in range(7)) + "hstack=inputs=7:shortest=1[images]",
        "[images][7:v]vstack=inputs=2:shortest=1[out]",
    ]
    output = dest / "comparison.mp4"
    command += ["-filter_complex_threads", "2", "-filter_complex", ";".join(filters),
                "-map", "[out]", "-frames:v", str(g["valid_frames"]), "-an",
                "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
                "-threads", "2", "-movflags", "+faststart", str(output)]
    subprocess.run(command, check=True, timeout=600)
    props = inspect(output)
    require(int(props["nb_read_frames"]) == g["valid_frames"], "Overview frame count differs")
    require(int(props["width"]) == width and int(props["height"]) == 424,
            "Overview dimensions differ")
    plan = next(c for c in read(ROOT / "EVALUATION_PLAN.json")["cases"]
                if c["source_id"] == sid)
    screenshots = []
    for frame in plan["representative_frames"]:
        path = dest / f"frame_{frame:03d}.jpg"
        subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-n", "-threads", "1",
                        "-i", str(output), "-vf", f"select=eq(n\\,{frame})",
                        "-frames:v", "1", "-q:v", "2", str(path)], check=True, timeout=60)
        screenshots.append({**bound(path), "frame": frame})
    subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-threads", "1",
                    "-i", str(output), "-f", "null", "-"], check=True, timeout=90)
    write(manifest, dict(schema="r149-seven-condition-overview-v1", source_id=sid,
                         roles=ROLES, labels=LABELS, inputs=inputs, video=bound(output),
                         screenshots=screenshots, valid_frames=g["valid_frames"],
                         fps=g["fps"], width=width, height=424, full_decode_passed=True))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    args = parser.parse_args()
    for case in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]:
        if args.case is None or case["source_id"] == args.case:
            result = render(case)
            print(result or f"{case['source_id']}: waiting for four completed outputs")
