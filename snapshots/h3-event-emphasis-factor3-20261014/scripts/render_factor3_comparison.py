#!/usr/bin/env python3
"""Render CPU-only, same-frame SOURCE / BASELINE / WEIGHT x2 / WEIGHT x3.

Only review/ and analysis/render_tool_validation.json are written. Raw media and
the sealed pilot archive are read-only. Missing/incomplete formal media produce a
truthful pending page (exit 2), never a substitute fourth column. Pillow, ffmpeg
and ffprobe must already be installed; --self-test performs CPU checks only.
"""

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import html
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont


ARCHIVE = Path("/Users/researcher/DevProjects/h3-event-emphasis-pilot-20261013")
LABELS = ("SOURCE", "BASELINE", "WEIGHT x2", "WEIGHT x3")
RUNS = ("06_seed2_baseline", "06_seed2_emphasis2", "06_seed2_emphasis3")
FRAME_COUNT, FPS = 141, 24
ORIGINAL, TILE, HEADER = (1312, 736), (656, 368), 48
ROW = (TILE[0] * 4, TILE[1] + HEADER)
FONT = Path("/System/Library/Fonts/Helvetica.ttc")
STYLE = """body{font:16px system-ui,sans-serif;background:#080808;color:#fff;margin:0 auto;padding:24px;max-width:2200px}h1{font-size:26px}h2{font-size:21px}p{line-height:1.55;color:#ddd}a{color:#fff;overflow-wrap:anywhere}section{border-top:1px solid #555;margin:24px 0;padding-top:16px}video,img{display:block;width:100%;height:auto;background:#000;margin:14px 0}summary{cursor:pointer}code{color:#fff}.note{border-left:3px solid #fff;padding-left:14px}li{line-height:1.6}figure{margin:0}figcaption{color:#ddd}"""


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def write_page(path, body):
    page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    page += f'<title>H3 event weight comparison</title><style>{STYLE}</style><body>{body}</body></html>\n'
    temporary = path.with_suffix(".html.tmp")
    temporary.write_text(page)
    temporary.replace(path)


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def signature(path):
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def executable(name):
    result = shutil.which(name)
    if not result:
        raise RuntimeError(f"{name} unavailable; use the existing media runtime")
    return result


def probe(path):
    result = subprocess.run(
        [executable("ffprobe"), "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,avg_frame_rate,nb_read_frames,duration",
         "-of", "json", str(path)], check=True, capture_output=True, text=True, timeout=180)
    stream = json.loads(result.stdout)["streams"][0]
    return {"width": stream["width"], "height": stream["height"],
            "frames": int(stream["nb_read_frames"]),
            "fps": str(Fraction(stream["avg_frame_rate"])), "duration": float(stream["duration"])}


def check_geometry(info, frames=FRAME_COUNT, fps=FPS, size=ORIGINAL):
    actual = info["width"], info["height"], info["frames"], info["fps"]
    expected = *size, frames, str(fps)
    if actual != expected:
        raise ValueError(f"Expected width/height/frames/fps {expected}; got {actual}; refuse resynchronization")
    if abs(info["duration"] - frames / fps) > 1e-5:
        raise ValueError("Duration disagrees with frame count / FPS")


def check_timestamps(path):
    result = subprocess.run(
        [executable("ffprobe"), "-v", "error", "-select_streams", "v:0",
         "-show_frames", "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=180)
    values = [float(frame["best_effort_timestamp_time"]) for frame in json.loads(result.stdout)["frames"]]
    if len(values) != FRAME_COUNT or any(abs(t - i / FPS) > 1e-5 for i, t in enumerate(values)):
        raise ValueError("Frame timestamps must run from 0 at exactly 24 FPS; refuse independent retiming")
    return {"count": len(values), "first_seconds": values[0], "last_seconds": values[-1],
            "same_index_24fps_timestamps_verified": True}


def media_paths(root, archive):
    return [archive / "inputs/06_anime_eye_insert.mp4",
            archive / f"outputs/{RUNS[0]}_00001_.mp4",
            archive / f"outputs/{RUNS[1]}_00001_.mp4",
            root / f"outputs/{RUNS[2]}_00001_.mp4"]


def validate_destination(root, archive):
    for protected in (ARCHIVE.resolve(), Path(archive).resolve()):
        if root == protected or root.is_relative_to(protected):
            raise ValueError("Refuse to write into the sealed pilot archive")


def formal_history(path):
    history = json.loads(path.read_text())
    if "status" not in history and len(history) == 1:
        history = next(iter(history.values()))
    status = history.get("status", {})
    if status.get("status_str") != "success" or status.get("completed") is not True:
        raise ValueError("Successful completed formal history not present")


def pending(root, problems):
    out = root / "review"
    out.mkdir(parents=True, exist_ok=True)
    result = {"status": "pending", "checked_utc": datetime.now(timezone.utc).isoformat(),
              "problems": problems, "formal_run_ids": list(RUNS), "column_labels": list(LABELS),
              "synthetic_results": False, "comparison_rendered": False,
              "expected_factor3_output": str(root / f"outputs/{RUNS[2]}_00001_.mp4")}
    write_json(out / "manifest.json", result)
    body = '<h1>H3 event weight comparison</h1><p>SOURCE / BASELINE / WEIGHT x2 / WEIGHT x3</p>'
    body += '<p class="note">Pending complete formal outputs. No current comparison has been rendered or validated. No substitute factor 3 result is shown.</p><ul>'
    body += ''.join('<li>' + html.escape(problem) + '</li>' for problem in problems) + '</ul>'
    body += '<p>Planned: complete 141-frame comparison at 24 FPS; frames 30-77 at 24 FPS and 6 FPS; every-frame contact sheets. Frame numbers are zero-based.</p>'
    body += '<p><a href="manifest.json">Current status manifest</a></p>'
    write_page(out / "index.html", body)
    return result


def decode(path):
    raw = subprocess.run(
        [executable("ffmpeg"), "-v", "error", "-xerror", "-threads", "2", "-i", str(path),
         "-vf", "scale=656:368:flags=lanczos", "-fps_mode", "passthrough", "-an",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        check=True, capture_output=True, timeout=180).stdout
    size = TILE[0] * TILE[1] * 3
    if len(raw) != FRAME_COUNT * size:
        raise ValueError("Expected exactly 141 decoded frames: " + str(path))
    return [Image.frombytes("RGB", TILE, raw[i * size:(i + 1) * size]) for i in range(FRAME_COUNT)]


def fonts():
    if not FONT.is_file():
        raise RuntimeError("Required font unavailable: " + str(FONT))
    return ImageFont.truetype(str(FONT), 20), ImageFont.truetype(str(FONT), 14)


def compose(sequences, frame):
    if len(sequences) != 4:
        raise ValueError("Exactly four independent input sequences are required")
    row = Image.new("RGB", ROW, "black")
    draw = ImageDraw.Draw(row)
    title_font, detail_font = fonts()
    for column, (label, sequence) in enumerate(zip(LABELS, sequences)):
        x = column * TILE[0]
        row.paste(sequence[frame], (x, HEADER))
        draw.text((x + 10, 3), label, font=title_font, fill="white")
        draw.text((x + 10, 28), f"frame {frame:03d} | {frame / FPS:.3f}s", font=detail_font, fill="white")
    return row


def encode(rows, path, fps):
    temporary = path.with_name(path.stem + ".partial.mp4")
    command = [executable("ffmpeg"), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{ROW[0]}x{ROW[1]}", "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264",
               "-threads", "2", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", str(temporary)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for row in rows:
            if row.size != ROW:
                raise ValueError("Unexpected comparison row dimensions")
            process.stdin.write(row.tobytes())
        process.stdin.close()
        error = process.stderr.read().decode("utf-8", errors="replace")
        if process.wait(timeout=180):
            raise RuntimeError("ffmpeg failed: " + error[-1000:])
        actual = probe(temporary)
        check_geometry(actual, len(rows), fps, ROW)
        temporary.replace(path)
        return actual
    except BaseException:
        if process.poll() is None:
            process.kill()
            process.wait()
        temporary.unlink(missing_ok=True)
        raise


def sheets(rows, indices, folder, prefix):
    folder.mkdir(parents=True, exist_ok=True)
    records = []
    for start in range(0, len(indices), 3):
        part = indices[start:start + 3]
        sheet = Image.new("RGB", (ROW[0], ROW[1] * len(part)), "black")
        for offset, frame in enumerate(part):
            sheet.paste(rows[frame], (0, offset * ROW[1]))
        path = folder / f"{prefix}_{part[0]:03d}-{part[-1]:03d}.jpg"
        sheet.save(path, quality=95, subsampling=0)
        with Image.open(path) as check:
            check.load()
            if check.size != sheet.size:
                raise ValueError("Sheet dimension mismatch")
        records.append({"file": str(path), "frames": part, "sha256": fingerprint(path)})
    return records


def validate_crop(crop):
    x, y, width, height = crop
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > ORIGINAL[0] or y + height > ORIGINAL[1]:
        raise ValueError("Crop must lie within the original 1312x736 frame")
    return x, y, width, height


def keyframe_crop(paths, crop, path):
    x, y, width, height = validate_crop(crop)
    tile_width = min(TILE[0], width)
    tile_height = max(1, round(height * tile_width / width))
    canvas = Image.new("RGB", (4 * tile_width, tile_height + 54), "black")
    draw = ImageDraw.Draw(canvas)
    title_font, detail_font = fonts()
    for column, (label, source) in enumerate(zip(LABELS, paths)):
        raw = subprocess.run(
            [executable("ffmpeg"), "-v", "error", "-xerror", "-threads", "2", "-i", str(source),
             "-vf", "select=eq(n\\,44)", "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
            check=True, capture_output=True, timeout=180).stdout
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.size != ORIGINAL:
                raise ValueError("Unexpected keyframe dimensions")
            tile = image.crop((x, y, x + width, y + height)).resize((tile_width, tile_height), Image.Resampling.LANCZOS)
        left = column * tile_width
        canvas.paste(tile, (left, 0))
        draw.text((left + 8, tile_height + 3), label, font=title_font, fill="white")
        draw.text((left + 8, tile_height + 30), "frame 044 | 1.833s", font=detail_font, fill="white")
    canvas.save(path)
    return {"file": path.name, "frame": 44, "source_timestamp_seconds": 44 / FPS,
            "crop_original_xywh": list(crop), "tile_size": [tile_width, tile_height],
            "captions": "bottom only; no heading", "sha256": fingerprint(path),
            "purpose": "Optional equal-coordinate detail preview; full-frame media remain primary evidence"}


def render(root, archive=ARCHIVE, crop=None):
    root, archive = Path(root).resolve(), Path(archive).resolve()
    validate_destination(root, archive)
    if crop is not None:
        validate_crop(crop)
    paths = media_paths(root, archive)
    problems = ["Missing media: " + str(path) for path in paths if not path.is_file()]
    histories = [archive / f"logs/{RUNS[0]}_history.json", archive / f"logs/{RUNS[1]}_history.json",
                 root / f"logs/{RUNS[2]}_history.json"]
    for path in histories:
        try:
            formal_history(path)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            problems.append(f"Formal history pending: {path}: {error}")
    if problems:
        return pending(root, problems)
    infos, timestamps, signatures = [], [], []
    for path in paths:
        try:
            before = signature(path)
            info = probe(path)
            check_geometry(info)
            timing = check_timestamps(path)
            if signature(path) != before:
                raise ValueError("File changed during completeness checks")
            infos.append(info)
            timestamps.append(timing)
            signatures.append(before)
        except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as error:
            problems.append(f"Media not ready: {path}: {error}")
    if problems:
        return pending(root, problems)
    pending(root, ["Preflight passed; CPU renderer is running. Final derivative validation is pending."])
    try:
        hashes = [fingerprint(path) for path in paths]
        sequences = [decode(path) for path in paths]
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return pending(root, [f"Media decode incomplete: {error}"])
    if any(signature(path) != prior for path, prior in zip(paths, signatures)):
        return pending(root, ["Input changed during hashing or decoding; retry after collection is complete"])
    rows = [compose(sequences, frame) for frame in range(FRAME_COUNT)]
    del sequences
    out = root / "review"
    out.mkdir(parents=True, exist_ok=True)
    videos = {}
    for name, selected, fps, bounds in (
        ("comparison_full.mp4", rows, 24, [0, 140]),
        ("comparison_frames_030-077.mp4", rows[30:78], 24, [30, 77]),
        ("comparison_frames_030-077_quarter_speed.mp4", rows[30:78], 6, [30, 77]),
    ):
        path = out / name
        videos[name] = {"probe": encode(selected, path, fps), "sha256": fingerprint(path),
                        "source_frames_inclusive": bounds}
    groups = {"dense_030_077": sheets(rows, list(range(30, 78)), out / "dense_030_077", "dense"),
              "all_frames": sheets(rows, list(range(FRAME_COUNT)), out / "all_frames", "frames")}
    for records in groups.values():
        for record in records:
            record["file"] = str(Path(record["file"]).relative_to(out))
    compact = keyframe_crop(paths, crop, out / "keyframe_044_compact.png") if crop else None
    if any(signature(path) != prior for path, prior in zip(paths, signatures)):
        return pending(root, ["Input changed while rendering; current derivatives are not approved for review"])
    result = {"status": "ready", "rendered_utc": datetime.now(timezone.utc).isoformat(),
              "formal_run_ids": list(RUNS), "benchmark_excluded": True, "synthetic_results": False,
              "inputs": [{"label": label, "path": str(path), "sha256": digest, "probe": info, "timestamps": timing}
                         for label, path, digest, info, timing in zip(LABELS, paths, hashes, infos, timestamps)],
              "histories": [{"path": str(path), "sha256": fingerprint(path)} for path in histories],
              "videos": videos, "sheets": groups, "compact_keyframe": compact, "column_labels": list(LABELS),
              "tile_width_height": list(TILE), "comparison_width_height": list(ROW),
              "frame_numbering": "zero-based; timestamp = source frame index / 24",
              "source_event_frames_inclusive": [39, 44], "source_core_frames_inclusive": [41, 42],
              "later_separate_event_frames_inclusive": [54, 68],
              "slow_motion_method": "Identical decoded frames encoded at 6 FPS; no interpolation or frame repetition",
              "temporal_alignment": "Identical frame index in all four columns; no independent retiming",
              "spatial_alignment": "All full frames equally scaled 1312x736 to 656x368; no crop or independent enlargement in videos/sheets",
              "audio": "Comparison derivatives are silent; raw source/generated media remain unchanged",
              "notes": ["Source event labels describe source timing only; they do not assert generated event occurrence.",
                        "Weights x2 and x3 identify temporal-reference attention interventions, not verified action repair.",
                        "Rendering verifies presentation only; scientific control and quality reviews are separate."]}
    write_json(out / "manifest.json", result)
    body = '<h1>H3 event weight comparison</h1><p>SOURCE / BASELINE / WEIGHT x2 / WEIGHT x3</p>'
    body += '<p>Complete original clips: 141 frames, 24 FPS, 1312 &times; 736. All four columns show the same zero-based frame index; each full frame is displayed at 656 &times; 368.</p>'
    body += '<p class="note">Inspect the source hand-eye relation at frames 39-44 (core 41-42). The later V / leg lift at 54-68 is a separate event. These source labels do not assert success in generated results.</p>'
    body += '<p>No independent retiming, interpolation or frame repetition. Quarter-speed playback uses the same frames at 6 FPS. Review exports are silent; original media are preserved.</p>'
    for title, name, description in (
        ("Complete clip: frames 0-140", "comparison_full.mp4", "Normal speed, 24 FPS, 5.875 seconds."),
        ("Event context: frames 30-77", "comparison_frames_030-077.mp4", "Normal speed, 24 FPS, 2 seconds."),
        ("Event context: quarter speed", "comparison_frames_030-077_quarter_speed.mp4", "Same 48 frames at 6 FPS, 8 seconds; frame labels retain original timestamps."),
    ):
        body += f'<section><h2>{title}</h2><p>{description}</p><video controls preload="metadata" src="{name}"></video><p><a href="{name}">Open video</a></p></section>'
    if compact:
        body += '<section><h2>Optional detail: frame 44</h2><p>Identical crop coordinates in all four originals. Use the full-frame sheets below for context.</p><a href="keyframe_044_compact.png"><img src="keyframe_044_compact.png" alt="Frame 44 equal-coordinate crop with bottom captions"></a></section>'
    for title, key in (("Dense context: every frame 30-77", "dense_030_077"), ("Full context: every frame 0-140", "all_frames")):
        body += f'<section><h2>{title}</h2><p>Three time rows per sheet; SOURCE / BASELINE / WEIGHT x2 / WEIGHT x3 across every row.</p><details><summary>Show all frame sheets</summary>'
        for record in groups[key]:
            body += f'<a href="{record["file"]}"><img loading="lazy" src="{record["file"]}" alt="Same-index four-column frames {record["frames"][0]}-{record["frames"][-1]}"></a>'
        body += '</details></section>'
    body += '<p><a href="manifest.json">Media manifest, checksums and exact frame coverage</a></p>'
    write_page(out / "index.html", body)
    return result


def self_test(root, archive):
    """Exercise software in temporary storage, without a fabricated factor 3 video."""
    root, archive = Path(root).resolve(), Path(archive).resolve()
    validate_destination(root, archive)
    checks = {}
    with tempfile.TemporaryDirectory(prefix="h3-factor3-render-tool-") as temporary:
        temporary = Path(temporary)
        result = render(temporary, archive)
        checks["missing_factor3_stays_pending"] = result["status"] == "pending" and not list((temporary / "review").glob("*.mp4"))
        checks["pending_index_contains_no_video_or_image"] = not any(tag in (temporary / "review/index.html").read_text() for tag in ("<video", "<img"))
        checks["real_archived_media"] = []
        for path in media_paths(root, archive)[:3]:
            info = probe(path)
            check_geometry(info)
            timing = check_timestamps(path)
            checks["real_archived_media"].append({"path": str(path), "probe": info, "timestamps": timing})
        checks["rejects_140_frame_mismatch"] = False
        try:
            check_geometry(dict(info, frames=140))
        except ValueError:
            checks["rejects_140_frame_mismatch"] = True
        checks["rejects_out_of_bounds_crop"] = False
        try:
            validate_crop((0, 0, 1313, 736))
        except ValueError:
            checks["rejects_out_of_bounds_crop"] = True
        checks["sealed_archive_write_rejected"] = False
        try:
            validate_destination(archive / "review", archive)
        except ValueError:
            checks["sealed_archive_write_rejected"] = True
        history = temporary / "software-test-history.json"
        write_json(history, {"status": {"status_str": "success", "completed": True}})
        formal_history(history)
        write_json(history, {"prompt-id": {"status": {"status_str": "success", "completed": True}}})
        formal_history(history)
        checks["accepts_direct_and_wrapped_complete_history"] = True
        write_json(history, {"status": {"status_str": "success", "completed": False}})
        checks["rejects_incomplete_formal_history"] = False
        try:
            formal_history(history)
        except ValueError:
            checks["rejects_incomplete_formal_history"] = True
        colors = ("red", "green", "blue", "yellow")
        # In-memory pixels test indexing only. Never exported as experiment media.
        sequences = [[Image.new("RGB", TILE, "black"), Image.new("RGB", TILE, color)] for color in colors]
        row = compose(sequences, 1)
        checks["same_frame_column_mapping"] = all(row.getpixel((column * TILE[0] + 100, HEADER + 100)) == Image.new("RGB", (1, 1), color).getpixel((0, 0)) for column, color in enumerate(colors))
        # Encoder fixtures carry no experiment column labels or source imagery.
        fixture = Image.new("RGB", ROW, "black")
        ImageDraw.Draw(fixture).text((20, 20), "RENDERER SOFTWARE TEST - NOT AN EXPERIMENT RESULT", fill="white", font=fonts()[0])
        checks["encoder_probes"] = {}
        for fps in (24, 6):
            checks["encoder_probes"][str(fps)] = encode([fixture] * 3, temporary / f"software-test-{fps}.mp4", fps)
        fixture_rows = [fixture] * 141
        dense = sheets(fixture_rows, list(range(30, 78)), temporary / "software-test-dense", "software_test")
        full = sheets(fixture_rows, list(range(141)), temporary / "software-test-full", "software_test")
        checks["three_time_rows_per_sheet"] = all(len(record["frames"]) == 3 for record in dense + full)
        checks["dense_coverage"] = len(dense) == 16 and [frame for record in dense for frame in record["frames"]] == list(range(30, 78))
        checks["full_coverage"] = len(full) == 47 and [frame for record in full for frame in record["frames"]] == list(range(141))
    if any(value is False for value in checks.values()):
        raise AssertionError(checks)
    report = {"status": "passed_cpu_software_checks_not_experiment_validation",
              "checked_utc": datetime.now(timezone.utc).isoformat(), "checks": checks,
              "fixture_files_deleted": True, "fake_factor3_media_rendered": False,
              "experimental_render_completed": False,
              "limitations": ["Actual four-input render and its visual review await complete formal factor 3 output.",
                              "Optional crop is implemented but cannot be evaluated before all four actual inputs exist."]}
    write_json(root / "analysis/render_tool_validation.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--keyframe-crop", nargs=4, type=int, metavar=("X", "Y", "WIDTH", "HEIGHT"),
                        help="Optional frame-44 compact PNG: identical crop in original pixels, captions below")
    parser.add_argument("--self-test", action="store_true", help="CPU software checks only; no fabricated factor 3 media")
    args = parser.parse_args()
    result = self_test(args.root, args.archive) if args.self_test else render(args.root, args.archive, args.keyframe_crop)
    print(json.dumps({"status": result["status"], "problems": result.get("problems", []),
                      "review": str(args.root / "review/index.html")}))
    raise SystemExit(2 if result["status"] == "pending" else 0)


if __name__ == "__main__":
    main()
