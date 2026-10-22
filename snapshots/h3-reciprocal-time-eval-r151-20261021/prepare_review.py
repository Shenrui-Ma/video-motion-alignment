"""Create complete, frame-indexed contact sheets for one verified new result."""
import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from prepare import ROOT, bind, read

FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
FFMPEG = "/opt/homebrew/bin/ffmpeg"


def make(case_id, role):
    case = next(c for c in read(ROOT / "EVALUATION_MANIFEST.json")["cases"]
                if c["source_id"] == case_id)
    result = read(ROOT / "results" / case_id / f"{role}.json")
    if not result["execution_verified"]:
        raise ValueError("Import verified execution first.")
    records = [(r, case["controls"][r]) for r in ("source", "native", "forward")]
    records.append((role, result["video"]))
    labels = {"source": "参考视频", "native": "普通编辑", "forward": "正向引导",
              "reverse": "反向引导", "combined": "双向引导"}
    g = case["geometry"]
    x, y, w, h = g["crop_xywh"]
    width, height = 384, 216
    frame_bytes = width * height * 3
    streams = {}
    for key, rec in records:
        if bind(Path(rec["file"]))["sha256"] != rec["sha256"]:
            raise ValueError(f"Video changed: {key}")
        filters = (f"crop={w}:{h}:{x}:{y},scale={width}:{height}:"
                   "force_original_aspect_ratio=decrease:force_divisible_by=2,"
                   f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black")
        data = subprocess.check_output([
            FFMPEG, "-v", "error", "-nostdin", "-threads", "1",
            "-i", rec["file"], "-vf", filters, "-frames:v", str(g["valid_frames"]),
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"
        ], timeout=90)
        if len(data) != frame_bytes * g["valid_frames"]:
            raise ValueError("Decoded frame count differs from frozen valid range.")
        streams[key] = data
    folder = ROOT / "reviews" / case_id / role / "contacts"
    folder.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(FONT, 17)
    pages = []
    rows_per_page, header, row_label = 8, 34, 28
    for start in range(0, g["valid_frames"], rows_per_page):
        end = min(start + rows_per_page, g["valid_frames"])
        page = Image.new("RGB", (4 * width, header + (end-start) * (height+row_label)), "black")
        draw = ImageDraw.Draw(page)
        for i, (key, _) in enumerate(records):
            draw.text((i*width+10, 6), labels[key], font=font, fill="white")
        for row, frame in enumerate(range(start, end)):
            top = header + row * (height + row_label)
            for col, (key, _) in enumerate(records):
                raw = streams[key][frame*frame_bytes:(frame+1)*frame_bytes]
                page.paste(Image.frombytes("RGB", (width, height), raw), (col*width, top))
            draw.text((10, top+height+3),
                      f"frame {frame:03d} | {frame/g['fps']:.3f}s", font=font, fill="white")
        path = folder / f"frames_{start:03d}_{end-1:03d}.jpg"
        page.save(path, quality=92)
        pages.append({**bind(path), "frames_inclusive": [start, end-1]})
    destination = folder.parent / "CONTACTS.json"
    full_frames = []
    tile_w, tile_h, tile_caption = 288, 162, 24
    for start in range(0, g["valid_frames"], 49):
        end = min(start + 49, g["valid_frames"])
        rows = (end-start+6)//7
        page = Image.new("RGB", (7*tile_w, rows*(tile_h+tile_caption)), "black")
        draw = ImageDraw.Draw(page)
        for i, frame in enumerate(range(start, end)):
            raw = streams[role][frame*frame_bytes:(frame+1)*frame_bytes]
            picture = Image.frombytes("RGB", (width, height), raw).resize((tile_w, tile_h))
            px, py = (i % 7)*tile_w, (i // 7)*(tile_h+tile_caption)
            page.paste(picture, (px, py))
            draw.text((px+5, py+tile_h+2), f"{role} · frame {frame:03d}", font=font, fill="white")
        path = folder / f"full_frames_{start:03d}_{end-1:03d}.jpg"
        page.save(path, quality=93)
        full_frames.append({**bind(path), "frames_inclusive": [start,end-1]})
    destination.write_text(json.dumps({
        "source_id": case_id, "role": role, "frame_range": [0, g["valid_frames"]-1],
        "column_order": [key for key, _ in records], "input_videos": dict(records),
        "images": pages, "all_new_frames": full_frames, "same_frame_comparison": True,
    }, ensure_ascii=False, indent=2) + "\n")
    print(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--role", choices=("reverse", "combined"), required=True)
    args = parser.parse_args()
    make(args.case, args.role)
