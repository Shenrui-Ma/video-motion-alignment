"""One compact five-column comparison and complete same-index review pages; no HTML."""
import argparse
import subprocess
from PIL import Image, ImageDraw, ImageFont
from common import *

ROLES = ("source", "native", "fixed", "originalauto", "centeredauto")
LABELS = ("参考视频", "普通编辑", "固定引导", "原自动引导 R138", "中心化筛选 R142")
FFMPEG, FFPROBE = "/opt/homebrew/bin/ffmpeg", "/opt/homebrew/bin/ffprobe"


def prepare():
    actual()
    m = read(ROOT / "prepared/MF_INPUTS.json")
    inputs = [Path(m["full_videos"][role]["file"]) for role in ROLES]
    helper = load_helper("r120_render_pair")
    for p in inputs:
        helper.check_time(helper.media_info(p, FFPROBE), 107, 1312, 736)
    dest = ROOT / "showcase"
    require(not dest.exists(), "media already prepared")
    dest.mkdir()
    font = helper.choose_font()
    caption = Image.new("RGB", (3200, 64), "black")
    draw = ImageDraw.Draw(caption)
    face = ImageFont.truetype(str(font), 26)
    for col, label in enumerate(LABELS):
        draw.text((col*640+(640-draw.textlength(label,font=face))/2, 18), label, font=face, fill="white")
    cap = dest / "caption.png"
    caption.save(cap)
    video = dest / "comparison_full98.mp4"
    cmd = [FFMPEG, "-v", "error", "-nostdin", "-n"]
    for p in inputs:
        cmd += ["-threads", "1", "-i", str(p)]
    cmd += ["-framerate", "24", "-loop", "1", "-i", str(cap)]
    filters = [f"[{i}:v]crop=1280:720:16:8,trim=end_frame=98,setpts=PTS-STARTPTS,scale=640:360:flags=lanczos,setsar=1[v{i}]" for i in range(5)]
    filters += ["[v0][v1][v2][v3][v4]hstack=inputs=5:shortest=1[images]",
                "[images][5:v]vstack=inputs=2:shortest=1[out]"]
    cmd += ["-filter_complex_threads", "2", "-filter_complex", ";".join(filters), "-map", "[out]",
            "-frames:v", "98", "-an", "-fps_mode", "vfr", "-c:v", "libx264", "-crf", "19",
            "-preset", "fast", "-pix_fmt", "yuv420p", "-threads", "2", "-movflags", "+faststart", str(video)]
    subprocess.run(cmd, check=True, timeout=420)
    helper.check_time(helper.media_info(video, FFPROBE), 98, 3200, 424)
    # Stream raw frames instead of retaining five complete RGB clips in memory.
    decoders = []
    ledger = []
    review = dest / "full98"
    review.mkdir()
    w, h, row_h, per_page = 480, 270, 314, 7
    face = ImageFont.truetype(str(font), 19)
    small = ImageFont.truetype(str(font), 16)
    static_indices = (4, 10, 19)
    static_columns = (0, 1, 3, 4)
    static = Image.new("RGB", (w*4, row_h*len(static_indices)), "black")
    static_draw = ImageDraw.Draw(static)
    try:
        for p in inputs:
            decoders.append(subprocess.Popen([FFMPEG, "-v", "error", "-nostdin", "-threads", "1", "-i", str(p),
                "-vf", f"crop=1280:720:16:8,scale={w}:{h}:flags=lanczos", "-frames:v", "98",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-threads", "1", "-"], stdout=subprocess.PIPE))
        for start in range(0, 98, per_page):
            indices = list(range(start, min(start+per_page, 98)))
            im = Image.new("RGB", (w*5, row_h*len(indices)), "black")
            draw = ImageDraw.Draw(im)
            for row, frame in enumerate(indices):
                for col, process in enumerate(decoders):
                    raw = process.stdout.read(w*h*3)
                    require(len(raw) == w*h*3, "incomplete decoded physical frame")
                    frame_image = Image.frombytes("RGB", (w,h), raw)
                    im.paste(frame_image, (col*w, row*row_h))
                    draw.text((col*w+8, row*row_h+h+20), LABELS[col], font=face, fill="white")
                    if frame in static_indices and col in static_columns:
                        sx, sy = static_columns.index(col)*w, static_indices.index(frame)*row_h
                        static.paste(frame_image, (sx,sy))
                        static_draw.text((sx+8,sy+h+20),LABELS[col],font=face,fill="white")
                        static_draw.text((sx+8,sy+h+1),f"frame {frame} | {frame/24:.3f}s",font=small,fill="#bbb")
                draw.text((8,row*row_h+h+1), f"frame {frame} | {frame/24:.3f}s", font=small, fill="#bbb")
            path = review / f"{len(ledger)+1:03}.jpg"
            im.save(path, quality=90)
            ledger.append(dict(file=path.name, sha256=sha(path), physical_frame_indices=indices))
        for process in decoders:
            require(not process.stdout.read(1) and process.wait(timeout=30) == 0, "decoder trailing data/failure")
    finally:
        for process in decoders:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
    collection = bound(ROOT / "incoming/actual/COLLECTION.json")
    static_path = dest/"static_pose_004_010_019.jpg"
    static.save(static_path,quality=92)
    save(review / "FRAME_LEDGER.json", dict(columns=ROLES, valid_frames=98, fps=24, crop_xywh=[16,8,1280,720],
         collection=collection, input_media=[bound(p) for p in inputs], pages=ledger,
         all_frames_prepared=True, all_frames_inspected=False))
    save(dest / "PRESENTATION.json", dict(columns=ROLES, labels=LABELS, collection=collection,
         video=bound(video), frames=list(range(98)), fps=24, crop_xywh=[16,8,1280,720],
         display_scale=[640,360], all_frames_review=bound(review/"FRAME_LEDGER.json"),
         static_pose_review=dict(file=bound(static_path),physical_frame_indices=list(static_indices),
             columns=[ROLES[i] for i in static_columns],full_review_range_inclusive=[4,19],
             scope="Final videos only. Centered eligibility is a hypothesis; static pose mismatch may matter."),
         quality_review="PENDING", HTML_created=False))
    plan = read(ROOT / "configs/EVALUATION_PLAN.json")
    save(ROOT / "audit/REVIEW_TEMPLATE.json", dict(collection=collection, all_valid_frames_inspected=False,
         examined_frames=[], task_acceptance=dict(status="PENDING", elderly_woman_identity=None,
         child_cabin_and_mask_retained=None, action_sequence_retained=None, framing_retained=None,
         source_man_identity_copy_observed=None, notes=""),
         static_pose=dict(frame_range_inclusive=[4,19],all_range_frames_inspected=False,
             keyframe_observations=[dict(frame=i,source_native_originalauto_centeredauto_notes="") for i in static_indices],
             centeredauto_relative_to_originalauto="PENDING",worsened_static_pose_preservation=None,
             notes="",evidence_scope="final_video_only"),
         events=[dict(id=e["id"], centeredauto_frames=None, centeredauto_status="PENDING", notes="") for e in plan["events"]],
         conclusion=""))
    return bound(dest / "PRESENTATION.json")


if __name__ == "__main__":
    print(json.dumps(prepare()))
