"""Build additional full-frame audit sheets from a verified actual R116 intake."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import SOURCES, bound, info, require, save, validate_static, verify_intake
from paired import verify_pair_intake
from render_native import check_time, media_info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=SOURCES, required=True)
    parser.add_argument("--paired", action="store_true")
    args = parser.parse_args()
    validate_static()
    gate = (verify_pair_intake if args.paired else verify_intake)(args.source)
    config = info(args.source)
    mode = "paired" if args.paired else "native"
    intake = ROOT / ("incoming_pairs" if args.paired else "incoming") / args.source
    output = ROOT / "audit" / "full_frame_review" / args.source / mode
    output.mkdir(parents=True, exist_ok=False)
    media = {"source": ROOT / config["source"]["file"], "native": intake / "native.mp4"}
    if args.paired:
        media["forced"] = intake / "forced.mp4"
    width, height = 480, 320
    valid, total = config["valid_frames"], config["geometry"]["frames"]
    raw_frames, bindings = {}, {}
    for label, path in media.items():
        properties = media_info(path, "/opt/homebrew/bin/ffprobe")
        check_time(properties, total, 1152, 768)
        raw = subprocess.check_output([
            "/opt/homebrew/bin/ffmpeg", "-v", "error", "-threads", "1", "-i", str(path),
            "-an", "-vf", f"scale={width}:{height}:flags=lanczos", "-frames:v", str(valid),
            "-threads", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
        ])
        size = width * height * 3
        require(len(raw) == valid * size, "Decoded valid-frame count differs")
        raw_frames[label] = [Image.frombytes("RGB", (width, height), raw[i*size:(i+1)*size]) for i in range(valid)]
        bindings[label] = {**bound(path), "all_PTS_checked": True}
    font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 17)
    pages = []
    for start in range(0, valid, 6):
        stop = min(start + 6, valid)
        canvas = Image.new("RGB", (len(media) * width, (height + 28) * (stop-start) + 30), "#0c0d10")
        draw = ImageDraw.Draw(canvas)
        for col, label in enumerate(media):
            draw.text((col*width+8, 5), label.upper(), font=font, fill="white")
        for row, index in enumerate(range(start, stop)):
            y = 30 + row*(height+28)
            draw.text((8, y+3), f"Frame {index:03d} | {index/24:.3f}s | source {index//3}", font=font, fill="#eadca1")
            for col, label in enumerate(media):
                canvas.paste(raw_frames[label][index], (col*width, y+28))
        path = output / f"frames_{start:03d}-{stop-1:03d}.jpg"
        canvas.save(path, quality=94)
        pages.append({**bound(path), "frames": list(range(start, stop))})
    save(output / "MEDIA_BINDINGS.json", {
        "source_id": args.source, "mode": mode,
        "gate": bound(intake / ("PAIR_RUNTIME_GATE.json" if args.paired else "NATIVE_RUNTIME_GATE.json")),
        "collection": bound(intake / "COLLECTION.json"),
        "media": bindings, "pages": pages, "coverage": list(range(valid)),
        "source_original_fps": 8, "generated_fps": 24,
        "source_motion_precision_seconds": 0.125,
    })
    print(json.dumps({"folder": str(output), "frames": valid, "pages": len(pages)}))


if __name__ == "__main__":
    main()
