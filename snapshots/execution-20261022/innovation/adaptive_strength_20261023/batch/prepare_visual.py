"""Prepare exact-frame visual evidence after generation, without scoring it."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

P = Path(__file__).resolve().parent
E = P.parents[2]
OLD = E / "showcases/partial_rope_pilots_20261022/visual"
OUT = E / "showcases/adaptive_strength_20261023/visual"
FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
LABELS = {"source": "参考视频", "native": "Baseline", "global_weak": "α = 0.25",
          "dynamic_dof": "动态 α（维数校准）", "heads_budget": "Attention head 分配",
          "coverage_blend25": "同时间与跨时刻混合", "fixed0375": "α = 0.375",
          "dynamic_anchor": "动态 α（首步校准）", "temporal_gain_field":"动态 α（按视频时间分配）", "causal_layer_budget":"动态 α（按层分配）"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    subprocess.run(args, check=True, timeout=180, capture_output=True)


def extract(video, folder, count):
    folder.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
         "-vf", "crop=1280:720:16:8,scale=768:432", "-frames:v", str(count),
         "-start_number", "0", "-q:v", "2", str(folder / "%03d.jpg")])
    assert len(list(folder.glob("[0-9][0-9][0-9].jpg"))) == count


def sheet(folder, frames, target, label, crop=None, cols=6, width=300):
    frames = list(frames)
    images = []
    for n in frames:
        im = Image.open(folder / f"{n:03d}.jpg").convert("RGB")
        if crop:
            im = im.crop(crop)
        im = im.resize((width, round(im.height * width / im.width)))
        images.append((n, im))
    row_height = images[0][1].height + 28
    out = Image.new("RGB", (cols * width, ((len(images) + cols - 1) // cols) * row_height), "#151515")
    draw = ImageDraw.Draw(out)
    font = ImageFont.truetype(FONT, 17)
    for i, (n, im) in enumerate(images):
        x, y = i % cols * width, i // cols * row_height
        out.paste(im, (x, y + 28))
        draw.text((x + 5, y + 3), f"{label} · {n}", font=font, fill="white")
    out.save(target, quality=92)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    jobs = json.loads((P / "jobs.json").read_text())["jobs"]
    for extra in ("anchor_pilots/jobs.json","field_pilots/jobs.json","layer_pilots/jobs.json"):
        extra_plan = P / extra
        if extra_plan.is_file():
            jobs += json.loads(extra_plan.read_text())["jobs"]
    matches = [j for j in jobs if j["id"] == args.job]
    assert len(matches) == 1, "Expected one uniquely identified planned experiment"
    job = matches[0]
    task, method = job["metadata"]["task_id"], job["metadata"]["method"]
    count = job["metadata"]["valid_frames"]
    assert digest(args.video) == args.sha256, "Generated video SHA mismatch"
    assert job["metadata"]["fps"] == 24
    dest = OUT / task / method
    dest.mkdir(parents=True, exist_ok=True)
    extract(args.video, dest / "frames", count)
    sheet(dest / "frames", range(0, count, 4), dest / "overview.jpg", LABELS[method])
    crop = (0, 65, 430, 380) if task == "short_0358" else (108, 60, 552, 432)
    for start in range(0, count, 36):
        sheet(dest / "frames", range(start, min(count, start + 36)),
              dest / f"detail_{start:03d}.jpg", LABELS[method], crop=crop)
    manifest = json.loads((E / "metrics/manifest.json").read_text())["jobs"]
    controls = [next(j for j in manifest if j["task_id"] == task and j["method"] == m)
                for m in ("source", "native", "global_weak")]
    videos = [OLD / task / (j["method"] + ".mp4") for j in controls] + [args.video]
    for video, control in zip(videos, controls):
        assert digest(video) == control["sha256"], "Historical control SHA mismatch"
        assert control["valid_frames"] == count
    labels = [LABELS[m] for m in ("source", "native", "global_weak", method)]
    caption_paths = []
    for i, label in enumerate(labels):
        canvas = Image.new("RGB", (640, 28), "black")
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.truetype(FONT, 20)
        draw.text((320, 14), label, font=font, anchor="mm", fill="white")
        path = dest / f"caption_{i}.png"
        canvas.save(path)
        caption_paths.append(path)
    ff = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for video in videos:
        ff += ["-i", str(video)]
    for path in caption_paths:
        ff += ["-loop", "1", "-framerate", "24", "-i", str(path)]
    filters = []
    for i in range(4):
        filters += [f"[{i}:v]trim=end_frame={count},setpts=PTS-STARTPTS,crop=1280:720:16:8,scale=640:360,setsar=1[v{i}]",
                    f"[v{i}][{i+4}:v]vstack=inputs=2:shortest=1[p{i}]"]
    filters += ["[p0][p1]hstack=inputs=2[top]", "[p2][p3]hstack=inputs=2[bottom]",
                "[top][bottom]vstack=inputs=2,pad=iw:ih+36:0:0:black[out]"]
    ff += ["-filter_complex_threads", "2", "-filter_complex", ";".join(filters), "-map", "[out]",
           "-an", "-frames:v", str(count), "-r", "24", "-c:v", "libx264", "-threads", "4",
           "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
           str(dest / "comparison.mp4")]
    run(ff)
    (dest / "PROVENANCE.json").write_text(json.dumps({
        "job_id": args.job, "method": method, "generated_sha256": args.sha256,
        "controls": [{"id": j["id"], "sha256": j["sha256"]} for j in controls],
        "valid_frames": count, "fps": 24, "crop_xywh": [16, 8, 1280, 720],
        "status": "prepared_for_visual_annotation", "scores_inferred": False,
        "comparison_sha256": digest(dest / "comparison.mp4")}, ensure_ascii=False, indent=2) + "\n")
    print(dest)


if __name__ == "__main__":
    main()
