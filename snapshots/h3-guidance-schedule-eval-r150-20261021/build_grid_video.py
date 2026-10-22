"""Rearrange the verified seven-column videos into a source / three / three grid."""
import argparse
import subprocess
from pathlib import Path

from common import ROOT, FFMPEG, FONT, bound, inspect, read, require, verify_record, write

OLD = ROOT.with_name("h3-guidance-schedule-eval-r149-20261020")
ROLES = ["source", "native", "early", "fixed", "late", "split", "global_weak"]
LABELS = ["参考视频", "普通编辑", "引导 1–9 步", "引导 7–15 步",
          "引导 12–20 步", "引导 1–4＋16–20 步", "全程弱引导 α=0.25"]
CAPTION_HEIGHT = 24
CELL_HEIGHT = 360 + CAPTION_HEIGHT
CONTROL_PADDING = 80
VIDEO_HEIGHT = 3 * CELL_HEIGHT + CONTROL_PADDING


def render(source_manifest):
    source = read(source_manifest)
    require(source["roles"] == ROLES and source["full_decode_passed"], "Unverified source layout")
    require((source["width"], source["height"]) == (4480, 424), "Unexpected panel dimensions")
    verify_record(source["video"])
    dest = ROOT / "overview_grid_controls" / source["source_id"]
    manifest = dest / "PRESENTATION.json"
    if manifest.exists():
        saved = read(manifest)
        require(saved["source_presentation"] == bound(source_manifest), "Source layout changed")
        verify_record(saved["video"])
        if saved.get("control_padding_bottom") == CONTROL_PADDING:
            return manifest
    dest.mkdir(parents=True, exist_ok=True)
    output = dest / f"comparison_padding{CONTROL_PADDING}.mp4"
    from PIL import Image, ImageDraw, ImageFont
    footer = Image.new("RGB", (4480, CAPTION_HEIGHT), "black")
    draw = ImageDraw.Draw(footer)
    font = ImageFont.truetype(FONT, 22)
    for i, label in enumerate(LABELS):
        left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
        draw.text((640*i + (640-(right-left))/2-left,
                   (CAPTION_HEIGHT-(bottom-top))/2-top), label, font=font, fill="white")
    caption = dest / "caption.png"
    footer.save(caption)
    filters = ["[0:v]split=7" + "".join(f"[s{i}]" for i in range(7))]
    filters += ["[1:v]split=7" + "".join(f"[c{i}]" for i in range(7))]
    for i in range(7):
        filters += [f"[s{i}]crop=640:360:{640*i}:0[image{i}]",
                    f"[c{i}]crop=640:{CAPTION_HEIGHT}:{640*i}:0[text{i}]",
                    f"[image{i}][text{i}]vstack=inputs=2:shortest=1[p{i}]"]
    filters += [f"[p0]pad=1920:{CELL_HEIGHT}:640:0:black[top]",
                "[p1][p2][p3]hstack=inputs=3[middle]",
                "[p4][p5][p6]hstack=inputs=3[bottom]",
                f"[top][middle][bottom]vstack=inputs=3,pad=1920:{VIDEO_HEIGHT}:0:0:black,setsar=1[out]"]
    command = [FFMPEG, "-v", "error", "-nostdin", "-n", "-threads", "1",
               "-i", source["video"]["file"],
               "-loop", "1", "-framerate", str(source["fps"]), "-i", str(caption),
               "-filter_complex_threads", "2",
               "-filter_complex", ";".join(filters), "-map", "[out]", "-an",
               "-frames:v", str(source["valid_frames"]), "-c:v", "libx264",
               "-crf", "16", "-preset", "fast", "-threads", "2",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)]
    subprocess.run(command, check=True, timeout=300)
    props = inspect(output)
    require((int(props["width"]), int(props["height"])) == (1920, VIDEO_HEIGHT), "Grid dimensions differ")
    require(int(props["nb_read_frames"]) == source["valid_frames"], "Frame count differs")
    from fractions import Fraction
    require(Fraction(props["avg_frame_rate"]) == source["fps"], "Frame rate differs")
    subprocess.run([FFMPEG, "-v", "error", "-nostdin", "-threads", "1",
                    "-i", str(output), "-f", "null", "-"], check=True, timeout=90)
    write(manifest, dict(schema="r150-native-controls-bottom-space-v3", source_id=source["source_id"],
                         source_presentation=bound(source_manifest), source_video=source["video"],
                         video=bound(output), roles=ROLES,
                         rows=[[None, "source", None], ["native", "early", "fixed"],
                               ["late", "split", "global_weak"]],
                         width=1920, height=VIDEO_HEIGHT, cell_width=640, cell_height=CELL_HEIGHT,
                         control_padding_bottom=CONTROL_PADDING,
                         caption_height=CAPTION_HEIGHT, caption=bound(caption),
                         valid_frames=source["valid_frames"], fps=source["fps"],
                         full_decode_passed=True, temporal_transform="none"))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    args = parser.parse_args()
    paths = sorted((OLD / "overview").glob("*/PRESENTATION.json")) + sorted((ROOT / "overview").glob("*/PRESENTATION.json"))
    require(len(paths) == 10, "Expected ten existing comparison videos")
    for path in paths:
        if args.case is None or path.parent.name == args.case:
            print(render(path), flush=True)
