#!/usr/bin/env python3
"""CPU-only equal-crop details; preserve all full-context review assets.

Uses the four already validated formal inputs in review/manifest.json. Writes
only review/compact/, a marked section in review/index.html, and
analysis/compact_media_qa.json. No interpolation or independent rescaling.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
import render_factor3_comparison as full
from PIL import Image, ImageDraw, ImageFont


CROP = (288, 0, 736, 736)
TILE = (368, 368)
CAPTION_HEIGHT = 44
ROW = (1472, 412)
FRAMES = list(range(30, 78))
SHEET_FRAMES = (41, 42, 43)
START, END = "<!-- COMPACT_DETAILS:START -->", "<!-- COMPACT_DETAILS:END -->"


def decode_window(path):
    raw = subprocess.run(
        [full.executable("ffmpeg"), "-v", "error", "-xerror", "-threads", "2", "-i", str(path),
         "-vf", "select=between(n\\,30\\,77),crop=736:736:288:0,scale=368:368:flags=lanczos",
         "-fps_mode", "passthrough", "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        check=True, capture_output=True, timeout=180).stdout
    frame_bytes = TILE[0] * TILE[1] * 3
    if len(raw) != len(FRAMES) * frame_bytes:
        raise ValueError("Expected exactly frames 30 through 77: " + str(path))
    return [Image.frombytes("RGB", TILE, raw[i * frame_bytes:(i + 1) * frame_bytes])
            for i in range(len(FRAMES))]


def compose(sequences, offset):
    row = Image.new("RGB", ROW, "black")
    draw = ImageDraw.Draw(row)
    label_font = ImageFont.truetype(str(full.FONT), 16)
    time_font = ImageFont.truetype(str(full.FONT), 12)
    frame = FRAMES[offset]
    for column, (label, sequence) in enumerate(zip(full.LABELS, sequences)):
        left = column * TILE[0]
        row.paste(sequence[offset], (left, 0))
        draw.text((left + 8, TILE[1] + 3), label, font=label_font, fill="white")
        draw.text((left + 8, TILE[1] + 24), f"frame {frame:03d} | {frame / full.FPS:.3f}s",
                  font=time_font, fill="white")
    return row


def encode(rows, path, fps):
    temporary = path.with_name(path.stem + ".partial.mp4")
    command = [full.executable("ffmpeg"), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{ROW[0]}x{ROW[1]}", "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264",
               "-threads", "2", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", str(temporary)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for row in rows:
            process.stdin.write(row.tobytes())
        process.stdin.close()
        error = process.stderr.read().decode("utf-8", errors="replace")
        if process.wait(timeout=180):
            raise RuntimeError("ffmpeg failed: " + error[-1000:])
        info = full.probe(temporary)
        full.check_geometry(info, frames=len(FRAMES), fps=fps, size=ROW)
        temporary.replace(path)
        return {"file": path.name, "probe": info, "sha256": full.fingerprint(path)}
    except BaseException:
        if process.poll() is None:
            process.kill()
            process.wait()
        temporary.unlink(missing_ok=True)
        raise


def update_index(path):
    section = START + '''
<section id="compact-details" style="max-width:1472px">
<h2>Compact event detail</h2>
<p>Same crop in all four originals: x288, y0, 736 &times; 736 pixels, displayed at 368 &times; 368. Source core frames are 41-42; the third row adds frame 43 context.</p>
<a href="compact/compact_frames_041-043.png"><img src="compact/compact_frames_041-043.png" alt="Frames 41, 42 and 43: SOURCE, BASELINE, WEIGHT x2, WEIGHT x3; bottom captions"></a>
<p>Frames 30-77 &middot; quarter speed, 6 FPS &middot; 8 seconds. Same original frames, no interpolation.</p>
<video controls preload="metadata" src="compact/compact_frames_030-077_quarter_speed.mp4"></video>
<p><a href="compact/compact_frames_030-077_quarter_speed.mp4">Open quarter-speed detail</a></p>
<p>Frames 30-77 &middot; normal speed, 24 FPS &middot; 2 seconds.</p>
<video controls preload="metadata" src="compact/compact_frames_030-077.mp4"></video>
<p><a href="compact/compact_frames_030-077.mp4">Open normal-speed detail</a> &middot; <a href="../analysis/compact_media_qa.json">Compact media checks</a></p>
<p>Full-frame clips and complete contact sheets continue below.</p>
</section>
''' + END
    content = path.read_text()
    if START in content:
        before, remainder = content.split(START, 1)
        _, after = remainder.split(END, 1)
        updated = before + section + after
    else:
        marker = content.find("<section>")
        if marker < 0:
            raise ValueError("Existing full-context review section not found")
        updated = content[:marker] + section + content[marker:]
    temporary = path.with_suffix(".html.tmp")
    temporary.write_text(updated)
    temporary.replace(path)


def render(root):
    root = root.resolve()
    full.validate_destination(root, full.ARCHIVE)
    review = root / "review"
    manifest_path = review / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("status") != "ready" or manifest.get("column_labels") != list(full.LABELS):
        raise ValueError("The complete four-column formal comparison must be ready first")
    paths = [Path(record["path"]) for record in manifest["inputs"]]
    if len(paths) != 4:
        raise ValueError("Exactly four validated formal inputs are required")
    preserved = {str(path.relative_to(review)): full.fingerprint(path)
                 for path in review.rglob("*")
                 if path.is_file() and path.name != "index.html" and "compact" not in path.relative_to(review).parts}
    input_checks = []
    for path, record in zip(paths, manifest["inputs"]):
        info = full.probe(path)
        full.check_geometry(info)
        timing = full.check_timestamps(path)
        digest = full.fingerprint(path)
        if digest != record["sha256"]:
            raise ValueError("Input differs from the validated full-context manifest: " + str(path))
        input_checks.append({"path": str(path), "sha256": digest, "probe": info, "timestamps": timing})
    signatures = [full.signature(path) for path in paths]
    sequences = [decode_window(path) for path in paths]
    rows = [compose(sequences, offset) for offset in range(len(FRAMES))]
    output = review / "compact"
    output.mkdir(exist_ok=True)
    sheet = Image.new("RGB", (ROW[0], ROW[1] * len(SHEET_FRAMES)), "black")
    for row_number, frame in enumerate(SHEET_FRAMES):
        sheet.paste(rows[FRAMES.index(frame)], (0, ROW[1] * row_number))
    sheet_path = output / "compact_frames_041-043.png"
    sheet.save(sheet_path)
    with Image.open(sheet_path) as checked:
        checked.load()
        if checked.size != (1472, 1236):
            raise ValueError("Compact sheet geometry mismatch")
        for row_number, frame in enumerate(SHEET_FRAMES):
            for column in range(4):
                box = (column * 368, row_number * 412, (column + 1) * 368, row_number * 412 + 368)
                if checked.crop(box).tobytes() != sequences[column][FRAMES.index(frame)].tobytes():
                    raise ValueError("Compact sheet image does not match the decoded same-frame crop")
    videos = [encode(rows, output / "compact_frames_030-077.mp4", 24),
              encode(rows, output / "compact_frames_030-077_quarter_speed.mp4", 6)]
    if any(full.signature(path) != signature for path, signature in zip(paths, signatures)):
        raise ValueError("An original changed during rendering")
    if any(full.fingerprint(review / path) != digest for path, digest in preserved.items()):
        raise ValueError("A preserved full-context asset changed during rendering")
    update_index(review / "index.html")
    report = {"status": "media_checks_passed_visual_review_pending",
              "created_utc": datetime.now(timezone.utc).isoformat(), "inputs": input_checks,
              "crop_original_xywh": list(CROP), "display_tile_size": list(TILE),
              "row_size": list(ROW), "caption_position": "below image only", "caption_height": CAPTION_HEIGHT,
              "labels": list(full.LABELS), "frame_numbering": "zero-based; original timestamp = frame / 24",
              "sheet": {"file": str(sheet_path.relative_to(review)), "frames": list(SHEET_FRAMES),
                        "source_core_frames": [41, 42], "size": [1472, 1236], "sha256": full.fingerprint(sheet_path),
                        "all_12_tiles_match_decoded_same_frame_crops": True},
              "videos": videos, "video_source_frames": FRAMES,
              "temporal_alignment": "Same source frame index in every column; no interpolation, repeats or independent retiming",
              "scaling": "Same native crop and exactly 0.5x Lanczos scaling in all four columns",
              "audio": "Silent comparison derivatives; all raw media unchanged",
              "full_context_assets_preserved": True, "preserved_asset_count": len(preserved),
              "preserved_asset_sha256": preserved, "visual_verdict": None}
    full.write_json(root / "analysis/compact_media_qa.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = render(args.root)
    print(json.dumps({"status": result["status"], "sheet": result["sheet"]["file"],
                      "videos": [{"file": record["file"], "probe": record["probe"]} for record in result["videos"]]}))


if __name__ == "__main__":
    main()
