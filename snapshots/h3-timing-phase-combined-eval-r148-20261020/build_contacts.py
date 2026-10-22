"""Compact final-video review pages; no model or pose execution."""
import argparse
import json
from PIL import Image, ImageDraw, ImageFont
from prepare_comparison import ROOT, FONT, bound, read, require


def page(images, output, width):
    font = ImageFont.truetype(FONT, 19)
    row_height = round(324 * width / 1920)
    sheet = Image.new("RGB", (width, len(images) * (row_height + 26)), "black")
    draw = ImageDraw.Draw(sheet)
    for row, (frame, image) in enumerate(images):
        y = row * (row_height + 26)
        with Image.open(image) as original:
            sheet.paste(original.resize((width, row_height), Image.Resampling.LANCZOS), (0, y))
        draw.text((8, y + row_height + 1), f"第 {frame} 帧 · {frame / 24:.3f} 秒",
                  fill="white", font=font)
    sheet.save(output, quality=88)
    return {**bound(output), "frames": [n for n, _ in images]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--key-frames", default="")
    a = p.parse_args()
    root = ROOT / "review" / a.case
    presentation = read(root / "PRESENTATION.json")
    shots = {s["physical_frame"]: s["file"] for s in presentation["screenshots"]}
    require(len(shots) == presentation["valid_frames"], "Full valid-frame images required")
    dest = root / "contacts"
    dest.mkdir(exist_ok=False)
    ordered = sorted(shots.items())
    all_pages = [page(ordered[i:i + 8], dest / f"all_{i // 8 + 1:02d}.jpg", 1280)
                 for i in range(0, len(ordered), 8)]
    keys = sorted(set(map(int, a.key_frames.split(",")))) if a.key_frames else []
    require(all(n in shots for n in keys), "Key frame outside valid domain")
    key_pages = [page([(n, shots[n]) for n in keys[i:i + 4]],
                      dest / f"key_{i // 4 + 1:02d}.jpg", 1920) for i in range(0, len(keys), 4)]
    manifest = {"source_id": a.case, "presentation": bound(root / "PRESENTATION.json"),
                "all_pages": all_pages, "key_pages": key_pages,
                "covers_all_valid_frames": True, "valid_frames": presentation["valid_frames"],
                "manual_review_completed": False}
    (dest / "CONTACTS.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"case": a.case, "contacts": str(dest / "CONTACTS.json"),
                      "all_pages": len(all_pages), "key_pages": len(key_pages)}))


if __name__ == "__main__":
    main()
