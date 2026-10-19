from pathlib import Path
import sys,fcntl,json,subprocess,time
R=Path("/Users/researcher/DevProjects/h3-timing-manual-source51310-r41-20261017/analysis/postrun");sys.path.insert(0,str(R))
from contract import read,sha,require,save,check_playback_probe
out=Path(__file__).resolve().parent
lock=Path("/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock")
with lock.open("a") as f:
 try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:print("BUSY");raise SystemExit(75)
 p=read(R/"PROTOCOL.json");run=p["cases"][0]["run_id"];arc=R/"captured"/run
 videos={"SOURCE":arc/"input/source_51310_video.mp4","Native":Path("/Users/researcher/DevProjects/h3-timing-new-actions-native-r38-20261017/analysis/postrun/captured/batch/output/r38_source_51310_seed2026101701_native_00001_.mp4"),"Manual":arc/"output"/(run+"_00001_.mp4")}
 expected=[p["source_video_sha256"],p["parents"]["Native"]["video_sha256"],read(arc/"analysis/pose/COMPLETE.json")["metadata"]["video_sha256"]]
 for video,digest in zip(videos.values(),expected):require(sha(video)==digest,"input changed")
 layout=p["presentation"]["layouts"]["source_native_manual"];caption=R/layout["asset"];require(sha(caption)==layout["asset_sha256"],"caption changed")
 folder=out/"media";folder.mkdir();records={};ffmpeg="/opt/homebrew/bin/ffmpeg";ffprobe="/opt/homebrew/bin/ffprobe"
 for key,v in videos.items():
  data=subprocess.check_output([ffprobe,"-v","error","-select_streams","v:0","-show_streams","-show_frames","-show_entries","stream=width,height,r_frame_rate,avg_frame_rate,duration,time_base:frame=best_effort_timestamp_time","-of","json",str(v)])
  records[key]=dict(check_playback_probe(json.loads(data)),sha256=sha(v))
 frames=p["fixed_visual_frames"];selection="+".join("eq(n\\,"+str(i)+")" for i in frames)
 graph="[0:v]scale=656:368:flags=area[a];[1:v]scale=656:368:flags=area[b];[2:v]scale=656:368:flags=area[c];[a][b][c]hstack=inputs=3[tiles];[tiles][3:v]vstack=inputs=2,split=2[v][s];[s]select='"+selection+"'[stills]"
 cmd=[ffmpeg,"-v","error","-nostdin"]
 for v in videos.values():cmd += ["-threads","1","-i",str(v)]
 cmd += ["-i",str(caption),"-filter_complex_threads","1","-filter_complex",graph,"-map","[v]","-an","-c:v","libx264","-threads","1","-crf","18","-pix_fmt","yuv420p","-movflags","+faststart",str(folder/"comparison_141frames.mp4"),"-map","[stills]","-fps_mode","vfr","-threads","1",str(folder/"still_%02d.png")]
 subprocess.run(cmd,check=True)
 for j,i in enumerate(frames,1):(folder/f"still_{j:02d}.png").rename(folder/f"frame{i:03d}.png")
 probe=json.loads(subprocess.check_output([ffprobe,"-v","error","-select_streams","v:0","-show_frames","-show_entries","stream=width,height,nb_frames,r_frame_rate:frame=best_effort_timestamp_time","-of","json",str(folder/"comparison_141frames.mp4")]))
 require(len(probe["frames"])==141,"output count");require(all(abs(float(q["best_effort_timestamp_time"])-i/24)<1e-6 for i,q in enumerate(probe["frames"])),"output PTS")
 save(folder/"PRESENTATION.json",{"inputs":records,"frames":141,"fps":24,"fixed_frames":frames,"labels":layout["labels"],"caption_sha256":sha(caption),"presentation_only":True,"renderer":"ffmpeg area scaling of original full canvas, Chinese footer below, same source frame indices","video_sha256":sha(folder/"comparison_141frames.mp4"),"files":{q.name:sha(q) for q in folder.iterdir() if q.is_file()},"quality_verdict":"pending"})
 print("COMPLETE",folder)
