"""One-shot original intake checks, compact media only. No GPU, polling or root review."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[2]
DEST=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"scripts"))
import consume_pair
from common import read,sha,bound,require,info
from paired import verify_pair_intake
from render_pair import media_info,check_time,choose_font

FFMPEG="/opt/homebrew/bin/ffmpeg"
FFPROBE="/opt/homebrew/bin/ffprobe"
LABELS=("参考视频","普通编辑","固定时序引导")


def save(path,value):
    require(not path.exists(),"evidence already exists")
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")


def inputs():
    p=info("short_0252")
    return [ROOT/p["source"]["file"],ROOT/"incoming_pairs/short_0252/native.mp4",
            ROOT/"incoming_pairs/short_0252/forced.mp4"]


def render():
    verify_pair_intake("short_0252")
    media=inputs()
    for p in media:check_time(media_info(p,FFPROBE),107,1312,736)
    font=choose_font()
    face=ImageFont.truetype(str(font),26)
    caption=Image.new("RGB",(1920,52),"black")
    d=ImageDraw.Draw(caption)
    for col,label in enumerate(LABELS):
        d.text((col*640+(640-d.textlength(label,font=face))/2,11),label,font=face,fill="white")
    cap=DEST/"caption.png";caption.save(cap)
    video=DEST/"source_native_guided_full98.mp4"
    cmd=[FFMPEG,"-v","error","-nostdin","-n"]
    for p in media:cmd+=["-threads","1","-i",str(p)]
    cmd+=["-framerate","24","-loop","1","-i",str(cap)]
    filters=[f"[{i}:v]crop=1280:720:16:8,trim=end_frame=98,setpts=PTS-STARTPTS,scale=640:360:flags=lanczos,setsar=1[v{i}]" for i in range(3)]
    filters+=["[v0][v1][v2]hstack=inputs=3:shortest=1[images]",
              "[images][3:v]vstack=inputs=2:shortest=1[out]"]
    cmd+=["-filter_complex_threads","2","-filter_complex",";".join(filters),"-map","[out]","-frames:v","98",
          "-an","-fps_mode","vfr","-c:v","libx264","-crf","19","-preset","fast","-pix_fmt","yuv420p",
          "-threads","2","-movflags","+faststart",str(video)]
    subprocess.run(cmd,check=True,timeout=240)
    check_time(media_info(video,FFPROBE),98,1920,412)
    # Ten small pages cover every frame; retain three exact full-scene static keyframes.
    w,h,row_h=384,216,244
    pages=[];readers=[]
    face=ImageFont.truetype(str(font),17);small=ImageFont.truetype(str(font),14)
    static_frames=(4,10,19);static=Image.new("RGB",(w*3,row_h*3),"black")
    static_draw=ImageDraw.Draw(static)
    try:
        for p in media:
            readers.append(subprocess.Popen([FFMPEG,"-v","error","-nostdin","-threads","1","-i",str(p),
                "-vf",f"crop=1280:720:16:8,scale={w}:{h}:flags=lanczos","-frames:v","98",
                "-f","rawvideo","-pix_fmt","rgb24","-threads","1","-"],stdout=subprocess.PIPE))
        for start in range(0,98,10):
            indices=list(range(start,min(start+10,98)))
            im=Image.new("RGB",(w*3,row_h*len(indices)),"black");draw=ImageDraw.Draw(im)
            for row,ix in enumerate(indices):
                for col,proc in enumerate(readers):
                    raw=proc.stdout.read(w*h*3);require(len(raw)==w*h*3,"missing physical frame")
                    frame=Image.frombytes("RGB",(w,h),raw)
                    im.paste(frame,(w*col,row_h*row))
                    draw.text((w*col+5,row_h*row+h+3),f"{ix:02d} | {ix/24:.3f}s | {LABELS[col]}",font=small,fill="white")
                    if ix in static_frames:
                        sy=static_frames.index(ix)*row_h;static.paste(frame,(w*col,sy))
                        static_draw.text((w*col+5,sy+h+3),f"{ix:02d} | {LABELS[col]}",font=face,fill="white")
            p=DEST/f"full98_{start:03d}_{indices[-1]:03d}.jpg";im.save(p,quality=90)
            pages.append(dict(file=p.name,sha256=sha(p),physical_frame_indices=indices))
        for proc in readers:
            require(not proc.stdout.read(1) and proc.wait(timeout=30)==0,"decoder trailing data/failure")
    finally:
        for proc in readers:
            if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
    static_path=DEST/"static_004_010_019.jpg";static.save(static_path,quality=94)
    save(DEST/"FRAME_LEDGER.json",dict(schema="r141b-independent-compact-full98-v1",
         collection=bound(ROOT/"incoming_pairs/short_0252/COLLECTION.json"),
         gate=bound(ROOT/"incoming_pairs/short_0252/PAIR_RUNTIME_GATE.json"),
         inputs=[bound(p) for p in media],columns=["source","native","guided"],fps=24,valid_frames=98,
         evaluated_indices=list(range(98)),crop_xywh=[16,8,1280,720],pages=pages,
         compact_video=bound(video),static_keyframes=bound(static_path),all_frames_prepared=True,
         all_frames_inspected=False,root_review_written=False,GPU_started=False,HTML_created=False))
    case=info("short_0252")
    graph=ROOT/"incoming_pairs/short_0252/native_graph.json"
    seed=read(graph)["6"]["inputs"]["noise_seed"]
    require(seed==2026101703,"unexpected inventory seed")
    save(DEST/"PENDING_INVENTORY_ENTRY.json",dict(
        schema="r141b-pending-inventory-entry-v1",
        proposed_inventory_id="r141b_short_0252_seed2026101703_generic_retention",
        status="PENDING_ROOT_ID_CONFIRMATION_AND_REVIEW",source_id="short_0252",seed=seed,
        prompt=dict(label="P3",version=case["prompt_version"],text=case["prompt"],
            sha256=hashlib.sha256(case["prompt"].encode()).hexdigest(),
            description="Official requested edit in task/reference envelope, with generic retention of people, scene, framing, camera motion and actions except explicitly requested changes.",
            actual_graph=bound(graph)),
        media={role:bound(p) for role,p in zip(("source","native","guided","comparison"),media+[video])},
        actual_guided_role="forced",actual_native_graph=bound(graph),
        actual_guided_graph=bound(ROOT/"incoming_pairs/short_0252/forced_graph.json"),
        domain=dict(original_geometry=case["geometry"],valid_frames=98,fps=24,
            evaluated_physical_indices=list(range(98)),excluded_padding_indices=list(range(98,107)),
            crop_xywh=case["crop_xywh"],comparison_scale_per_column=[640,360]),
        actual_pair_gate=bound(ROOT/"incoming_pairs/short_0252/PAIR_RUNTIME_GATE.json"),
        actual_collection=bound(ROOT/"incoming_pairs/short_0252/COLLECTION.json"),
        MF_inputs=bound(ROOT/"prepared/short_0252/paired/MF_INPUTS.json"),
        independent_review="PENDING",root_review="PENDING",official_MF="PENDING",
        inventory_id_confirmed_by_root=False,merged_into_main_inventory=False,
        prior_showcase_modified=False,new_independent_source_count=0))
    print(json.dumps(bound(DEST/"FRAME_LEDGER.json")))


def consume():
    consume_pair.bind("host9_oxygen_generic_retention_r141b_attempt1")
    state=consume_pair.status("short_0252")
    require(state["status"]=="PASSED_GATE","actual pair gate required")
    collected=consume_pair.collect("short_0252")
    metrics=consume_pair.prepare_metrics("short_0252",paired=True)
    save(DEST/"INTAKE.json",dict(collection=collected,metric_inputs=metrics,
        bound_consumer=bound(ROOT/"scripts/consume_pair.py"),
        pipeline="Same bind/status/collect/metric_inputs functions; compact presentation replaces default large pages/HTML.",
        GPU_started=False,root_review_written=False))
    render()


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--render-only",action="store_true");a=p.parse_args()
    render() if a.render_only else consume()
