#!/usr/bin/env python3
"""CPU-only short-action SOURCE / MUSK BASELINE / MUSK x3 review.

Writes only review/ and analysis/renderer_qa.json. Requires both completed
formal histories and three complete 141-frame, 24-FPS inputs. Missing
results produce a truthful pending page (exit 2); no substitute output is used.
Produces one 61-frame normal-speed triptych and one core-frame PNG preview.
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


LABELS = ("SOURCE", "MUSK BASELINE", "MUSK x3")
CAPTION_LABELS = ("1.参考视频", "2.编辑后视频", "3.编辑＋短时动作三倍加权后视频")
CAPTION_LEGEND = "角色替换"
RUNS = ("07_musk_s1_baseline", "07_musk_s1_weight3")
SOURCE = "07_real_ary_v.mp4"
REFERENCE = "elon_musk_royal_society.jpg"
ORIGINAL, FULL_TILE, FULL_ROW = (1312, 736), (656, 368), (1968, 416)
COUNT, FPS = 141, 24
EVENT = list(range(40, 101))
PREVIEW_FRAME = 61
SHORT_VIDEO = "comparison_short.mp4"
PREVIEW_IMAGE = f"comparison_preview_frame_{PREVIEW_FRAME:03d}.png"
CAPTION_FONT_SIZE = 22
SOURCE_EVENT, SOURCE_CORE = [54, 69], [60, 62]
LATENT_INTERVAL, BIN_COVERAGE = [16, 22], [52, 72]
SOURCE_WINDOW = [34.5, 40.375]
SOURCE_URL = "https://www.youtube.com/watch?v=oPnUDTAG0_0"
CAVEAT = "本页仅包含一个来源片段、一个随机种子的配对结果。手工选择的短动作加权范围包含相邻动作与全部空间内容；这一对结果不能证明普遍有效，也不能保证修正整段动作的时间偏移。视频生成完成与实验控制验证通过是两个独立状态。"
STYLE = """body{font:16px system-ui,sans-serif;background:#080808;color:#fff;margin:0 auto;padding:24px;max-width:1968px}h1{font-size:26px}h2{font-size:21px}p{line-height:1.55;color:#ddd}a{color:#fff;overflow-wrap:anywhere}section{border-top:1px solid #555;margin:24px 0;padding-top:16px}video,img{display:block;width:100%;height:auto;background:#000;margin:14px 0}summary{cursor:pointer}.note{border-left:3px solid #fff;padding-left:14px}li{line-height:1.6}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:32em;overflow:auto;border:1px solid #555;padding:12px;font-size:13px}"""

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def write_page(path, body):
    content = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    content += '<meta name="comparison-caption-style" content="zh-CN black bottom row; PingFang SC 22px; no visible frame or time labels">'
    content += '<meta name="comparison-frame-evidence" content="Zero-based indices; source seconds = frame / 24; source excerpt 34.5-40.375; event 54-69; core 60-62; latent 16:22; coverage 52-72">'
    content += f'<title>床边舞蹈 · 角色替换对比</title><style>{STYLE}</style><body>{body}</body></html>\n'
    temporary = path.with_suffix(".html.tmp")
    temporary.write_text(content, encoding="utf-8")
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
    if plan["formal_jobs"] != list(RUNS) or plan["source"] != SOURCE:
        raise ValueError("Plan does not match the named formal pair and source")
    if plan["sampling"]["output"] != [1312, 736, 141, 24]:
        raise ValueError("Plan geometry differs from the full-frame renderer")
    expected = {"technical_benchmark": None, "source_event_full_frames": SOURCE_EVENT,
                "source_event_core_frames": SOURCE_CORE, "expected_latent_interval_half_open": LATENT_INTERVAL,
                "expected_position_bin_coverage": BIN_COVERAGE}
    for key, value in expected.items():
        if key not in plan or plan[key] != value:
            raise ValueError("Unexpected plan setting: " + key)
    graphs = [json.loads((root / f"configs/{run}.json").read_text()) for run in RUNS]
    for graph, run, factor in zip(graphs, RUNS, (1, 3)):
        if graph["50"]["inputs"]["factor"] != factor or graph["14"]["inputs"]["filename_prefix"] != run:
            raise ValueError("Graph factor or output name does not match the formal comparison")
        if graph["22"]["inputs"]["file"] != SOURCE or graph["21"]["inputs"]["image"] != REFERENCE:
            raise ValueError("Graph source or reference differs from the review provenance")
        if [graph["50"]["inputs"]["start_frame"], graph["50"]["inputs"]["end_frame"]] != SOURCE_EVENT:
            raise ValueError("Graph intervention differs from the source event")
        if graph["6"]["inputs"]["noise_seed"] != plan["seed"]:
            raise ValueError("Graph seed differs from the plan")
    if graphs[0]["5"] != graphs[1]["5"] or graphs[0]["5"]["inputs"]["run_id"] != "07_musk_shared_conditioning":
        raise ValueError("Formal graphs must share conditioning node 5 exactly")
    return {"plan": plan, "plan_sha256": fingerprint(plan_path),
            "graphs": [{"run": run, "sha256": fingerprint(root / f"configs/{run}.json"),
                        "factor": graph["50"]["inputs"]["factor"], "seed": graph["6"]["inputs"]["noise_seed"],
                        "prompt_sha256": hashlib.sha256(graph["5"]["inputs"]["prompt"].encode()).hexdigest()}
                       for graph, run in zip(graphs, RUNS)],
            "scope": "Graph metadata documents intended controls; actual parity is determined by the verifier."}


def support_files(root, config):
    """Bundle provenance only after checking the supplied metadata and SHA256s."""
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
    source_path = root / "inputs/source_metadata.json"
    source = json.loads(source_path.read_text())
    expected = {"clip_id": SOURCE.removesuffix(".mp4"), "source_url": SOURCE_URL,
                "source_window_seconds": SOURCE_WINDOW, "output_frames": COUNT, "output_fps": FPS,
                "width": ORIGINAL[0], "height": ORIGINAL[1]}
    if any(source.get(key) != value for key, value in expected.items()):
        raise ValueError("Source metadata identity, excerpt or geometry mismatch")
    if source["event"]["transition_frames_inclusive"] != SOURCE_EVENT or source["event"]["decisive_frames_inclusive"] != SOURCE_CORE:
        raise ValueError("Source metadata event differs from this experiment")
    source_sha = fingerprint(root / "inputs" / SOURCE)
    if source_sha != source["output_sha256"]:
        raise ValueError("Source clip differs from its recorded provenance")
    shutil.copy2(reference, review / REFERENCE)
    shutil.copy2(root / "inputs/CREDITS.txt", review / "CREDITS.txt")
    write_json(review / "provenance.json", {"reference": provenance, "source_metadata": source,
               "source_metadata_sha256": fingerprint(source_path), "source_clip_sha256_verified": source_sha,
               "configuration": config,
               "source_metadata_note": "Historical recolor-task prompts describe source selection; the current formal graphs request a synthetic Musk identity edit.",
               "source_normalization": {"native_size": [1280, 720], "normalized_content_size": [1308, 736],
                                        "existing_padding_pixels": {"left": 2, "right": 2, "top": 0, "bottom": 0},
                                        "renderer_changes": "None; complete normalized frames are scaled equally without cropping, padding changes or independent retiming."},
               "conditioning_execution_policy": "No benchmark. Baseline computes shared node 5; weighted run must cache it. Actual history verification is separate.",
               "synthetic_media_disclosure": "Musk columns are AI-generated identity edits of the source performer, not recordings of Elon Musk performing this dance."})
    control = read_control_validation(root)
    write_json(review / "control_validation.json", control["report"] if control["available"] else control)
    return control


def introduction(config):
    return ('<h1>床边舞蹈 · 角色替换对比</h1>'
            '<p>从参考动作到角色替换，再到短时动作三倍加权。后两列为人工智能生成的马斯克角色替换画面，并非本人表演录像。</p>')


def credits():
    return ('<section><h2>来源与署名</h2>'
            f'<p><a href="{REFERENCE}">马斯克参考照片</a>：Debbie Rowe / The Royal Society，'
            '<a href="https://commons.wikimedia.org/wiki/File:Elon_Musk_Royal_Society.jpg">维基共享资源</a>，'
            '<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC BY-SA 3.0</a>。归档照片保持原样，模型预处理单独记录。</p>'
            '<p>舞蹈来源：<a href="https://www.youtube.com/watch?v=oPnUDTAG0_0">Ary Vilchis 的原始公开视频</a>。'
            '本次使用已有实验片段，截取位置保留于来源元数据；提供的记录中没有声明可自由再利用的视频许可。</p>'
            '<p><a href="CREDITS.txt">完整署名</a> · <a href="provenance.json">来源、截取范围与配置</a> · '
            '<a href="manifest.json">媒体清单</a> · <a href="renderer_qa.json">渲染检查</a></p></section>')


def review_details(control):
    body = '<section><details><summary>方法、验证状态与来源</summary>'
    body += validation_panel(control) + f'<p>{CAVEAT}</p>'
    body += '<p>三列保留完整画面并按相同比例缩小，使用同一来源帧，不裁剪、不插帧、不分别调整时间。源片已有的左右窄边保留，不按生成结果重新处理边框。短片以正常速度播放，比较视频为静音。</p>'
    body += '<p>加权覆盖的时间位置比手工标注动作略宽，并作用于这些位置的全部空间内容。这里提供短动作对比与一张核心姿态预览，不作全面质量评估或普遍效果结论。</p>'
    body += '<p>这一对没有技术预跑：基础组先计算共享条件，加权组应复用缓存；是否实际复用以运行历史为准。本例与先前舞蹈例的主机不同，跨案例差异不能单独归因为内容。</p>'
    return body + credits() + '</details></section>'


def save_qa(root, qa):
    write_json(root / "analysis/renderer_qa.json", qa)
    write_json(root / "review/renderer_qa.json", qa)


def pending(root, problems, config):
    control = support_files(root, config)
    review = root / "review"
    result = {"status": "pending", "checked_utc": datetime.now(timezone.utc).isoformat(), "problems": problems,
              "column_labels": list(LABELS), "formal_runs": list(RUNS), "technical_benchmark": None,
              "synthetic_results_substituted": False, "comparison_rendered": False,
              "caption_style": caption_metadata(), "source_event_full_frames": SOURCE_EVENT,
              "source_event_core_frames": SOURCE_CORE, "expected_latent_interval_half_open": LATENT_INTERVAL,
              "expected_position_bin_coverage": BIN_COVERAGE, "context_frames": [EVENT[0], EVENT[-1]],
              "planned_media": {"video": SHORT_VIDEO, "frames": len(EVENT), "fps": FPS,
                                "duration_seconds": len(EVENT) / FPS,
                                "preview": PREVIEW_IMAGE, "preview_source_frame": PREVIEW_FRAME},
              "interpretation_limit": CAVEAT, "control_verification": control,
              "media_readiness_is_control_verification": False}
    write_json(review / "manifest.json", result)
    qa = {"status": "pending_formal_outputs", "experimental_render_completed": False,
          "synthetic_results_substituted": False, "problems": problems,
          "plan_and_graph_checks_passed": True, "source_and_portrait_sha256_verified": True,
          "caption_style": result["caption_style"], "planned_media": result["planned_media"],
          "control_report_status": control["reported_status"], "media_readiness_is_control_verification": False,
          "visual_review_scope": "One short normal-speed video and one core-frame preview; no comprehensive visual analysis.",
          "visual_review": "not performed; actual comparison media are pending"}
    save_qa(root, qa)
    body = introduction(config)
    body += '<section><h2>等待正式结果</h2><p class="note">两段正式输出及其成功运行记录齐备后，这里会显示一个正常速度的短动作三联视频和一张核心姿态预览。当前尚未生成比较结果。</p></section>'
    write_page(review / "index.html", body + review_details(control))
    qa["self_contained_local_links_checked"] = verify_links(review)
    qa["all_local_links_exist"] = True
    save_qa(root, qa)
    return result


def ready_page(review, control, config):
    body = introduction(config)
    body += (f'<section><h2>短动作对比</h2><video controls preload="metadata" '
             f'data-source-frames="{EVENT[0]}-{EVENT[-1]}" data-playback-fps="{FPS}" '
             f'src="{SHORT_VIDEO}"></video><a href="{SHORT_VIDEO}">打开视频</a></section>')
    body += (f'<section><details><summary>核心姿态预览</summary><img loading="lazy" '
             f'data-source-frame="{PREVIEW_FRAME}" src="{PREVIEW_IMAGE}" '
             'alt="同一核心动作位置的三列角色替换对照"></details></section>')
    write_page(review / "index.html", body + review_details(control))


def render(root):
    root = root.resolve()
    if root.name != "h3-musk-bedside-pair-20261014":
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
    rows = [compose(sequences, frame) for frame in EVENT]
    if any(rows[index].crop((column * 656, 0, (column + 1) * 656, 368)).tobytes() != sequences[column][frame].tobytes()
           for index, frame in enumerate(EVENT) for column in range(3)):
        raise ValueError("Caption composition changed an image tile")
    del sequences
    review = root / "review"
    video = {**encode(rows, review / SHORT_VIDEO, FPS),
             "source_frames_inclusive": [EVENT[0], EVENT[-1]],
             "normalized_source_seconds": [frame / FPS for frame in EVENT]}
    subprocess.run([executable("ffmpeg"), "-v", "error", "-xerror", "-threads", "2",
                    "-i", str(review / SHORT_VIDEO), "-map", "0:v:0", "-an", "-f", "null", "-"],
                   check=True, capture_output=True, timeout=180)
    video["full_decode_passed"] = True
    preview = rows[EVENT.index(PREVIEW_FRAME)]
    preview_path = review / PREVIEW_IMAGE
    preview.save(preview_path)
    with Image.open(preview_path) as checked:
        checked.load()
        if checked.size != FULL_ROW or checked.tobytes() != preview.tobytes():
            raise ValueError("Saved preview differs from the core-frame composition")
    preview_record = {"file": PREVIEW_IMAGE, "source_frame": PREVIEW_FRAME,
                      "normalized_source_seconds": PREVIEW_FRAME / FPS,
                      "origin": "lossless preencode composition of the same source frame in each column",
                      "sha256": fingerprint(preview_path), "size": list(FULL_ROW)}
    if any(signature(path) != prior or fingerprint(path) != digest
           for path, prior, digest in zip(paths, signatures, hashes)):
        return pending(root, ["An input changed during rendering; derivatives are not approved for review"], config)
    control = support_files(root, config)
    result = {"status": "ready", "rendered_utc": datetime.now(timezone.utc).isoformat(), "column_labels": list(LABELS),
              "formal_runs": list(RUNS), "technical_benchmark": None,
              "inputs": [{"label": label, "path": str(path), "sha256": digest, "probe": info, "timestamps": timing}
                         for label, path, digest, info, timing in zip(LABELS, paths, hashes, infos, timings)],
              "formal_histories": [{"path": str(path), "sha256": fingerprint(path)} for path in histories],
              "videos": {SHORT_VIDEO: video}, "preview": preview_record,
              "tile_size": list(FULL_TILE), "comparison_size": list(FULL_ROW), "caption_style": caption_metadata(),
              "caption_position": "below all complete frames", "source_event_full_frames": SOURCE_EVENT,
              "source_event_core_frames": SOURCE_CORE, "latent_interval_half_open": LATENT_INTERVAL,
              "position_bin_coverage_inclusive": BIN_COVERAGE, "context_frames": [EVENT[0], EVENT[-1]],
              "source_existing_padding_pixels": {"left": 2, "right": 2, "top": 0, "bottom": 0},
              "source_native_size": [1280, 720], "source_normalized_content_size": [1308, 736],
              "source_window_seconds": SOURCE_WINDOW,
              "spatial_alignment": "Complete 1312x736 frames scaled equally to 656x368; no cropping, overlays or independent enlargement",
              "temporal_alignment": "Same source frame index in every column, encoded at the original 24 FPS; no retiming, interpolation or repeated frames",
              "audio": "Silent short comparison; raw media preserved",
              "synthetic_media_disclosure": "Musk columns are generated identity edits, not authentic performance recordings",
              "interpretation_limit": CAVEAT, "control_verification": control, "media_readiness_is_control_verification": False,
              "self_contained_review": True, "reference_and_credits": "provenance.json"}
    write_json(review / "manifest.json", result)
    qa = {"status": "media_checks_passed_spot_preview_pending", "experimental_render_completed": True,
          "videos": {SHORT_VIDEO: video}, "preview": preview_record,
          "comparison_count": 1, "preview_count": 1, "composed_frames": len(EVENT),
          "preencode_image_tiles_checked": 3 * len(EVENT), "preencode_image_tiles_equal_decoded_inputs": True,
          "raw_input_hashes_unchanged_after_render": True, "raw_inputs_unchanged_during_render": True,
          "no_crop_or_blackbar_overlay": True, "caption_style": caption_metadata(),
          "source_and_portrait_sha256_verified": True, "media_readiness_is_control_verification": False,
          "control_report_status": control["reported_status"],
          "visual_review_scope": "One short normal-speed video and one core-frame preview; no comprehensive visual analysis.",
          "visual_review": "pending one actual core-frame preview spot check"}
    save_qa(root, qa)
    ready_page(review, control, config)
    qa["self_contained_local_links_checked"] = verify_links(review)
    qa["all_local_links_exist"] = True
    save_qa(root, qa)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = render(args.root)
    print(json.dumps({"status": result["status"], "problems": result.get("problems", []),
                      "review": str(args.root / "review/index.html")}, ensure_ascii=False))
    raise SystemExit(2 if result["status"] == "pending" else 0)


if __name__ == "__main__":
    main()
