#!/usr/bin/env python3
"""CPU-only SOURCE / SILVER WOLF BASELINE / SILVER WOLF x3 review renderer.

Writes only review/ and analysis/renderer_qa.json. Requires the one completed
Silver Wolf baseline formal history and three complete 141-frame, 24-FPS inputs. Missing
results produce a truthful pending page (exit 2); no substitute output is used.
Rendering conventions reuse the validated factor3 full/compact renderers.
"""

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont


WEIGHTED_ROOT = Path("/Users/researcher/DevProjects/h3-event-emphasis-silverwolf-20261014")
FIREFLY_ROOT = Path("/Users/researcher/DevProjects/h3-event-emphasis-factor3-20261014")
PILOT_ROOT = Path("/Users/researcher/DevProjects/h3-event-emphasis-pilot-20261013")
RUN = "06_silverwolf_seed2_baseline"
LABELS = ("SOURCE", "SILVER WOLF BASELINE", "SILVER WOLF x3")
ORIGINAL, FULL_TILE, COMPACT_TILE = (1312, 736), (656, 368), (368, 368)
FULL_ROW, COMPACT_ROW = (1968, 416), (1104, 412)
COUNT, FPS = 141, 24
EVENT = list(range(30, 78))
KEYFRAMES = [40, 41, 42]
CROP = [288, 0, 736, 736]
FONT = Path("/System/Library/Fonts/Helvetica.ttc")
CAVEAT = "Both generated columns use Silver Wolf with nominally identical prompt, seed and settings apart from event weight (baseline x1 versus x3). Nominal agreement does not establish a causal weighting comparison. Read the control validator status and its environment differences and evidence limits below; media readiness is not a control-validation pass."
STYLE = """body{font:16px system-ui,sans-serif;background:#080808;color:#fff;margin:0 auto;padding:24px;max-width:1968px}h1{font-size:26px}h2{font-size:21px}p{line-height:1.55;color:#ddd}a{color:#fff;overflow-wrap:anywhere}section{border-top:1px solid #555;margin:24px 0;padding-top:16px}video,img{display:block;width:100%;height:auto;background:#000;margin:14px 0}summary{cursor:pointer}.note{border-left:3px solid #fff;padding-left:14px}li{line-height:1.6}.compact{max-width:1104px}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:32em;overflow:auto;border:1px solid #555;padding:12px;font-size:13px}"""


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def write_page(path, body):
    content = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    content += f'<title>H3 Silver Wolf baseline versus weight x3</title><style>{STYLE}</style><body>{body}</body></html>\n'
    temporary = path.with_suffix(".html.tmp")
    temporary.write_text(content)
    temporary.replace(path)


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def signature(path):
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def executable(name):
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"{name} unavailable; use the existing media runtime")
    return found


def probe(path):
    result = subprocess.run(
        [executable("ffprobe"), "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,avg_frame_rate,nb_read_frames,duration", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=180)
    stream = json.loads(result.stdout)["streams"][0]
    return {"width": stream["width"], "height": stream["height"], "frames": int(stream["nb_read_frames"]),
            "fps": str(Fraction(stream["avg_frame_rate"])), "duration": float(stream["duration"])}


def check_geometry(info, count=COUNT, fps=FPS, size=ORIGINAL):
    if (info["width"], info["height"], info["frames"], info["fps"]) != (*size, count, str(fps)):
        raise ValueError("Frame count, FPS or geometry mismatch; refuse resynchronization")
    if abs(info["duration"] - count / fps) > 1e-5:
        raise ValueError("Duration disagrees with frame count / FPS")


def check_timestamps(path):
    result = subprocess.run(
        [executable("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_frames",
         "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=180)
    times = [float(frame["best_effort_timestamp_time"]) for frame in json.loads(result.stdout)["frames"]]
    if len(times) != COUNT or any(abs(time - index / FPS) > 1e-5 for index, time in enumerate(times)):
        raise ValueError("Require exactly frame-index / 24 timestamps; refuse independent retiming")
    return {"count": len(times), "first_seconds": times[0], "last_seconds": times[-1], "exact_24fps_grid": True}


def formal_history(path):
    history = json.loads(path.read_text())
    if "status" not in history and len(history) == 1:
        history = next(iter(history.values()))
    status = history.get("status", {})
    if status.get("status_str") != "success" or status.get("completed") is not True:
        raise ValueError("Successful completed formal history required")


def media_paths(root):
    return [root / "inputs/06_anime_eye_insert.mp4",
            root / f"outputs/{RUN}_00001_.mp4",
            WEIGHTED_ROOT / "outputs/06_silverwolf_seed2_emphasis3_00001_.mp4"]


def read_control_validation(root):
    """Expose the validator's own findings without inventing a causal verdict."""
    path = root / "analysis/baseline_validation.json"
    if not path.is_file():
        return {"available": False, "reported_status": "pending",
                "message": "Control validation is not available yet. Runtime/environment parity has not been established."}
    try:
        content = path.read_text()
        report = json.loads(content)
        if not isinstance(report, dict):
            raise ValueError("Expected a JSON object")
    except (OSError, ValueError) as error:
        return {"available": False, "reported_status": "unreadable",
                "message": f"Control validation could not be read: {error}; causal matching is not established."}
    return {"available": True, "path": str(path), "reported_status": report.get("status", "unspecified"),
            "sha256": hashlib.sha256(content.encode()).hexdigest(), "report": report}


def validation_notes(report):
    """Surface explicit limits and failed environment controls, without judging them."""
    notes = []

    def visit(value, path=()):
        key = ".".join(path).lower()
        if isinstance(value, dict):
            for child, item in value.items():
                visit(item, (*path, str(child)))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, (*path, str(index)))
        elif value is not None and value != "":
            explicit = any(word in key for word in ("limit", "warning", "error", "mismatch", "difference", "confound"))
            environment = any(word in key for word in ("environment", "runtime", "backend", "kernel", "gpu", "host"))
            failed_environment = environment and (value is False or (value is True and any(word in key for word in ("cross_", "different", "mismatch"))))
            environment_message = environment and isinstance(value, str) and any(word in value.lower() for word in ("mismatch", "different", "cross-environment", "fail"))
            host_or_device = any(word in key for word in ("host", "hostname", "gpu_model", "device_name"))
            if (explicit and value is not False) or failed_environment or environment_message or host_or_device:
                label = ".".join(path)
                notes.append((environment, f"{label}: {value}"))

    visit(report)
    return [note for _, note in sorted(notes, key=lambda pair: not pair[0])]


def validation_panel(control):
    status = html.escape(str(control["reported_status"]))
    body = f'<section id="control-validation"><h2>Control validation</h2><p class="note">Validator reported status: <strong>{status}</strong>.</p>'
    if control["available"]:
        notes = validation_notes(control["report"])
        if notes:
            body += '<ul>' + ''.join('<li>' + html.escape(note) + '</li>' for note in notes[:6]) + '</ul>'
            if len(notes) > 6:
                body += '<p>Additional recorded limits appear in the complete report.</p>'
        body += '<p><a href="../analysis/baseline_validation.json">Open the complete control-validation report</a>.</p>'
        body += '<details><summary>Complete validator report</summary><pre>'
        body += html.escape(json.dumps(control["report"], ensure_ascii=False, indent=2)) + '</pre></details>'
    else:
        body += '<p>' + html.escape(control["message"]) + '</p>'
    return body + '</section>'


def introduction(control):
    return ('<h1>H3 Silver Wolf baseline versus weight x3</h1><p>SOURCE / SILVER WOLF BASELINE / SILVER WOLF x3</p>'
            f'<p class="note">{CAVEAT}</p>'
            '<p>Nominal settings: same prompt and reference, seed 2026101312, 20 steps; event weight x1 versus x3. '
            '<a href="../inputs/silverwolf_reference.png">Open the Silver Wolf reference image</a>.</p>' + validation_panel(control))


def pending(root, problems):
    review = root / "review"
    review.mkdir(parents=True, exist_ok=True)
    result = {"status": "pending", "checked_utc": datetime.now(timezone.utc).isoformat(), "problems": problems,
              "column_labels": list(LABELS), "new_formal_runs_requested": 1, "new_formal_run": RUN,
              "synthetic_results": False, "comparison_rendered": False, "interpretation_limit": CAVEAT,
              "control_validation": read_control_validation(root)}
    write_json(review / "manifest.json", result)
    body = introduction(read_control_validation(root)) + '<p class="note">Pending complete formal Silver Wolf baseline output. No comparison result has been rendered or substituted.</p><ul>'
    body += ''.join('<li>' + html.escape(problem) + '</li>' for problem in problems) + '</ul>'
    body += '<p>Planned: synchronized full clip, frames 30-77 at normal and quarter speed, dense and complete frame sheets, and equal-crop details for frames 40-42. All frame numbers are zero-based.</p><p><a href="manifest.json">Current status</a></p>'
    write_page(review / "index.html", body)
    write_json(root / "analysis/renderer_qa.json", {"status": "pending_formal_output", "experimental_render_completed": False,
               "synthetic_media_created": False, "problems": problems, "visual_review": "not performed; actual new output is pending"})
    return result


def decode(path, compact=False):
    tile = COMPACT_TILE if compact else FULL_TILE
    video_filter = ("select=between(n\\,30\\,77),crop=736:736:288:0,scale=368:368:flags=lanczos" if compact
                    else "scale=656:368:flags=lanczos")
    count = len(EVENT) if compact else COUNT
    raw = subprocess.run(
        [executable("ffmpeg"), "-v", "error", "-xerror", "-threads", "2", "-i", str(path), "-vf", video_filter,
         "-fps_mode", "passthrough", "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        check=True, capture_output=True, timeout=180).stdout
    frame_bytes = tile[0] * tile[1] * 3
    if len(raw) != count * frame_bytes:
        raise ValueError("Unexpected decoded frame count: " + str(path))
    return [Image.frombytes("RGB", tile, raw[index * frame_bytes:(index + 1) * frame_bytes]) for index in range(count)]


def compose(sequences, offset, frame, compact=False):
    if len(sequences) != 3:
        raise ValueError("Exactly three independently decoded inputs are required")
    tile, size = (COMPACT_TILE, COMPACT_ROW) if compact else (FULL_TILE, FULL_ROW)
    row = Image.new("RGB", size, "black")
    draw = ImageDraw.Draw(row)
    title_font = ImageFont.truetype(str(FONT), 16 if compact else 20)
    detail_font = ImageFont.truetype(str(FONT), 12 if compact else 14)
    image_y, text_y, detail_y = (0, 371, 392) if compact else (0, 371, 395)
    for column, (label, sequence) in enumerate(zip(LABELS, sequences)):
        left = column * tile[0]
        row.paste(sequence[offset], (left, image_y))
        draw.text((left + 8, text_y), label, font=title_font, fill="white")
        draw.text((left + 8, detail_y), f"frame {frame:03d} | {frame / FPS:.3f}s", font=detail_font, fill="white")
    return row


def encode(rows, path, fps):
    size = rows[0].size
    temporary = path.with_name(path.stem + ".partial.mp4")
    command = [executable("ffmpeg"), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{size[0]}x{size[1]}", "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264",
               "-threads", "2", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temporary)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for row in rows:
            if row.size != size:
                raise ValueError("Inconsistent comparison row size")
            process.stdin.write(row.tobytes())
        process.stdin.close()
        error = process.stderr.read().decode("utf-8", errors="replace")
        if process.wait(timeout=180):
            raise RuntimeError("ffmpeg failed: " + error[-1000:])
        info = probe(temporary)
        check_geometry(info, len(rows), fps, size)
        temporary.replace(path)
        return {"probe": info, "sha256": fingerprint(path)}
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
        sheet = Image.new("RGB", (FULL_ROW[0], FULL_ROW[1] * len(part)), "black")
        for offset, frame in enumerate(part):
            sheet.paste(rows[frame], (0, offset * FULL_ROW[1]))
        path = folder / f"{prefix}_{part[0]:03d}-{part[-1]:03d}.jpg"
        sheet.save(path, quality=95, subsampling=0)
        with Image.open(path) as checked:
            checked.load()
            if checked.size != sheet.size:
                raise ValueError("Sheet dimensions do not match")
        records.append({"file": str(path), "frames": part, "sha256": fingerprint(path)})
    return records


def compact_assets(paths, output):
    output.mkdir(parents=True, exist_ok=True)
    sequences = [decode(path, compact=True) for path in paths]
    rows = [compose(sequences, offset, frame, compact=True) for offset, frame in enumerate(EVENT)]
    sheet = Image.new("RGB", (COMPACT_ROW[0], COMPACT_ROW[1] * 3), "black")
    for row_number, frame in enumerate(KEYFRAMES):
        sheet.paste(rows[EVENT.index(frame)], (0, row_number * COMPACT_ROW[1]))
    path = output / "compact_frames_040-042.png"
    sheet.save(path)
    with Image.open(path) as checked:
        checked.load()
        if checked.size != (1104, 1236):
            raise ValueError("Compact sheet dimensions do not match")
        for row_number, frame in enumerate(KEYFRAMES):
            for column in range(3):
                box = (column * 368, row_number * 412, (column + 1) * 368, row_number * 412 + 368)
                if checked.crop(box).tobytes() != sequences[column][EVENT.index(frame)].tobytes():
                    raise ValueError("Compact cell does not match the corresponding original-frame crop")
    videos = {name: encode(rows, output / name, fps) for name, fps in (
        ("compact_frames_030-077.mp4", 24), ("compact_frames_030-077_quarter_speed.mp4", 6))}
    return {"crop_original_xywh": CROP, "tile_size": list(COMPACT_TILE), "row_size": list(COMPACT_ROW),
            "caption_position": "below images only", "same_crop_and_scale_in_all_columns": True,
            "sheet": {"file": "compact/" + path.name, "frames": KEYFRAMES, "size": [1104, 1236],
                      "sha256": fingerprint(path), "all_9_tiles_match_decoded_original_frame_crops": True},
            "videos": videos, "source_frames": EVENT}


def verify_links(review):
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.paths = []

        def handle_starttag(self, tag, attrs):
            self.paths.extend(value for key, value in attrs if key in ("href", "src") and value and not value.startswith("#"))
    links = Links()
    links.feed((review / "index.html").read_text())
    if not all((review / path).resolve().is_file() for path in links.paths):
        raise ValueError("Review contains a broken local media link")
    return len(links.paths)


def ready_page(review, groups, control):
    body = introduction(control)
    body += '<p>All three columns use the same zero-based frame index and original timestamp. Source event: frames 39-44, core 41-42. The later action at 54-68 is separate. These source labels do not assert generated success.</p>'
    body += '<section class="compact"><h2>Compact event detail</h2><p>Identical native crop x288, y0, 736 &times; 736, scaled to 368 &times; 368. Rows show frames 40, 41 and 42, covering the source core at 41-42 and the earlier weighted-output gesture at 40-41; captions remain below the images.</p><a href="compact/compact_frames_040-042.png"><img src="compact/compact_frames_040-042.png" alt="Same-frame source, Silver Wolf baseline and Silver Wolf x3 crops at frames 40-42"></a>'
    for title, name in (("Quarter speed: 48 frames at 6 FPS, 8 seconds", "compact_frames_030-077_quarter_speed.mp4"),
                        ("Normal speed: 48 frames at 24 FPS, 2 seconds", "compact_frames_030-077.mp4")):
        body += f'<p>{title}</p><video controls preload="metadata" src="compact/{name}"></video><a href="compact/{name}">Open compact video</a>'
    body += '</section><p>Full-frame views below scale each complete 1312 &times; 736 frame equally to 656 &times; 368. Quarter-speed views encode the same frames at 6 FPS; no interpolation, repeats or independent retiming. Review videos are silent; raw media are preserved.</p>'
    for title, name in (("Complete clip: 141 frames at 24 FPS, 5.875 seconds", "comparison_full.mp4"),
                        ("Frames 30-77: normal speed, 2 seconds", "comparison_frames_030-077.mp4"),
                        ("Frames 30-77: quarter speed, 8 seconds", "comparison_frames_030-077_quarter_speed.mp4")):
        body += f'<section><h2>{title}</h2><video controls preload="metadata" src="{name}"></video><a href="{name}">Open full-frame video</a></section>'
    for title, key in (("Dense context: every frame 30-77", "dense_030_077"), ("Full context: every frame 0-140", "all_frames")):
        body += f'<section><h2>{title}</h2><p>Three time rows per sheet; SOURCE / SILVER WOLF BASELINE / SILVER WOLF x3 across every row.</p><details><summary>Show all frame sheets</summary>'
        for record in groups[key]:
            body += f'<a href="{record["file"]}"><img loading="lazy" src="{record["file"]}" alt="Same-index triplets: frames {record["frames"][0]}-{record["frames"][-1]}"></a>'
        body += '</details></section>'
    body += '<p><a href="manifest.json">Media manifest and interpretation limits</a> &middot; <a href="../analysis/renderer_qa.json">Renderer checks</a></p>'
    write_page(review / "index.html", body)


def render(root):
    root = root.resolve()
    for protected in (WEIGHTED_ROOT.resolve(), FIREFLY_ROOT.resolve(), PILOT_ROOT.resolve()):
        if root == protected or root.is_relative_to(protected):
            raise ValueError("Refuse writes into an existing sealed archive")
    paths = media_paths(root)
    reference = root / "inputs/silverwolf_reference.png"
    history = root / f"logs/{RUN}_history.json"
    problems = ["Pending media: " + str(path) for path in paths + [reference] if not path.is_file()]
    if not history.is_file():
        problems.append("Pending successful formal history: " + str(history))
    else:
        try:
            formal_history(history)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            problems.append(f"Formal history is not complete: {error}")
    if problems:
        return pending(root, problems)
    infos, timings, signatures = [], [], []
    for path in paths:
        try:
            before = signature(path)
            info = probe(path)
            check_geometry(info)
            timing = check_timestamps(path)
            if signature(path) != before:
                raise ValueError("Input changed during completeness checks")
            infos.append(info)
            timings.append(timing)
            signatures.append(before)
        except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as error:
            problems.append(f"Media is not complete: {path}: {error}")
    if problems:
        return pending(root, problems)
    with Image.open(reference) as image:
        image.load()
        reference_size = list(image.size)
    pending(root, ["Preflight passed; CPU render and derivative validation are running"])
    hashes = [fingerprint(path) for path in paths]
    try:
        sequences = [decode(path) for path in paths]
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return pending(root, [f"Media decode incomplete: {error}"])
    rows = [compose(sequences, frame, frame) for frame in range(COUNT)]
    del sequences
    review = root / "review"
    videos = {}
    for name, selected, fps, bounds in (
        ("comparison_full.mp4", rows, 24, [0, 140]),
        ("comparison_frames_030-077.mp4", rows[30:78], 24, [30, 77]),
        ("comparison_frames_030-077_quarter_speed.mp4", rows[30:78], 6, [30, 77]),
    ):
        videos[name] = {**encode(selected, review / name, fps), "source_frames_inclusive": bounds}
    groups = {"dense_030_077": sheets(rows, EVENT, review / "dense_030_077", "dense"),
              "all_frames": sheets(rows, list(range(COUNT)), review / "all_frames", "frames")}
    del rows
    for records in groups.values():
        for record in records:
            record["file"] = str(Path(record["file"]).relative_to(review))
    compact = compact_assets(paths, review / "compact")
    if any(signature(path) != prior for path, prior in zip(paths, signatures)):
        return pending(root, ["An input changed while rendering; current derivatives are not approved for review"])
    result = {"status": "ready", "rendered_utc": datetime.now(timezone.utc).isoformat(), "column_labels": list(LABELS),
              "new_formal_runs_requested": 1, "new_formal_run": RUN, "benchmark_excluded": True, "synthetic_results": False,
              "inputs": [{"label": label, "path": str(path), "sha256": digest, "probe": info, "timestamps": timing}
                         for label, path, digest, info, timing in zip(LABELS, paths, hashes, infos, timings)],
              "formal_history": {"path": str(history), "sha256": fingerprint(history)},
              "silver_wolf_reference": {"path": str(reference), "sha256": fingerprint(reference), "size": reference_size},
              "requested_settings": {"seed": 2026101312, "steps": 20, "baseline_event_weight": 1, "weighted_event_weight": 3, "prompt_match": "nominal; consult control validator"},
              "videos": videos, "sheets": groups, "compact": compact, "full_tile_size": list(FULL_TILE),
              "full_comparison_size": list(FULL_ROW), "frame_numbering": "zero-based; original timestamp = frame / 24",
              "caption_position": "below images in both full-frame and compact views",
              "source_event_frames_inclusive": [39, 44], "source_core_frames": [41, 42], "separate_later_event_frames": [54, 68],
              "temporal_alignment": "Same frame index in every column; no independent retiming, interpolation or repeated frames",
              "spatial_alignment": "Full frames use equal scaling; compact details use identical native crop and 0.5x scaling",
              "audio": "Silent derivatives; raw media unchanged", "interpretation_limit": CAVEAT,
              "control_validation": read_control_validation(root), "causal_matching_claim": "defer to the control validator; never infer from nominal seed/settings",
              "note": "Rendering verifies presentation only. Identity/motion quality and experimental controls require separate review."}
    write_json(review / "manifest.json", result)
    qa = {"status": "media_checks_passed_visual_review_pending", "experimental_render_completed": True,
          "synthetic_media_created": False, "videos": videos, "compact": compact,
          "dense_sheet_count": len(groups["dense_030_077"]), "full_sheet_count": len(groups["all_frames"]),
          "dense_exact_coverage": [f for r in groups["dense_030_077"] for f in r["frames"]] == EVENT,
          "full_exact_coverage": [f for r in groups["all_frames"] for f in r["frames"]] == list(range(COUNT)),
          "raw_inputs_unchanged_during_render": True, "visual_review": "pending actual-media visual inspection"}
    write_json(root / "analysis/renderer_qa.json", qa)
    ready_page(review, groups, result["control_validation"])
    qa["local_links_checked"] = verify_links(review)
    qa["all_local_links_exist"] = True
    write_json(root / "analysis/renderer_qa.json", qa)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = render(args.root)
    print(json.dumps({"status": result["status"], "problems": result.get("problems", []),
                      "review": str(args.root / "review/index.html")}))
    raise SystemExit(2 if result["status"] == "pending" else 0)


if __name__ == "__main__":
    main()
