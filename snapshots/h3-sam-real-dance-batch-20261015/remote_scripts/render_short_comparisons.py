#!/usr/bin/env python3
"""Render two short Sam identity-edit comparisons using complete formal media.

Writes only review/ and analysis/renderer_qa.json. Each ready case produces one
61-frame, 24-FPS triptych and one PNG preview. Missing results remain pending;
one case can be ready while the other waits. No substituted media are used.
"""

import argparse
from datetime import datetime, timezone
from fractions import Fraction
from functools import lru_cache
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont


LABELS = ("SOURCE", "SAM BASELINE", "SAM x3")
CAPTION_LABELS = ("1.参考视频", "2.编辑后视频", "3.编辑＋短时动作三倍加权后视频")
CAPTION_LEGEND = "角色替换"
CAPTION_FONT_SIZE = 22
REFERENCE = "sam_altman_village_global_20221117_original.jpg"
ORIGINAL, FULL_TILE, FULL_ROW = (1312, 736), (656, 368), (1968, 416)
COUNT, FPS = 141, 24
EVENT = list(range(40, 101))
CASE_SPECS = {
    "05": {"title": "室内舞蹈", "source": "05_real_megumi_v.mp4", "preview_frame": 56,
           "source_url": "https://www.youtube.com/watch?v=3vd5c8XMP9c", "source_window_seconds": [37.0, 42.875],
           "source_event_full_frames": [50, 65], "source_event_core_frames": [53, 61],
           "expected_latent_interval_half_open": [14, 20], "expected_position_bin_coverage": [47, 67],
           "existing_black_borders_pixels": {"top": 70, "bottom": 69, "left": 2, "right": 2}},
    "07": {"title": "床边舞蹈", "source": "07_real_ary_v.mp4", "preview_frame": 61,
           "source_url": "https://www.youtube.com/watch?v=oPnUDTAG0_0", "source_window_seconds": [34.5, 40.375],
           "source_event_full_frames": [54, 69], "source_event_core_frames": [60, 62],
           "expected_latent_interval_half_open": [16, 22], "expected_position_bin_coverage": [52, 72],
           "existing_black_borders_pixels": {"top": 0, "bottom": 0, "left": 2, "right": 2}},
}
CAVEAT = "每个来源只比较一个种子的基础组与三倍加权组。短动作加权也覆盖相邻位置的全部空间内容；这里仅作短片和预览的基本检查，不证明普遍效果，也不作全面动作质量分析。媒体完成与实验控制验证是独立状态。"
STYLE = 'body{font:16px system-ui,sans-serif;background:#080808;color:#fff;margin:0 auto;padding:24px;max-width:1968px}h1{font-size:26px}h2{font-size:21px}p{line-height:1.55;color:#ddd}a{color:#fff;overflow-wrap:anywhere}section{border-top:1px solid #555;margin:24px 0;padding-top:16px}video,img{display:block;width:100%;height:auto;background:#000;margin:14px 0}summary{cursor:pointer}.note{border-left:3px solid #fff;padding-left:14px}li{line-height:1.6}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:32em;overflow:auto;border:1px solid #555;padding:12px;font-size:13px}'


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
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


def read_control_validation(root):
    """Expose the validator's own findings without inventing a causal verdict."""
    path = root / "analysis/batch_verification.json"
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


def validation_panel(control):
    labels = {"pending": "等待验证", "pass": "通过", "passed": "通过", "fail": "未通过",
              "failed": "未通过", "error": "验证发现问题", "unreadable": "报告暂不可读"}
    status = labels.get(control["reported_status"], "请查看审计报告")
    body = f'<section id="control-validation"><h2>实验控制验证</h2><p class="note">独立验证状态：<strong>{status}</strong>。视频可播放不代表实验控制已经通过。</p>'
    body += '<p><a href="control_validation.json">查看完整控制验证记录</a>。本次只做短片与预览的基本检查，不进行全面动作质量分析。</p>'
    if not control["available"]:
        body += '<p>完整控制报告尚未就绪，不能据此认定运行环境或条件已配对。</p>'
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
    expected_jobs = [f"{case_id}_sam_s1_{arm}" for case_id in CASE_SPECS for arm in ("baseline", "weight3")]
    if plan["formal_jobs"] != expected_jobs or plan["technical_benchmark"] is not None or plan["factors"] != [1, 3]:
        raise ValueError("Plan must contain exactly the four formal Sam jobs without a benchmark")
    if plan["sampling"]["output"] != [*ORIGINAL, COUNT, FPS]:
        raise ValueError("Plan output geometry differs from the renderer")
    presentation = plan["presentation"]
    expected_presentation = {"source_frames_inclusive": [40, 100], "fps": 24, "composite_frames": 61,
                             "normal_speed_only": True, "large_visual_review": False}
    if any(presentation.get(key) != value for key, value in expected_presentation.items()):
        raise ValueError("Plan presentation differs from short-only normal-speed rendering")
    if [case["case_id"] for case in plan["cases"]] != list(CASE_SPECS):
        raise ValueError("Plan cases must be ordered 05 then 07")
    cases = {}
    for planned in plan["cases"]:
        case_id = planned["case_id"]
        spec = CASE_SPECS[case_id]
        runs = [f"{case_id}_sam_s1_baseline", f"{case_id}_sam_s1_weight3"]
        for key in ("source", "source_event_full_frames", "source_event_core_frames",
                    "expected_latent_interval_half_open", "expected_position_bin_coverage"):
            if planned[key] != spec[key]:
                raise ValueError(f"Case {case_id} plan differs at {key}")
        if planned["formal_jobs"] != runs or planned["shared_node5_run_id"] != f"{case_id}_sam_shared_conditioning":
            raise ValueError("Case run identities or shared conditioning name differ")
        graphs = [json.loads((root / f"configs/{run}.json").read_text()) for run in runs]
        graph_records = []
        for graph, run, factor in zip(graphs, runs, (1, 3)):
            if graph["50"]["inputs"]["factor"] != factor or graph["14"]["inputs"]["filename_prefix"] != run:
                raise ValueError("Formal graph factor or output name mismatch")
            if graph["22"]["inputs"]["file"] != spec["source"] or graph["21"]["inputs"]["image"] != REFERENCE:
                raise ValueError("Formal graph source or reference photograph mismatch")
            if [graph["50"]["inputs"]["start_frame"], graph["50"]["inputs"]["end_frame"]] != spec["source_event_full_frames"]:
                raise ValueError("Formal graph event differs from the case plan")
            if graph["6"]["inputs"]["noise_seed"] != planned["seed"]:
                raise ValueError("Formal graph seed differs from the case plan")
            graph_records.append({"run": run, "factor": factor,
                                  "sha256": fingerprint(root / f"configs/{run}.json"),
                                  "prompt_sha256": hashlib.sha256(graph["5"]["inputs"]["prompt"].encode()).hexdigest()})
        if graphs[0]["5"] != graphs[1]["5"] or graphs[0]["5"]["inputs"]["run_id"] != planned["shared_node5_run_id"]:
            raise ValueError("Each case must share node 5 exactly within its formal pair")
        cases[case_id] = {**spec, **planned, "graphs": graph_records,
                          "video": f"{case_id}_sam_short_triptych.mp4",
                          "preview": f"{case_id}_sam_preview_frame_{spec['preview_frame']:03d}.png"}
    return {"plan": plan, "plan_sha256": fingerprint(plan_path), "cases": cases,
            "scope": "Intended graph controls only; runtime parity is reported by the independent batch verifier."}


def support_files(root, config, control):
    review = root / "review"
    review.mkdir(parents=True, exist_ok=True)
    reference = root / "inputs" / REFERENCE
    provenance = json.loads((root / "inputs/reference_provenance.json").read_text())
    if provenance["creator"] != "Village Global" or provenance["license"] != "CC BY 2.0":
        raise ValueError("Unexpected Sam reference attribution or licence")
    if fingerprint(reference) != provenance["sha256"]:
        raise ValueError("Sam reference photograph differs from its recorded SHA256")
    with Image.open(reference) as image:
        image.load()
        if list(image.size) != provenance["original_dimensions"]:
            raise ValueError("Sam reference photograph dimensions differ from provenance")
    sources = {}
    for case_id, case in config["cases"].items():
        metadata_path = root / "inputs" / Path(case["source"]).with_suffix(".json")
        metadata = json.loads(metadata_path.read_text())
        expected = {"clip_id": Path(case["source"]).stem, "source_url": case["source_url"],
                    "source_window_seconds": case["source_window_seconds"], "output_frames": COUNT,
                    "output_fps": FPS, "width": ORIGINAL[0], "height": ORIGINAL[1]}
        if any(metadata.get(key) != value for key, value in expected.items()):
            raise ValueError(f"Case {case_id} source metadata identity or geometry mismatch")
        if metadata["event"]["transition_frames_inclusive"] != case["source_event_full_frames"] or metadata["event"]["decisive_frames_inclusive"] != case["source_event_core_frames"]:
            raise ValueError(f"Case {case_id} source metadata event mismatch")
        source_sha = fingerprint(root / "inputs" / case["source"])
        if source_sha != metadata["output_sha256"]:
            raise ValueError(f"Case {case_id} source SHA256 differs from metadata")
        sources[case_id] = {"metadata": metadata, "metadata_sha256": fingerprint(metadata_path),
                            "verified_source_sha256": source_sha,
                            "retained_black_borders_pixels": case["existing_black_borders_pixels"],
                            "renderer_changes": "None to raw input. Complete normalized frames are scaled equally, including all existing borders."}
    shutil.copy2(reference, review / REFERENCE)
    shutil.copy2(root / "inputs/CREDITS.txt", review / "CREDITS.txt")
    write_json(review / "provenance.json", {"reference": provenance, "sources": sources, "configuration": config,
               "source_metadata_note": "Historical recolor prompts describe source selection; current graphs request synthetic Sam Altman identity edits.",
               "conditioning_policy": "Each baseline computes its shared node 5; its weighted run must reuse it. No benchmark. Runtime history is verified separately.",
               "synthetic_media_disclosure": "Generated identity edits, not recordings of Sam Altman performing these dances."})
    write_json(review / "control_validation.json", control["report"] if control["available"] else control)
    return sources


def pending_case(case_id, case, problems, *, status="pending"):
    return {"case_id": case_id, "status": status, "problems": problems,
            "formal_runs": case["formal_jobs"], "comparison_rendered": False,
            "synthetic_results_substituted": False,
            "planned_media": {"video": case["video"], "frames": len(EVENT), "fps": FPS,
                              "duration_seconds": len(EVENT) / FPS, "source_frames_inclusive": [40, 100],
                              "preview": case["preview"], "preview_source_frame": case["preview_frame"]},
            "checks": {"status": "pending_formal_outputs" if status == "pending" else "error",
                       "experimental_render_completed": False,
                       "visual_review": "not performed; actual case comparison media are pending"}}


def render_case(root, case_id, case, source_provenance):
    paths = [root / "inputs" / case["source"]] + [root / "outputs" / f"{run}_00001_.mp4" for run in case["formal_jobs"]]
    histories = [root / f"logs/{run}_history.json" for run in case["formal_jobs"]]
    problems = ["Pending media: " + str(path) for path in paths if not path.is_file()]
    for history in histories:
        if not history.is_file():
            problems.append("Pending successful formal history: " + str(history))
        else:
            try:
                formal_history(history)
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
                problems.append(f"Incomplete formal history: {history}: {error}")
    if problems:
        return pending_case(case_id, case, problems)
    signatures = [signature(path) for path in paths]
    infos, timings = [], []
    for path in paths:
        info = probe(path)
        check_geometry(info)
        infos.append(info)
        timings.append(check_timestamps(path))
    hashes = [fingerprint(path) for path in paths]
    history_hashes = [fingerprint(path) for path in histories]
    if hashes[0] != source_provenance["verified_source_sha256"]:
        raise ValueError("Source changed after provenance verification")
    if any(signature(path) != prior for path, prior in zip(paths, signatures)):
        raise ValueError("Input changed during completeness checks")
    sequences = [decode(path) for path in paths]
    rows = [compose(sequences, frame) for frame in EVENT]
    if any(rows[index].crop((column * 656, 0, (column + 1) * 656, 368)).tobytes() != sequences[column][frame].tobytes()
           for index, frame in enumerate(EVENT) for column in range(3)):
        raise ValueError("Caption composition changed a source image tile")
    del sequences
    review = root / "review"
    video = {**encode(rows, review / case["video"], FPS), "source_frames_inclusive": [40, 100],
             "normalized_source_seconds": [frame / FPS for frame in EVENT]}
    subprocess.run([executable("ffmpeg"), "-v", "error", "-xerror", "-threads", "2",
                    "-i", str(review / case["video"]), "-map", "0:v:0", "-an", "-f", "null", "-"],
                   check=True, capture_output=True, timeout=180)
    video["full_decode_passed"] = True
    preview = rows[EVENT.index(case["preview_frame"])]
    preview_path = review / case["preview"]
    preview.save(preview_path)
    with Image.open(preview_path) as checked:
        checked.load()
        if checked.size != FULL_ROW or checked.tobytes() != preview.tobytes():
            raise ValueError("Saved preview differs from the selected core-frame composition")
    preview_record = {"file": case["preview"], "source_frame": case["preview_frame"],
                      "normalized_source_seconds": case["preview_frame"] / FPS,
                      "origin": "lossless preencode composition of the same source frame in each column",
                      "sha256": fingerprint(preview_path), "size": list(FULL_ROW)}
    if any(signature(path) != prior or fingerprint(path) != digest for path, prior, digest in zip(paths, signatures, hashes)):
        raise ValueError("A raw input changed during rendering; derivatives are not approved")
    if any(fingerprint(path) != digest for path, digest in zip(histories, history_hashes)):
        raise ValueError("A formal history changed during rendering")
    return {"case_id": case_id, "status": "ready", "comparison_rendered": True,
            "rendered_utc": datetime.now(timezone.utc).isoformat(), "formal_runs": case["formal_jobs"],
            "column_labels": list(LABELS), "videos": {case["video"]: video}, "preview": preview_record,
            "inputs": [{"label": label, "path": str(path), "sha256": digest, "probe": info, "timestamps": timing}
                       for label, path, digest, info, timing in zip(LABELS, paths, hashes, infos, timings)],
            "formal_histories": [{"path": str(path), "sha256": digest} for path, digest in zip(histories, history_hashes)],
            "source_event_full_frames": case["source_event_full_frames"], "source_event_core_frames": case["source_event_core_frames"],
            "latent_interval_half_open": case["expected_latent_interval_half_open"],
            "position_bin_coverage_inclusive": case["expected_position_bin_coverage"],
            "source_window_seconds": case["source_window_seconds"],
            "retained_black_borders_pixels": case["existing_black_borders_pixels"],
            "checks": {"status": "media_checks_passed_spot_preview_pending", "experimental_render_completed": True,
                       "preencode_image_tiles_checked": 183, "preencode_image_tiles_equal_decoded_inputs": True,
                       "raw_input_hashes_unchanged_after_render": True, "formal_histories_unchanged_after_render": True,
                       "encoded_video_full_decode_passed": True, "preview_png_roundtrip_passed": True,
                       "no_crop_retiming_or_border_normalization": True,
                       "visual_review": "pending one actual preview spot check; no comprehensive visual analysis"}}


def overall_status(cases):
    statuses = [case["status"] for case in cases.values()]
    if len(statuses) == len(CASE_SPECS) and all(status == "ready" for status in statuses):
        return "ready"
    if any(status == "ready" for status in statuses):
        return "partial"
    return "error" if any(status == "error" for status in statuses) else "pending"


def write_page(review, cases, control):
    body = '<h1>山姆·奥特曼 · 短动作角色替换对比</h1><p>每组三列依次是参考视频、角色替换、短时动作三倍加权后的角色替换。后两列为人工智能生成画面，并非本人表演录像。</p>'
    for case_id, case in cases.items():
        spec = CASE_SPECS[case_id]
        body += f'<section id="case-{case_id}"><h2>{spec["title"]}</h2>'
        if case["status"] == "ready":
            video = next(iter(case["videos"]))
            body += (f'<video controls preload="metadata" data-source-frames="40-100" data-playback-fps="24" '
                     f'src="{video}"></video><a href="{video}">打开短片</a>')
            body += (f'<details><summary>核心姿态预览</summary><img loading="lazy" '
                     f'data-source-frame="{spec["preview_frame"]}" src="{case["preview"]["file"]}" '
                     'alt="同一核心动作位置的三列角色替换对照"></details>')
        else:
            message = "媒体检查未通过，详情保留在检查记录中。" if case["status"] == "error" else "等待这组正式输出及成功运行记录。当前没有生成或代替比较结果。"
            body += f'<p class="note">{message}</p>'
        body += '</section>'
    body += '<section><details><summary>方法、验证状态与来源</summary>' + validation_panel(control)
    body += f'<p>{CAVEAT}</p>'
    body += '<p>短片以正常速度、静音播放。三列使用相同来源位置，保留完整画面并等比例缩小，不裁剪、不插帧、不分别调整时间或重做边框。原始长视频保持不变。</p>'
    body += '<p>室内片段原有的上下黑边与左右窄边、床边片段原有的左右窄边均保留。每组基础结果先计算共享条件，加权结果应复用该组条件；实际运行是否匹配以独立验证记录为准。</p>'
    body += (f'<p><a href="{REFERENCE}">山姆·奥特曼参考照片</a>：Village Global，'
             '<a href="https://commons.wikimedia.org/wiki/File:Sam_Altman_November_2022.jpg">维基共享资源</a>，'
             '<a href="https://creativecommons.org/licenses/by/2.0/">CC BY 2.0</a>。原照片保持不变，生成画面为基于该参考的改编。</p>'
             '<p>舞蹈来源：<a href="https://www.youtube.com/watch?v=3vd5c8XMP9c">Megumi 原始公开视频</a>、'
             '<a href="https://www.youtube.com/watch?v=oPnUDTAG0_0">Ary Vilchis 原始公开视频</a>。截取范围保留于元数据；已有记录未声明可自由再利用的舞蹈视频许可。</p>'
             '<p><a href="CREDITS.txt">完整署名</a> · <a href="provenance.json">来源与配置</a> · '
             '<a href="manifest.json">媒体清单</a> · <a href="renderer_qa.json">基本检查记录</a></p></details></section>')
    content = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    content += '<meta name="comparison-caption-style" content="zh-CN black bottom row; PingFang SC 22px; no frame, time or English overlays">'
    content += '<meta name="comparison-frame-evidence" content="Zero-based source frames 40-100 at 24 FPS; previews 05:56 and 07:61; per-case excerpt and event times retained in manifest/provenance">'
    content += f'<title>短动作角色替换对比</title><style>{STYLE}</style><body>{body}</body></html>\n'
    temporary = review / "index.html.tmp"
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(review / "index.html")


def render(root):
    root = root.resolve()
    if root.name != "h3-sam-real-dance-batch-20261015":
        raise ValueError("Render only within this task's named directory")
    config = configuration(root)
    control = read_control_validation(root)
    sources = support_files(root, config, control)
    cases = {}
    for case_id, case in config["cases"].items():
        try:
            cases[case_id] = render_case(root, case_id, case, sources[case_id])
        except (OSError, ValueError, KeyError, IndexError, RuntimeError, subprocess.SubprocessError) as error:
            cases[case_id] = pending_case(case_id, case, [f"Case media checks failed: {error}"], status="error")
    status = overall_status(cases)
    review = root / "review"
    result = {"status": status, "checked_utc": datetime.now(timezone.utc).isoformat(), "cases": cases,
              "rendered_case_count": sum(case["status"] == "ready" for case in cases.values()),
              "technical_benchmark": None, "caption_style": caption_metadata(),
              "tile_size": list(FULL_TILE), "comparison_size": list(FULL_ROW),
              "source_frames_inclusive": [40, 100], "frames_per_video": 61, "fps": 24,
              "duration_seconds": 61 / 24, "audio": "Silent comparison derivatives; raw media preserved",
              "synthetic_results_substituted": False, "interpretation_limit": CAVEAT,
              "control_verification": control, "media_readiness_is_control_verification": False}
    write_json(review / "manifest.json", result)
    qa = {"status": status, "experimental_render_completed": status == "ready",
          "rendered_case_count": result["rendered_case_count"], "cases": {case_id: case["checks"] for case_id, case in cases.items()},
          "plan_and_four_graph_checks_passed": True, "source_and_portrait_sha256_verified": True,
          "caption_style": result["caption_style"], "control_report_status": control["reported_status"],
          "media_readiness_is_control_verification": False, "synthetic_results_substituted": False,
          "visual_review_scope": "At most one preview spot check per ready case; no comprehensive visual or efficacy analysis"}
    write_json(review / "renderer_qa.json", qa)
    write_page(review, cases, control)
    qa["local_links_checked"] = verify_links(review)
    qa["all_local_links_exist"] = True
    write_json(root / "analysis/renderer_qa.json", qa)
    write_json(review / "renderer_qa.json", qa)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = render(args.root)
    print(json.dumps({"status": result["status"], "cases": {key: value["status"] for key, value in result["cases"].items()},
                      "review": str(args.root / "review/index.html")}, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "ready" else 2)


if __name__ == "__main__":
    main()
