#!/usr/bin/env python3
"""CPU-only, deterministic full-frame SOURCE / MUSK BASELINE / MUSK x3 review.

Writes only review/ and analysis/renderer_qa.json. Requires both completed
formal histories and three complete 141-frame, 24-FPS inputs. Missing
results produce a truthful pending page (exit 2); no substitute output is used.
Rendering conventions reuse the validated factor3 full/compact renderers.
"""

import argparse
from datetime import datetime, timezone
from fractions import Fraction
from functools import lru_cache
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont


LABELS = ("SOURCE", "MUSK BASELINE", "MUSK x3")
CAPTION_LABELS = ("1.参考视频", "2.编辑后视频", "3.编辑＋短时动作三倍加权后视频")
CAPTION_LEGEND = "角色替换"
RUNS = ("05_musk_s1_baseline", "05_musk_s1_weight3")
SOURCE = "05_real_megumi_v.mp4"
REFERENCE = "elon_musk_royal_society.jpg"
ORIGINAL, FULL_TILE, FULL_ROW = (1312, 736), (656, 368), (1968, 416)
COUNT, FPS = 141, 24
EVENT = list(range(40, 101))
CAPTION_FONT_SIZE = 22
CAVEAT = "This is one source and one seed pair. The manually chosen emphasis window includes adjacent motion and all spatial content; it does not establish general benefit or guarantee correction of global timing. Media readiness is not a control-verification pass."
STYLE = """body{font:16px system-ui,sans-serif;background:#080808;color:#fff;margin:0 auto;padding:24px;max-width:1968px}h1{font-size:26px}h2{font-size:21px}p{line-height:1.55;color:#ddd}a{color:#fff;overflow-wrap:anywhere}section{border-top:1px solid #555;margin:24px 0;padding-top:16px}video,img{display:block;width:100%;height:auto;background:#000;margin:14px 0}summary{cursor:pointer}.note{border-left:3px solid #fff;padding-left:14px}li{line-height:1.6}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:32em;overflow:auto;border:1px solid #555;padding:12px;font-size:13px}"""

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def write_page(path, body):
    content = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    content += f'<title>H3 synthetic Musk dance comparison</title><style>{STYLE}</style><body>{body}</body></html>\n'
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
    return [root / "inputs" / SOURCE] + [root / "outputs" / f"{run}_00001_.mp4" for run in RUNS]


def read_control_validation(root):
    """Expose the validator's own findings without inventing a causal verdict."""
    path = root / "analysis/pair_verification.json"
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
        body += '<p><a href="control_validation.json">Open the complete control-verification snapshot</a>.</p>'
        body += '<details><summary>Complete validator report</summary><pre>'
        body += html.escape(json.dumps(control["report"], ensure_ascii=False, indent=2)) + '</pre></details>'
    else:
        body += '<p>' + html.escape(control["message"]) + '</p>'
    return body + '</section>'


def decode(path):
    raw = subprocess.run(
        [executable("ffmpeg"), "-v", "error", "-xerror", "-threads", "2", "-i", str(path),
         "-vf", "scale=656:368:flags=lanczos", "-fps_mode", "passthrough", "-an",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        check=True, capture_output=True, timeout=180).stdout
    frame_bytes = FULL_TILE[0] * FULL_TILE[1] * 3
    if len(raw) != COUNT * frame_bytes:
        raise ValueError("Expected exactly 141 complete decoded frames: " + str(path))
    return [Image.frombytes("RGB", FULL_TILE, raw[i * frame_bytes:(i + 1) * frame_bytes]) for i in range(COUNT)]


@lru_cache(maxsize=1)
def caption_font():
    candidates = [Path("/System/Library/Fonts/PingFang.ttc")]
    candidates.extend(sorted(Path("/System/Library/AssetsV2/com_apple_MobileAsset_Font8").glob("*.asset/AssetData/PingFang.ttc")))
    for path in candidates:
        if path.is_file():
            font = ImageFont.truetype(str(path), CAPTION_FONT_SIZE, index=3)
            return font, {"path": str(path), "face_index": 3, "family_style": list(font.getname()), "size_px": CAPTION_FONT_SIZE}
    raise RuntimeError("An existing PingFang SC font is required; no font will be downloaded")


def draw_caption_band(canvas, image_height, labels=CAPTION_LABELS, legend=CAPTION_LEGEND):
    """Reusable equal-column Chinese footer; never draws into the image area."""
    if canvas.width % len(labels):
        raise ValueError("Caption columns require equal integer widths")
    font, _ = caption_font()
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, image_height, canvas.width - 1, canvas.height - 1), fill="black")
    tile_width = canvas.width // len(labels)
    positions = [(legend, 24, False)] + [(label, (index + 0.5) * tile_width, True) for index, label in enumerate(labels)]
    layout = []
    for text, x, centered in positions:
        left, top, right, bottom = font.getbbox(text)
        width, height = right - left, bottom - top
        start_x = round(x - width / 2) if centered else x
        start_y = image_height + 10
        if start_x < 0 or start_x + width > canvas.width or start_y + height > canvas.height - 4:
            raise ValueError("Chinese caption does not fit the existing footer geometry")
        draw.text((start_x - left, start_y - top), text, font=font, fill="white")
        layout.append({"text": text, "bbox": [start_x, start_y, start_x + width, start_y + height]})
    if layout[0]["bbox"][2] + 12 > layout[1]["bbox"][0]:
        raise ValueError("Left legend overlaps the centered first-column caption")
    return layout


def caption_metadata():
    _, font = caption_font()
    return {"language": "zh-CN", "legend": CAPTION_LEGEND, "column_captions": list(CAPTION_LABELS),
            "font": font, "alignment": "legend at far left; each column caption centered", "background": "black",
            "foreground": "white", "position": "existing footer below the complete image", "visible_frame_time_text": False,
            "frame_evidence": "Zero-based indices remain in filenames, manifests, source timestamps and HTML metadata",
            "intervention_wording": "Threefold short-action weighting, not prompt emphasis"}


def compose(sequences, frame):
    if len(sequences) != 3:
        raise ValueError("Three independently decoded formal inputs are required")
    row = Image.new("RGB", FULL_ROW, "black")
    for column, sequence in enumerate(sequences):
        x = column * FULL_TILE[0]
        row.paste(sequence[frame], (x, 0))
    draw_caption_band(row, FULL_TILE[1])
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



def verify_links(review):
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.paths = []

        def handle_starttag(self, tag, attrs):
            self.paths.extend(value for key, value in attrs if key in ("href", "src") and value and not value.startswith(("#", "https://", "http://")))
    links = Links()
    links.feed((review / "index.html").read_text())
    if not all((review / path).resolve().is_file() for path in links.paths):
        raise ValueError("Review contains a broken local media link")
    return len(links.paths)


def configuration(root):
    plan_path = root / "configs/plan.json"
    plan = json.loads(plan_path.read_text())
    if plan["formal_jobs"] != list(RUNS) or plan["source"] != SOURCE:
        raise ValueError("Plan does not match the named formal pair and source")
    if plan["sampling"]["output"] != [1312, 736, 141, 24]:
        raise ValueError("Plan geometry differs from the full-frame renderer")
    graphs = [json.loads((root / f"configs/{run}.json").read_text()) for run in RUNS]
    for graph, run, factor in zip(graphs, RUNS, (1, 3)):
        if graph["50"]["inputs"]["factor"] != factor or graph["14"]["inputs"]["filename_prefix"] != run:
            raise ValueError("Graph factor or output name does not match the formal comparison")
        if graph["22"]["inputs"]["file"] != SOURCE or graph["21"]["inputs"]["image"] != REFERENCE:
            raise ValueError("Graph source or reference differs from the review provenance")
    return {"plan": plan, "plan_sha256": fingerprint(plan_path),
            "graphs": [{"run": run, "sha256": fingerprint(root / f"configs/{run}.json"),
                        "factor": graph["50"]["inputs"]["factor"], "seed": graph["6"]["inputs"]["noise_seed"],
                        "prompt_sha256": hashlib.sha256(graph["5"]["inputs"]["prompt"].encode()).hexdigest()}
                       for graph, run in zip(graphs, RUNS)],
            "scope": "Graph metadata documents intended controls; actual parity is determined by the verifier."}


def support_files(root, config):
    """Bundle all locally linked provenance inside review for later copying."""
    review = root / "review"
    review.mkdir(parents=True, exist_ok=True)
    reference = root / "inputs" / REFERENCE
    provenance = json.loads((root / "inputs/reference_provenance.json").read_text())
    if fingerprint(reference) != provenance["sha256"]:
        raise ValueError("Reference photograph differs from the recorded provenance")
    with Image.open(reference) as image:
        image.load()
        if list(image.size) != provenance["original_dimensions"]:
            raise ValueError("Reference photograph dimensions differ from provenance")
    shutil.copy2(reference, review / REFERENCE)
    shutil.copy2(root / "inputs/CREDITS.txt", review / "CREDITS.txt")
    source = json.loads((root / "inputs/source_metadata.json").read_text())
    if fingerprint(root / "inputs" / SOURCE) != source["output_sha256"]:
        raise ValueError("Source clip differs from its recorded provenance")
    write_json(review / "provenance.json", {"reference": provenance, "source_metadata": source, "configuration": config,
               "source_metadata_note": "Historical recolor-task fields describe source selection; the current graphs request a synthetic Musk identity edit.",
               "synthetic_media_disclosure": "MUSK BASELINE and MUSK x3 are AI-generated edits of the source dancer, not recordings of Elon Musk performing this dance."})
    control = read_control_validation(root)
    write_json(review / "control_validation.json", control["report"] if control["available"] else control)
    return control


def introduction(config):
    plan = config["plan"]
    body = '<h1>H3 synthetic Musk dance comparison</h1>'
    body += '<p>The Musk columns are AI-generated identity edits of the source dancer.</p>'
    body += f'<p>One source/seed pair &middot; {plan["sampling"]["steps"]} steps &middot; seed {plan["seed"]} &middot; weights x1 / x3 &middot; source target frames 50-65 (core 53-61).</p>'
    return body


def credits():
    return ('<section><h2>Reference and provenance</h2>'
            f'<p><a href="{REFERENCE}">Reference photograph</a>: Debbie Rowe / The Royal Society, '
            '<a href="https://commons.wikimedia.org/wiki/File:Elon_Musk_Royal_Society.jpg">Wikimedia Commons</a>, '
            '<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC BY-SA 3.0</a>. The bundled JPEG is unchanged; generated edits and native model preprocessing are documented separately.</p>'
            '<p>Dance source: <a href="https://www.youtube.com/watch?v=3vd5c8XMP9c">Megumi creator upload</a>, existing excerpt 37.0-42.875 seconds. No permissive source-video licence is recorded in the supplied metadata.</p>'
            '<p><a href="CREDITS.txt">Credits</a> &middot; <a href="provenance.json">Provenance and configuration</a> &middot; '
            '<a href="manifest.json">Media manifest</a> &middot; <a href="renderer_qa.json">Renderer checks</a></p></section>')


def review_details(control):
    status = html.escape(str(control["reported_status"]))
    body = f'<section><details><summary>Control verification: {status} &middot; limits and credits</summary>'
    body += validation_panel(control) + f'<p>{CAVEAT}</p>'
    body += '<p>Source event labels identify the source timing; generated gestures require separate visual assessment.</p>'
    return body + credits() + '</details></section>'


def save_qa(root, qa):
    write_json(root / "analysis/renderer_qa.json", qa)
    write_json(root / "review/renderer_qa.json", qa)


def pending(root, problems, config):
    control = support_files(root, config)
    review = root / "review"
    result = {"status": "pending", "checked_utc": datetime.now(timezone.utc).isoformat(), "problems": problems,
              "column_labels": list(LABELS), "formal_runs": list(RUNS), "synthetic_results_substituted": False,
              "comparison_rendered": False, "interpretation_limit": CAVEAT, "control_verification": control}
    write_json(review / "manifest.json", result)
    qa = {"status": "pending_formal_outputs", "experimental_render_completed": False, "synthetic_results_substituted": False,
          "problems": problems, "visual_review": "not performed; formal comparison outputs are pending"}
    save_qa(root, qa)
    body = introduction(config) + '<p class="note">Pending both completed formal outputs. No comparison result has been rendered or substituted.</p><ul>'
    body += ''.join('<li>' + html.escape(problem) + '</li>' for problem in problems) + '</ul>'
    body += '<p>Planned: all 141 frames at 24 FPS; frames 40-100 at 24 FPS and quarter-speed 6 FPS; complete and dense sheets with three time rows per page. All frame numbers are zero-based.</p>'
    write_page(review / "index.html", body + review_details(control))
    qa["self_contained_local_links_checked"] = verify_links(review)
    save_qa(root, qa)
    return result


def ready_page(review, groups, control, config):
    body = introduction(config)
    for title, name in (("Complete clip: 141 frames at 24 FPS, 5.875 seconds", "comparison_full.mp4"),
                        ("Frames 40-100: normal speed, 61 frames at 24 FPS", "comparison_frames_040-100.mp4"),
                        ("Frames 40-100: quarter speed, the same 61 frames at 6 FPS", "comparison_frames_040-100_quarter_speed.mp4")):
        body += f'<section><h2>{title}</h2><video controls preload="metadata" src="{name}"></video><a href="{name}">Open video</a></section>'
    body += '<p>Full 1312 &times; 736 frames are scaled equally to 656 &times; 368, retaining the original letterboxing. Columns share the same zero-based frame index and source timestamp: 24 FPS normally, or the same frames at 6 FPS for quarter speed without interpolation. Review videos are silent.</p>'
    for title, key in (("Dense event context: every frame 40-100", "dense_040_100"), ("Full context: every frame 0-140", "all_frames")):
        body += f'<section><h2>{title}</h2><p>Three time rows per sheet (the final dense sheet has one row). 中文底栏：1.参考视频 / 2.编辑后视频 / 3.编辑＋短时动作三倍加权后视频。帧号与时间保留在文件名和元数据中。</p><details><summary>Show all frame sheets</summary>'
        for record in groups[key]:
            body += f'<a href="{record["file"]}"><img loading="lazy" src="{record["file"]}" alt="Same-index triplets at frames {record["frames"][0]}-{record["frames"][-1]}"></a>'
        body += '</details></section>'
    write_page(review / "index.html", body + review_details(control))


def render(root):
    root = root.resolve()
    if root.name != "h3-musk-real-dance-pair-20261014":
        raise ValueError("Render only into this task's named directory; copy the completed review folder for delivery")
    config = configuration(root)
    paths = media_paths(root)
    histories = [root / f"logs/{run}_history.json" for run in RUNS]
    problems = ["Pending media: " + str(path) for path in paths if not path.is_file()]
    for history in histories:
        if not history.is_file():
            problems.append("Pending completed formal history: " + str(history))
        else:
            try:
                formal_history(history)
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
                problems.append(f"Formal history is incomplete: {history}: {error}")
    if problems:
        return pending(root, problems, config)
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
        return pending(root, problems, config)
    pending(root, ["Preflight passed; CPU comparison render and media validation are running"], config)
    hashes = [fingerprint(path) for path in paths]
    try:
        sequences = [decode(path) for path in paths]
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return pending(root, [f"Media decode incomplete: {error}"], config)
    rows = [compose(sequences, frame) for frame in range(COUNT)]
    del sequences
    review = root / "review"
    videos = {}
    for name, selected, fps, bounds in (
        ("comparison_full.mp4", rows, 24, [0, 140]),
        ("comparison_frames_040-100.mp4", rows[40:101], 24, [40, 100]),
        ("comparison_frames_040-100_quarter_speed.mp4", rows[40:101], 6, [40, 100]),
    ):
        videos[name] = {**encode(selected, review / name, fps), "source_frames_inclusive": bounds}
    groups = {"dense_040_100": sheets(rows, EVENT, review / "dense_040_100", "dense"),
              "all_frames": sheets(rows, list(range(COUNT)), review / "all_frames", "frames")}
    for records in groups.values():
        for record in records:
            record["file"] = str(Path(record["file"]).relative_to(review))
    if any(signature(path) != prior for path, prior in zip(paths, signatures)):
        return pending(root, ["An input changed during rendering; derivatives are not approved for review"], config)
    control = support_files(root, config)
    result = {"status": "ready", "rendered_utc": datetime.now(timezone.utc).isoformat(), "column_labels": list(LABELS),
              "formal_runs": list(RUNS), "technical_benchmark_excluded": config["plan"]["technical_benchmark"],
              "inputs": [{"label": label, "path": str(path), "sha256": digest, "probe": info, "timestamps": timing}
                         for label, path, digest, info, timing in zip(LABELS, paths, hashes, infos, timings)],
              "formal_histories": [{"path": str(path), "sha256": fingerprint(path)} for path in histories],
              "videos": videos, "sheets": groups, "tile_size": list(FULL_TILE), "comparison_size": list(FULL_ROW),
              "caption_style": caption_metadata(),
              "caption_position": "below all complete frames", "source_event_full_frames": [50, 65], "source_event_core_frames": [53, 61],
              "context_frames": [40, 100], "source_letterbox_pixels": {"top": 70, "bottom": 69},
              "spatial_alignment": "Complete 1312x736 frames scaled equally to 656x368; no cropping, overlays or independent enlargement",
              "temporal_alignment": "Same frame index and original timestamp in every column; no independent retiming, interpolation or repeated frames",
              "slow_motion_method": "Same 61 context frames encoded at 6 FPS", "audio": "Silent comparison derivatives; raw media preserved",
              "synthetic_media_disclosure": "Musk columns are generated identity edits, not authentic performance recordings",
              "interpretation_limit": CAVEAT, "control_verification": control, "media_readiness_is_control_verification": False,
              "self_contained_review": True, "reference_and_credits": "provenance.json"}
    write_json(review / "manifest.json", result)
    qa = {"status": "media_checks_passed_visual_review_pending", "experimental_render_completed": True,
          "videos": videos, "dense_sheet_count": len(groups["dense_040_100"]), "full_sheet_count": len(groups["all_frames"]),
          "dense_exact_coverage": [frame for record in groups["dense_040_100"] for frame in record["frames"]] == EVENT,
          "full_exact_coverage": [frame for record in groups["all_frames"] for frame in record["frames"]] == list(range(COUNT)),
          "raw_inputs_unchanged_during_render": True, "no_crop_or_blackbar_overlay": True,
          "control_report_status": control["reported_status"], "visual_review": "pending actual comparison media inspection"}
    save_qa(root, qa)
    ready_page(review, groups, control, config)
    qa["self_contained_local_links_checked"] = verify_links(review)
    qa["all_local_links_exist"] = True
    save_qa(root, qa)
    return result


def refresh_existing_html(path):
    """Change the caption explanation only; retain custom review/raw-link sections."""
    previous = path.read_text()
    updated = previous.replace(
        "SOURCE / MUSK BASELINE / MUSK x3 across each row; white captions below the complete frame.",
        "中文底栏：1.参考视频 / 2.编辑后视频 / 3.编辑＋短时动作三倍加权后视频。帧号与时间保留在文件名和元数据中。")
    metadata = '<meta name="comparison-caption-style" content="zh-CN black bottom row; threefold short-action weighting"><meta name="comparison-frame-evidence" content="Zero-based frame indices in filenames, sheet manifests and image alt metadata; source seconds = frame / 24">'
    if 'name="comparison-caption-style"' not in updated:
        updated = updated.replace("<title>", metadata + "<title>", 1)
    raw_links = re.findall(r'<a\b[^>]*href="raw/[^>]*>.*?</a>', previous)
    selected_sections = re.findall(r'<section\b[^>]*id="selected[^\"]*"[^>]*>.*?</section>', previous, re.DOTALL)
    if any(part not in updated for part in raw_links + selected_sections):
        raise ValueError("Caption explanation update would alter a custom review section")
    temporary = path.with_suffix(".html.tmp")
    temporary.write_text(updated)
    temporary.replace(path)
    return {"raw_link_count_preserved": len(raw_links), "selected_section_count_preserved": len(selected_sections)}


def refresh_captions(root, delivery=None):
    """Rerender existing ready media while merging metadata and preserving HTML."""
    root = root.resolve()
    review = root / "review"
    destinations = [review]
    if delivery is not None:
        delivery = delivery.resolve()
        if delivery == review or not delivery.is_dir():
            raise ValueError("Delivery must be a separate existing review directory")
        destinations.append(delivery)
    manifest = json.loads((review / "manifest.json").read_text())
    if manifest.get("status") != "ready" or manifest.get("formal_runs") != list(RUNS):
        raise ValueError("Caption refresh requires this completed formal pair")
    managed = set(manifest["videos"])
    managed.update(record["file"] for records in manifest["sheets"].values() for record in records)
    protected = {}
    for folder in destinations:
        for path in folder.rglob("*"):
            if path.is_file() and str(path.relative_to(folder)) not in managed and path.name not in ("index.html", "manifest.json", "renderer_qa.json"):
                protected[str(path)] = fingerprint(path)
    paths = media_paths(root)
    for run in RUNS:
        formal_history(root / f"logs/{run}_history.json")
    for path, record in zip(paths, manifest["inputs"]):
        info = probe(path)
        check_geometry(info)
        check_timestamps(path)
        if fingerprint(path) != record["sha256"]:
            raise ValueError("Raw media differs from the verified comparison manifest")
        protected[str(path)] = record["sha256"]
    sequences = [decode(path) for path in paths]
    rows = [compose(sequences, frame) for frame in range(COUNT)]
    if any(rows[frame].crop((column * 656, 0, (column + 1) * 656, 368)).tobytes() != sequences[column][frame].tobytes()
           for frame in range(COUNT) for column in range(3)):
        raise ValueError("Caption refresh changed a decoded image tile")
    del sequences
    videos = {}
    for name, selected, fps in (("comparison_full.mp4", rows, 24),
                                ("comparison_frames_040-100.mp4", rows[40:101], 24),
                                ("comparison_frames_040-100_quarter_speed.mp4", rows[40:101], 6)):
        videos[name] = encode(selected, review / name, fps)
    groups = {"dense_040_100": sheets(rows, EVENT, review / "dense_040_100", "dense"),
              "all_frames": sheets(rows, list(range(COUNT)), review / "all_frames", "frames")}
    for records in groups.values():
        for record in records:
            record["file"] = str(Path(record["file"]).relative_to(review))
    # Actual same-index preview for visual QA; no synthetic or substituted input.
    preview = review / "caption_style_frame_056.png"
    rows[56].save(preview)
    rows[56].crop((0, 368, FULL_ROW[0], FULL_ROW[1])).save(review / "caption_style_band.png")
    style = caption_metadata()
    checked = {"all_423_composed_image_tiles_equal_decoded_inputs": True, "frames_unchanged": True,
               "visible_captions": style, "comparison_videos_updated": 3, "comparison_jpgs_updated": 68,
               "visual_review": "pending inspection against the supplied caption reference", "destinations": []}
    for folder in destinations:
        if folder != review:
            for relative in sorted(managed):
                target = folder / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(review / relative, target)
            for name in ("caption_style_frame_056.png", "caption_style_band.png"):
                shutil.copy2(review / name, folder / name)
        current = json.loads((folder / "manifest.json").read_text())
        for name, record in videos.items():
            current["videos"][name].update(record)
        for key, records in groups.items():
            fresh = {record["file"]: record for record in records}
            for record in current["sheets"][key]:
                replacement = fresh[record["file"]]
                if record["frames"] != replacement["frames"]:
                    raise ValueError("A sheet's frame-index evidence would change")
                record["sha256"] = replacement["sha256"]
        current["caption_style"] = style
        current["caption_refreshed_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(folder / "manifest.json", current)
        page_checks = refresh_existing_html(folder / "index.html")
        page_checks["local_links_checked"] = verify_links(folder)
        page_checks["path"] = str(folder)
        checked["destinations"].append(page_checks)
    if any(fingerprint(Path(path)) != digest for path, digest in protected.items()):
        raise ValueError("A protected raw, report, methods or provenance asset changed")
    checked["protected_assets_unchanged"] = True
    checked["protected_asset_sha256"] = protected
    for folder in destinations:
        qa = json.loads((folder / "renderer_qa.json").read_text())
        for name, record in videos.items():
            qa["videos"][name].update(record)
        if "visual_verdict" in qa:
            qa["prior_caption_visual_verdict"] = qa.pop("visual_verdict")
        qa["status"] = "media_checks_passed_chinese_caption_visual_review_pending"
        qa["caption_refresh"] = checked
        qa["visual_review"] = checked["visual_review"]
        write_json(folder / "renderer_qa.json", qa)
        if folder == review:
            write_json(root / "analysis/renderer_qa.json", qa)
    return {"status": "media_checks_passed_chinese_caption_visual_review_pending", "caption_refresh": checked}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--refresh-captions", action="store_true", help="Rerender ready comparisons without replacing custom HTML sections")
    parser.add_argument("--delivery-root", type=Path, help="Existing delivery directory to update during --refresh-captions")
    args = parser.parse_args()
    if args.delivery_root is not None and not args.refresh_captions:
        parser.error("--delivery-root requires --refresh-captions")
    result = refresh_captions(args.root, args.delivery_root) if args.refresh_captions else render(args.root)
    print(json.dumps({"status": result["status"], "problems": result.get("problems", []), "review": str(args.root / "review/index.html")}))
    raise SystemExit(2 if result["status"] == "pending" else 0)


if __name__ == "__main__":
    main()
