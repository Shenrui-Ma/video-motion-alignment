import subprocess,json,hashlib,os;from pathlib import Path
os.environ["CUDA_VISIBLE_DEVICES"]=""
p=Path('/data4/researcher/h3_runs/timing_oxygen_online_resume_r138_20261020/audit/observations/step010_9b81bdd7e53044d38a9bf68340333667/native.mp4');d=Path('/data4/researcher/h3_runs/oxygen_online_recovery_metrics_r138_20261020/index10_visual');d.mkdir(parents=True,exist_ok=True);indices=[4, 9, 14, 19, 25, 30, 35, 40]
h=hashlib.sha256(p.read_bytes()).hexdigest();assert h=="ed3c3e0c77305dbacc8f3bb976097ad3ce2221d5e5f0f0ff5faf0fdcdad24048"
files={}
for i in indices:
 q=d/("ordinary_%03d.jpg"%i);subprocess.run(["ffmpeg","-v","error","-threads","1","-i",str(p),"-vf",f"select=eq(n\\,{i}),crop=1280:720:16:8","-frames:v","1","-q:v","2","-y",str(q)],check=True);files[q.name]=hashlib.sha256(q.read_bytes()).hexdigest()
(d/"EXTRACTION.json").write_text(json.dumps({"video":str(p),"video_sha256":h,"indices":indices,"crop_xywh":[16,8,1280,720],"files":files,"GPU_started":False},indent=2)+"\n")
print(json.dumps({"frames":len(files),"root":str(d)}))