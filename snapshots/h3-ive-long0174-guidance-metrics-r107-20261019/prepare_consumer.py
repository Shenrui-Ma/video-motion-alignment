from pathlib import Path
import json,hashlib,shutil
R=Path(__file__).resolve().parent;P=R.parent/'h3-timing-ive-long0174-guidance-r107-20261019';B=R.parent/'h3-ive-p1-guidance-metrics-r99-20261019';C=R.parent/'h3-ive-native-screen-metrics-r96-20261018'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
for folder in ('scripts','configs','incoming','showcase','audit','tests'):(R/folder).mkdir(parents=True,exist_ok=True)
b=read(P/'configs/parent_bindings.json')['long_0174'];runtime=read(P/'configs/runtime.json')
config={'producer_local':str(P),'producer_remote':runtime['remote_root'],'host':runtime['host'],'cases':{'long_0174':{'source_id':'long_0174','run_id':b['run_id'],'native_video':{'file':str(C/'incoming/long_0174/native.mp4'),'sha256':b['native_video']['sha256']},'reference_video':{'file':str(C/'inputs/long_0174_video.mp4'),'sha256':sha(C/'inputs/long_0174_video.mp4')},'valid_frames':145,'first_six_predictions':b['first_six_predictions'],'task':'建筑外行走：女子白色衣服改为黑色','parent_gate':{'file':str(C/'incoming/long_0174/NATIVE_RUNTIME_GATE.json'),'sha256':sha(C/'incoming/long_0174/NATIVE_RUNTIME_GATE.json')}}},'fps':24,'sampled_frames':158,'crop_xywh':[16,8,1280,720],'method':'固定时序引导：去噪索引6–14，50个DiT层，alpha=1','metric':'IVEBench official MF and visible event timing at unchanged physical timestamps','producer_runtime_sha256':sha(P/'configs/runtime.json'),'producer_seal_sha256':sha(P/'deploy_manifest.json')}
write(R/'configs/contract.json',config);shutil.copy2(P/'deploy_manifest.json',R/'configs/producer_deploy_manifest.json')
text=(B/'scripts/consume.py').read_text().replace('R99','R107').replace('r99-','r107-').replace('r99_','r107_').replace('display.check_time(info, 90, 1312, 736)','display.check_time(info, CONFIG["sampled_frames"], 1312, 736)')
(R/'scripts/consume.py').write_text(text)
print('R107 consumer prepared')
