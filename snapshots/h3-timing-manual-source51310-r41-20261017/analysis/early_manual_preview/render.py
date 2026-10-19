from pathlib import Path
import sys,fcntl,time
R=Path("/Users/researcher/DevProjects/h3-timing-manual-source51310-r41-20261017/analysis/postrun");sys.path.insert(0,str(R))
from contract import read,sha,require,save
from presentation import render_layout
out=Path(__file__).resolve().parent
lock=Path("/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock")
with lock.open("a") as f:
 try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:print("BUSY");raise SystemExit(75)
 p=read(R/"PROTOCOL.json");run=p["cases"][0]["run_id"];arc=R/"captured"/run
 videos={"SOURCE":arc/"input/source_51310_video.mp4","Native":Path("/Users/researcher/DevProjects/h3-timing-new-actions-native-r38-20261017/analysis/postrun/captured/batch/output/r38_source_51310_seed2026101701_native_00001_.mp4"),"Manual":arc/"output"/(run+"_00001_.mp4")}
 require(sha(videos["SOURCE"])==p["source_video_sha256"],"source changed")
 require(sha(videos["Native"])==p["parents"]["Native"]["video_sha256"],"Native changed")
 require(sha(videos["Manual"])==read(arc/"analysis/pose/COMPLETE.json")["metadata"]["video_sha256"],"Manual changed")
 result=render_layout(videos,out/"media",p,p["presentation"]["layouts"]["source_native_manual"])
 print("COMPLETE",len(result["fixed_frames"]),"frames",result["frames"])
