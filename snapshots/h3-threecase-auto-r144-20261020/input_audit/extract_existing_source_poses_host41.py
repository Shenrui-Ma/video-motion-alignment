from pathlib import Path
import hashlib,json,os,subprocess,sys,time
root=Path('/data4/researcher/h3_runs/threecase_auto_r144_20261020/input_audit');root.mkdir(parents=True,exist_ok=True)
old=Path('/data4/researcher/h3_runs/timing_oxygen_online_resume_r138_20261020')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(1048576),b''):h.update(c)
 return h.hexdigest()
script=old/'scripts/pose_probe.py';assert sha(script)=='04c6dd432ddf102300a4cd065f4de8b9c2bc0661ce1abb06d994330b32ae693f'
b=json.loads((old/'configs/observer_external_bindings.json').read_text())
checked={}
for p,h in b['external_files'].items():
 if '/dwpose/' in p or 'DWPose' in p:
  assert Path(p).is_file() and sha(p)==h,p
  checked[p]=h
assert len(checked)==4
jobs=[('short_0358','ed48b90939dd7387f5a4e56a371394e899b600baa230740544ec75ea9fd531fd',105,107),('long_0039','ed29fd0615aaeee1f24f103b37bea5f18dc7daebce0159b8ff460492ca6c934c',106,107)]
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4')
started=time.time();receipts=[]
(root/'CPU_POSE_PREFLIGHT.json').write_text(json.dumps({'script':str(script),'sha256':sha(script),'weights_and_code':checked,'CUDA_VISIBLE_DEVICES':'','threads':4,'network_downloads':False,'jobs':jobs,'started_unix':started},indent=2)+'\n')
for sid,video_sha,valid,total in jobs:
 video=Path('/data4/researcher/h3_runs/ive_context_mf_20261020/cases')/sid/'source_full.mp4';assert sha(video)==video_sha
 output=root/sid;output.mkdir(exist_ok=True)
 command=[sys.executable,str(script),'--video',str(video),'--output-dir',str(output),'--aux-root',b['aux_root'],'--threads','4','--stride','1']
 print(json.dumps({'started_source':sid,'valid_frames':valid,'sampled_frames':total}),flush=True)
 before=time.monotonic()
 with (output/'pose_cpu.log').open('x') as log:subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
 pose=output/'source_full.pose.json';v=json.loads(pose.read_text());assert v['video']['sha256']==video_sha and v['video']['fps']==24 and v['video']['container_frame_count']==total
 assert len(v['frames'])==total and v['provenance']['device']=='cpu' and v['provenance']['providers']==['CPUExecutionProvider']
 result={'source_id':sid,'source_pose':str(pose),'source_pose_sha256':sha(pose),'source_video':str(video),'source_video_sha256':video_sha,'processed_frames':len(v['frames']),'valid_frames':valid,'excluded_padding':list(range(valid,total)),'frame_count':total,'fps':24,'content_crop_xywh':[16,8,1280,720],'CPU_seconds':time.monotonic()-before,'selection_rule':v['provenance']['selection_rule'],'ROI':None,'oxygen_adult_ROI_applied':False,'GPU_started':False}
 (output/'POSE_READY.json').write_text(json.dumps(result,indent=2)+'\n');receipts.append(result);print(json.dumps(result),flush=True)
(root/'CPU_POSE_COMPLETE.json').write_text(json.dumps({'passed':True,'receipts':receipts,'wall_seconds':time.time()-started,'GPU_started':False,'downloaded':False},indent=2)+'\n')
