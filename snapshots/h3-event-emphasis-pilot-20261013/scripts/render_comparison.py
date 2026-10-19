#!/usr/bin/env python3
"""CPU-only black/English triplets. Writes only review/, never source files.

Requires successful formal histories. Missing inputs give a truthful pending page.
"""
import argparse
from fractions import Fraction
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
from PIL import Image, ImageDraw, ImageFont

RUNS = ("06_seed2_baseline", "06_seed2_emphasis2")
LABELS = ("PREVIOUS", "PRESENT", "PRESENT + EVENT WEIGHT x2")
TILE, ROW = (656, 368), (1968, 416)
FONT = Path("/System/Library/Fonts/Helvetica.ttc")
STYLE = """body{font:16px system-ui,sans-serif;background:#080808;color:#eee;margin:0 auto;padding:24px;max-width:1600px}h1{font-size:26px}h2{font-size:21px}p{line-height:1.55;color:#ccc}a{color:#9bd4ff}section{border-top:1px solid #444;margin:24px 0;padding-top:16px}video,img{display:block;width:100%;height:auto;background:#000;margin:14px 0}summary{cursor:pointer}code{color:#ffda87}.note{color:#ffda87}a{overflow-wrap:anywhere}"""


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path):
    executable = shutil.which("ffprobe")
    if not executable:
        raise RuntimeError("ffprobe unavailable; inspect PATH/install before retry")
    result = subprocess.run([executable, "-v", "error", "-count_frames", "-select_streams", "v:0",
                             "-show_entries", "stream=width,height,avg_frame_rate,nb_read_frames,duration",
                             "-of", "json", str(path)], check=True, capture_output=True, text=True, timeout=180)
    stream = json.loads(result.stdout)["streams"][0]
    return {"width": stream["width"], "height": stream["height"], "frames": int(stream["nb_read_frames"]),
            "fps": str(Fraction(stream["avg_frame_rate"])), "duration": float(stream["duration"])}


def decode(path):
    executable = shutil.which("ffmpeg")
    if not executable:
        raise RuntimeError("ffmpeg unavailable; inspect PATH/install before retry")
    raw = subprocess.run([executable, "-v", "error", "-i", str(path), "-vf", "scale=656:368:flags=lanczos",
                          "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         check=True, capture_output=True, timeout=180).stdout
    size = TILE[0] * TILE[1] * 3
    if len(raw) != 141 * size:
        raise ValueError("expected exactly 141 decoded frames: " + str(path))
    return [Image.frombytes("RGB", TILE, raw[i * size:(i + 1) * size]) for i in range(141)]


def compose(sequences, frame):
    row = Image.new("RGB", ROW, "black")
    draw = ImageDraw.Draw(row)
    title_font = ImageFont.truetype(str(FONT), 20)
    detail_font = ImageFont.truetype(str(FONT), 14)
    for col, (label, sequence) in enumerate(zip(LABELS, sequences)):
        x = col * TILE[0]
        row.paste(sequence[frame], (x, 48))
        draw.text((x + 10, 3), label, font=title_font, fill="white")
        draw.text((x + 10, 28), f"frame {frame:03d} | {frame / 24:.3f}s", font=detail_font, fill="white")
    return row


def encode(rows, path, fps):
    executable = shutil.which("ffmpeg")
    temp = path.with_name(path.stem + ".partial.mp4")
    command = [executable, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{ROW[0]}x{ROW[1]}", "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264",
               "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(temp)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for row in rows:
            process.stdin.write(row.tobytes())
        process.stdin.close()
        error = process.stderr.read().decode("utf-8", errors="replace")
        if process.wait(timeout=180):
            raise RuntimeError("ffmpeg failed: " + error[-1000:])
        temp.replace(path)
    except BaseException:
        if process.poll() is None:
            process.kill()
            process.wait()
        temp.unlink(missing_ok=True)
        raise
    actual = probe(path)
    if actual["frames"] != len(rows) or actual["fps"] != str(fps) or (actual["width"], actual["height"]) != ROW:
        raise ValueError("derivative video geometry or frame count mismatch")
    return actual


def sheets(rows, indices, folder, prefix, rows_per_page=3):
    folder.mkdir(parents=True, exist_ok=True)
    result = []
    for start in range(0, len(indices), rows_per_page):
        part = indices[start:start + rows_per_page]
        sheet = Image.new("RGB", (ROW[0], ROW[1] * len(part)), "black")
        for offset, index in enumerate(part):
            sheet.paste(rows[index], (0, offset * ROW[1]))
        path = folder / f"{prefix}_{part[0]:03d}-{part[-1]:03d}.jpg"
        sheet.save(path, quality=95, subsampling=0)
        with Image.open(path) as check:
            check.load()
            if check.size != sheet.size:
                raise ValueError("sheet dimension mismatch")
        result.append({"file": str(path), "frames": part, "sha256": fingerprint(path)})
    return result


def page(body):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + f'<title>H3 short-event emphasis comparison</title><style>{STYLE}</style><body>' + body + '</body></html>\n'


def pending(root, missing):
    out = root / "review"
    out.mkdir(exist_ok=True)
    result = {"status": "pending", "missing": missing, "formal_run_ids": list(RUNS), "synthetic_results": False}
    write_json(out / "manifest.json", result)
    (out / "index.html").write_text(page('<h1>H3 short-event emphasis comparison</h1><p class="note">Pending formal outputs. No comparison has been rendered.</p><ul>' + ''.join('<li>' + html.escape(x) + '</li>' for x in missing) + '</ul>'))
    return result


def render(root):
    root = Path(root)
    paths = [root / "inputs/06_anime_eye_insert.mp4"] + [root / "outputs" / (name + "_00001_.mp4") for name in RUNS]
    missing = [str(path.relative_to(root)) for path in paths if not path.is_file()]
    for name in RUNS:
        path = root / "logs" / (name + "_history.json")
        if not path.is_file():
            missing.append(str(path.relative_to(root)))
            continue
        history = json.loads(path.read_text())
        if "status" not in history and len(history) == 1:
            history = next(iter(history.values()))
        status = history.get("status", {})
        if status.get("status_str") != "success" or status.get("completed") is not True:
            missing.append(name + ": successful formal history")
    if missing:
        return pending(root, missing)
    if not FONT.is_file():
        raise RuntimeError("Required font unavailable: " + str(FONT))
    infos = [probe(path) for path in paths]
    if any((x["width"], x["height"], x["frames"], x["fps"]) != (1312, 736, 141, "24") for x in infos):
        raise ValueError("refuse to resynchronize/trim mismatched source/baseline/intervention videos")
    sequences = [decode(path) for path in paths]
    rows = [compose(sequences, frame) for frame in range(141)]
    out = root / "review"
    out.mkdir(exist_ok=True)
    videos = {}
    for name, selected, fps in (("comparison_full.mp4", rows, 24), ("comparison_full_quarter_speed.mp4", rows, 6),
                                ("comparison_frames_030-077.mp4", rows[30:78], 24),
                                ("comparison_frames_030-077_quarter_speed.mp4", rows[30:78], 6)):
        path = out / name
        videos[name] = {"probe": encode(selected, path, fps), "sha256": fingerprint(path)}
    groups = {
        "key_event": sheets(rows, list(range(39, 45)), out / "key_event", "event"),
        "dense_030_077": sheets(rows, list(range(30, 78)), out / "dense_030_077", "dense"),
        "all_frames": sheets(rows, list(range(141)), out / "all_frames", "frames")}
    for records in groups.values():
        for record in records:
            record["file"] = str(Path(record["file"]).relative_to(out))
    result = {"status": "ready", "formal_run_ids": list(RUNS), "benchmark_excluded": True,
              "inputs": [{"path": str(path), "sha256": fingerprint(path), "probe": info} for path, info in zip(paths, infos)],
              "videos": videos, "sheets": groups, "triplet_labels": list(LABELS),
              "tile_width_height": list(TILE), "comparison_width_height": list(ROW),
              "source_event_frames_inclusive": [39, 44], "source_core_frames_inclusive": [41, 42],
              "later_separate_event_frames_inclusive": [54, 68],
              "slow_motion_method": "same decoded frames encoded at 6 FPS (quarter speed), no interpolation or frame repetition",
              "temporal_alignment": "same frame index for all three columns; no column-specific retiming",
              "spatial_alignment": "each full 1312x736 frame scaled equally to 656x368; no cropping or independent enlargement",
              "notes": ["Reference event labels describe SOURCE timing only; they do not assert generated event occurrence.",
                        "Factor x2 is attention-odds weighting for selected temporal reference tokens, not proof of action-feature isolation.",
                        "Successful rendering does not imply repaired motion; review timing, relation, count, order, identity and global quality."]}
    write_json(out / "manifest.json", result)
    body = '<h1>H3 short-event emphasis comparison</h1><p>PREVIOUS / PRESENT / PRESENT + EVENT WEIGHT x2 &middot; fixed seed 2026101312 &middot; same prompt and AV noise &middot; 20 steps</p>'
    body += '<p>PREVIOUS = source video. PRESENT = fresh baseline with no attention intervention. PRESENT + EVENT WEIGHT x2 = manual temporal-reference attention weighting. This pair uses the same ordinary prompt in both generated conditions.</p>'
    body += '<p class="note">Inspect the early short hand-eye relation at source frames 39-44 (core 41-42). The later V / leg lift at 54-68 is a separate event and cannot substitute for it.</p>'
    body += '<p>All columns use equal full-frame scaling and the same frame index. No crop, independent zoom, time warping or interpolated frames. Labels identify the source event; they do not announce success.</p>'
    for title, normal, slow in (("Complete clip: all 141 frames", "comparison_full.mp4", "comparison_full_quarter_speed.mp4"),
                                ("Dense event context: frames 30-77", "comparison_frames_030-077.mp4", "comparison_frames_030-077_quarter_speed.mp4")):
        body += f'<section><h2>{title}</h2><p>Original speed (24 FPS)</p><video controls preload="metadata" src="{normal}"></video><p>Quarter speed (6 FPS, same frames)</p><video controls preload="metadata" src="{slow}"></video></section>'
    for title, key in (("Source short-event window: every frame 39-44", "key_event"), ("Dense comparison: every frame 30-77", "dense_030_077"), ("Complete coverage: every frame 0-140", "all_frames")):
        body += '<section><h2>' + title + '</h2>'
        if key != "key_event":
            body += '<details><summary>Show all frame sheets</summary>'
        for record in groups[key]:
            body += f'<a href="{record["file"]}"><img loading="lazy" src="{record["file"]}" alt="Same-index triplet frames {record["frames"][0]}-{record["frames"][-1]}"></a>'
        if key != "key_event":
            body += '</details>'
        body += '</section>'
    body += '<p><a href="manifest.json">Media manifest and provenance</a> &middot; Technical benchmark output excluded.</p>'
    (out / "index.html").write_text(page(body))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = render(args.root)
    print(json.dumps({"status": result["status"], "missing": result.get("missing", []), "review": str(args.root / "review/index.html")}))
    raise SystemExit(2 if result["status"] == "pending" else 0)


if __name__ == "__main__":
    main()
