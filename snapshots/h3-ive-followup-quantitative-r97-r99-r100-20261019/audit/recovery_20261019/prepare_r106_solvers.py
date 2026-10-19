"""Bind completed R106 solver videos to the unchanged official IVE MF path."""
from pathlib import Path
import hashlib,json,shutil,subprocess,os,sys
H=Path(__file__).resolve().parent;BASE=H.parents[1];P=BASE.parent
C=P/'h3-sampler-control-metrics-r106-20261019';PROD=P/'h3-timing-sampler-control-r106-20261019';PY='/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
sys.path.insert(0,str(C/'scripts'));import consume;consume.validate_collected()
name='r106_short_0252_solvers';r=H/name;assert not r.exists();r.mkdir();(r/'audit').mkdir()
for d in ('scripts','runtime','configs'):shutil.copytree(BASE/d,r/d)
case=r/'cases'/name;(case/'inputs').mkdir(parents=True)
gate=read(C/'incoming/gate.json');mf=read(C/'prepared/MF_INPUTS.json');assert mf['actual_gate_sha256']==sha(C/'incoming/gate.json') and mf['frame_count']==98
cfg=read(r/'configs/RUNTIME.json');cfg['remote_root']='/data4/researcher/h3_runs/ive_r106_sampler_mf_20261019';cfg['GPU_execution_status']='CPU_READY_ROOT_SCHEDULING_REQUIRED';put(r/'configs/RUNTIME.json',cfg)
paths={'source_full.mp4':PROD/'inputs/short_0252_video.mp4','source_original.mp4':PROD/'inputs/short_0252_original.mp4','source_provenance.json':PROD/'inputs/short_0252_provenance.json','PAIR_RUNTIME_GATE.json':C/'incoming/gate.json','COLLECTION.json':C/'incoming/COLLECTION.json','CONSUMER_MF_INPUTS.json':C/'prepared/MF_INPUTS.json'}
for role in ('euler','res_multistep'):
 paths[role+'.mp4']=C/'incoming'/(role+'.mp4');paths[role+'_history.json']=C/'incoming'/(role+'_history.json')
for n,p in paths.items():shutil.copy2(p,case/'inputs'/n)
spec={'case_id':name,'source_id':'short_0252','valid_frames':98,'total_frames':107,'fps':24,'crop_xywh':[16,8,1280,720],'gate':{'file':'inputs/PAIR_RUNTIME_GATE.json','sha256':sha(paths['PAIR_RUNTIME_GATE.json']),'schema':gate['schema'],'valid_frame_keys':['valid_frames'],'crop_keys':['evaluation_crop_xywh']},'source':{'full_file':'inputs/source_full.mp4','full_sha256':sha(paths['source_full.mp4']),'original_file':'inputs/source_original.mp4','original_sha256':sha(paths['source_original.mp4']),'provenance_file':'inputs/source_provenance.json','provenance_sha256':sha(paths['source_provenance.json'])},'targets':{}}
for role in ('euler','res_multistep'):
 d=gate['runs'][role];assert d['NFE']==20 and d['routed_blocks']==0 and d['valid_frames']==98 and d['video']['sha256']==sha(paths[role+'.mp4'])
 spec['targets'][role]={'full_file':'inputs/'+role+'.mp4','full_sha256':d['video']['sha256'],'history_file':'inputs/'+role+'_history.json','history_sha256':sha(paths[role+'_history.json']),'run_id':d['run_id'],'gate_video_keys':['runs',role,'video'],'gate_run_keys':['runs',role,'run_id'],'method_label':'ordinary '+role}
put(case/'SPEC.json',spec);put(case/'INTAKE_RECEIPT.json',{'consumer':str(C),'consumer_freeze_sha256':sha(C/'CONSUMER_FREEZE.json'),'inputs':{k:{'path':str(v),'sha256':sha(v)} for k,v in paths.items()},'CUDA_started':False})
p=subprocess.run([PY,str(r/'scripts/prepare.py'),'--case',name,'--ffmpeg','/opt/homebrew/bin/ffmpeg','--ffprobe','/opt/homebrew/bin/ffprobe'],capture_output=True,text=True,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'));(r/'audit/PREPARE.log').write_text(p.stdout+p.stderr);assert p.returncode==0
m=read(case/'INPUTS.json')
for role in ('source','euler','res_multistep'):assert m['roles'][role]['score_frame_md5']==mf['files'][role]['decoded_frame_md5']
put(r/'audit/READY_FOR_TRACKER_BINDING.json',{'passed':True,'fresh_roles':['source','euler','res_multistep'],'frame_count':98,'input_sha256':sha(case/'INPUTS.json'),'consumer_pixels_exact':True,'CUDA_started':False})
print(json.dumps({'root':str(r),'input_sha256':sha(case/'INPUTS.json'),'CUDA_started':False}))
