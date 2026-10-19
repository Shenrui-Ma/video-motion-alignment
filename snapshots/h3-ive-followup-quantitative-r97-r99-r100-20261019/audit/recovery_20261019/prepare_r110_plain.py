"""Prepare ordinary-only R110 MF against the exact existing R100 source track."""
from pathlib import Path
import json,hashlib,subprocess,shutil
H=Path(__file__).resolve().parent;BASE=H.parents[1];P=BASE.parent
C=P/'h3-ive-basketball-boundprompt-metrics-r110-20261019';I=C/'incoming'
O=H/'r100_short_0114';OC=O/'cases/r100_short_0114';OT=O/'actual_host41/cases/r100_short_0114'
name='r110_short_0114_plain';R=H/name;D=R/'cases'/name
PY='/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
assert not R.exists()
for rel,v in read(C/'CONSUMER_FREEZE.json')['files'].items():assert sha(C/rel)==(v['sha256'] if isinstance(v,dict) else v)
for rel,v in read(I/'COLLECTION.json')['files'].items():assert Path(rel).name==rel and sha(I/rel)==v
assert sha(I/'gate.json')=='2d5a721547dc0ab4fd342f63c11fc2194bb644982ae2e4c3c51b8e9f3618600a'
q='import sys;sys.path.insert(0,'+repr(str(C/'scripts'))+');import consume as c;c.validate_gate(c.read(c.INC/"gate.json"),c.read(c.INC/"COMPLETE.json"),c.read(c.INC/"ROOT_EXIT_RECEIPT.json"),c.read(c.INC/"STARTED.json"))'
subprocess.run([PY,'-c',q],check=True,timeout=60)
gate=read(I/'gate.json');oldspec=read(OC/'SPEC.json');oldm=read(OC/'INPUTS.json');report=read(OT/'tracks/source/REPORT.json')
assert sha(I/'source.mp4')==oldm['roles']['source']['full_sha256']==report['source_prepared_sha256']
assert sha(I/'p1.mp4')==sha(P/'h3-ive-basketball-shortprompt-metrics-r109-20261019/incoming/plain.mp4')
assert sha(I/'COLLECTION.json')=='cce6268f029404a471ec0b7030a34f155369859e8c2a1aa3b483457c159cef03'
assert report['tracks_sha256']==sha(OT/'tracks/source/tracks.npz')
assert report['passed'] and report['tracks_shape']==[1,105,100,2]
R.mkdir()
for folder in ('scripts','runtime','configs'):shutil.copytree(BASE/folder,R/folder)
(R/'audit').mkdir();(D/'inputs').mkdir(parents=True)
copies={'source_full.mp4':I/'source.mp4','source_original.mp4':OC/oldspec['source']['original_file'],'source_provenance.json':OC/oldspec['source']['provenance_file'],'source_score.mp4':OC/oldm['roles']['source']['score_file'],'SOURCE_CACHE_INPUTS.json':OC/'INPUTS.json','NATIVE_RUNTIME_GATE.json':I/'gate.json','plain.mp4':I/'plain.mp4','plain_history.json':I/'history.json','COLLECTION.json':I/'COLLECTION.json','R100_SCORE_VERIFIED.json':O/'RESULT_VERIFIED.json','R109_SCORE_VERIFIED.json':H/'r109_short_0114_plain/RESULT_VERIFIED.json','ACTUAL_VISUAL_REVIEW.json':C/'audit/full105_review/REVIEW.json'}
for rel,path in copies.items():shutil.copy2(path,D/'inputs'/rel)
shutil.copytree(OT/'tracks/source',D/'tracks/source')
shutil.copy2(O/'actual_host41/audit/actual_r100_short_0114_attempt1/source/RELEASED.json',D/'inputs/SOURCE_RELEASED.json')
cfg=read(R/'configs/RUNTIME.json');cfg['remote_root']=f'/data4/researcher/h3_runs/ive_recovery_{name}_20261019';cfg['GPU_execution_status']='CPU_READY_PLAIN_ONLY_AFTER_MAIN_PAIRED_MF';put(R/'configs/RUNTIME.json',cfg)
spec={'case_id':name,'source_id':'short_0114','valid_frames':105,'total_frames':107,'fps':24,'crop_xywh':[16,8,1280,720],'gate':{'file':'inputs/NATIVE_RUNTIME_GATE.json','sha256':sha(I/'gate.json'),'schema':gate['schema']},'source':oldspec['source'],'targets':{'plain':{'full_file':'inputs/plain.mp4','full_sha256':sha(I/'plain.mp4'),'history_file':'inputs/plain_history.json','history_sha256':sha(I/'history.json'),'run_id':gate['run_id'],'gate_video_keys':['video'],'method_label':'ordinary reference-bound short prompt; no guidance'}},'source_cache_reuse':{'original_cache_dir':str(OT/'tracks/source'),'cache_inputs_file':'inputs/SOURCE_CACHE_INPUTS.json','cache_inputs_sha256':sha(OC/'INPUTS.json'),'selection_sha256':report['selection_sha256'],'source_report_sha256':sha(OT/'tracks/source/REPORT.json'),'source_tracks_sha256':sha(OT/'tracks/source/tracks.npz'),'source_score_sha256':report['source_score_sha256'],'host':report['admission_before_cuda']['hostname'],'gpu_name':report['admission_before_cuda']['gpu_name'],'torch_version':report['torch_version'],'cuda_version':report['cuda_version']},'interpretation':{'purpose':'ordinary prompt control','algorithm_benefit_comparison':False,'visual_review':'PARTIAL: player, ball and dribbling restored; sustained downward composition shift'}}
put(D/'SPEC.json',spec);put(D/'INTAKE_RECEIPT.json',{'passed':True,'consumer_freeze_sha256':sha(C/'CONSUMER_FREEZE.json'),'input_sources':{rel:{'file':str(path),'sha256':sha(path)} for rel,path in copies.items()},'GPU_started':False})
x=subprocess.run([PY,str(R/'scripts/prepare.py'),'--case',name,'--ffmpeg','/opt/homebrew/bin/ffmpeg','--ffprobe','/opt/homebrew/bin/ffprobe'],capture_output=True,text=True,timeout=300);(R/'audit/PREPARE.log').write_text(x.stdout+x.stderr);assert x.returncode==0,'inspect PREPARE.log'
put(R/'audit/READY_FOR_TRACKER_BINDING.json',{'case':name,'passed':True,'input_sha256':sha(D/'INPUTS.json'),'fresh_roles':['plain'],'cached_roles':['source'],'valid_frames':105,'source_decoded_frames_match':True,'GPU_started':False,'priority':'after R111 actual release; root-coordinated MF batch'})
print(json.dumps(read(R/'audit/READY_FOR_TRACKER_BINDING.json')))
