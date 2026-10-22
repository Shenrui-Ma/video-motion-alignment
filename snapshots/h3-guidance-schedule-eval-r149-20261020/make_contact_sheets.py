"""CPU contact sheets from already validated, same-frame four-column media."""
import argparse
from PIL import Image, ImageDraw, ImageFont
from common import ROOT, FONT, bound, read, require, verify_record, write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--schedule", required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    args = parser.parse_args()
    folder = ROOT / "review" / args.case / args.schedule
    presentation = read(folder / "PRESENTATION.json")
    require(presentation["source_id"] == args.case and presentation["schedule"] == args.schedule,
            "Wrong presentation")
    require(0 <= args.start <= args.end < presentation["valid_frames"], "Frame domain differs")
    records = {item["frame"]: item for item in presentation["screenshots"]}
    out = folder / "contacts"
    out.mkdir(exist_ok=True)
    font = ImageFont.truetype(FONT, 24)
    sheets = []
    for first in range(args.start, args.end + 1, 5):
        frames = list(range(first, min(first + 5, args.end + 1)))
        images = []
        for frame in frames:
            verify_record(records[frame])
            image = Image.open(records[frame]["file"]).convert("RGB")
            require(image.size == (2560, 424), "Unexpected four-column frame")
            images.append(image)
        sheet = Image.new("RGB", (2560, 456 * len(images)), "black")
        draw = ImageDraw.Draw(sheet)
        for index, (frame, image) in enumerate(zip(frames, images)):
            y = index * 456
            draw.text((14, y + 2), f"第 {frame:03d} 帧 · {frame / presentation['fps']:.3f} 秒",
                      font=font, fill="white")
            sheet.paste(image, (0, y + 32))
        path = out / f"frames_{frames[0]:03d}_{frames[-1]:03d}.jpg"
        require(not path.exists(), "Existing contact sheet must be preserved")
        sheet.save(path, quality=94, subsampling=0)
        sheets.append({**bound(path), "frames": frames})
    write(out / f"INDEX_{args.start:03d}_{args.end:03d}.json", {
        "presentation": bound(folder / "PRESENTATION.json"),
        "frame_domain": [args.start, args.end], "fps": presentation["fps"],
        "labels": presentation["labels"], "sheets": sheets,
        "status": "PER_JOB_VERIFIED_BATCH_RELEASE_PENDING",
        "scope": "Contiguous frames; original four columns and Chinese bottom captions retained."})
    print(str(out))


if __name__ == "__main__":
    main()
