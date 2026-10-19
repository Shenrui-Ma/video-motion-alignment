"""Prepare official MF for an actually reviewed ordinary-only result; no method comparison."""
from pathlib import Path
import json,hashlib,subprocess,shutil
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[1];P=BASE.parent
C=P/'h3-ive-task-repair-metrics-r102-20261019';source='short_0126';case='r102_short_0126_native';R=HERE/case
PY='/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
assert not R.exists();subprocess.run([PY,'-c','import sys;sys.path.insert(0,'+repr(str(C/'scripts'))+');import common;common.validate_static();common.verify_intake("short_0126")'],check=True,cwd=C,timeout=120)
manifest=C/'prepared/short_0126/native/MF_INPUTS.json';assert sha(manifest)=='dda812b0667b6a638c3c0434753acfff197d22021ec488784027333081b78ad7'
m=read(manifest);dest=C/'incoming'/source;assert sha(dest/'COLLECTION.json')=='bd9fe6dff9aeb24ed9248e920d7620255234213d5e886b438e422526164502c8';collection=read(dest/'COLLECTION.json')
for name,digest in collection['files'].items():assert sha(dest/name)==digest
row=next(x for x in read(C/'configs/contract.json')['sources'] if x['source_id']==source);gatefile=dest/'NATIVE_RUNTIME_GATE.json';gate=read(gatefile);assert gate['passed'] and all(gate['checks'].values()) and set(gate['runs'])=={'native'}
R.mkdir()
for folder in ('runtime','scripts','configs'):shutil.copytree(BASE/folder,R/folder)
(R/'audit').mkdir();D=R/'cases'/case;(D/'inputs').mkdir(parents=True)
full=C/row['source']['file'];original=Path(row['original_media']['file']);provenance=C/row['provenance']['file'];history=dest/'native_history.json'
copies={'source_full.mp4':full,'source_original.mp4':original,'source_provenance.json':provenance,'NATIVE_RUNTIME_GATE.json':gatefile,'native.mp4':dest/'native.mp4','native_history.json':history,'COLLECTION.json':dest/'COLLECTION.json','MF_INPUTS.json':manifest,'ACTUAL_VISUAL_REVIEW.json':C/'audit/root_native_review/short_0126/REVIEW.json'}
for name,path in copies.items():shutil.copy2(path,D/'inputs'/name)
runtime=read(R/'configs/RUNTIME.json');runtime['remote_root']=f'/data4/researcher/h3_runs/ive_recovery_{case}_20261019';runtime['GPU_execution_status']='CPU_READY_SECONDARY_TO_PAIRED_SCORES';put(R/'configs/RUNTIME.json',runtime)
spec={'case_id':case,'source_id':source,'valid_frames':109,'total_frames':124,'fps':24,'crop_xywh':[16,8,1280,720],'gate':{'file':'inputs/NATIVE_RUNTIME_GATE.json','sha256':sha(gatefile),'schema':gate['schema'],'valid_frame_keys':['runs','native','valid_frames'],'crop_keys':['runs','native','evaluation_crop_xywh']},'source':{'full_file':'inputs/source_full.mp4','full_sha256':sha(full),'original_file':'inputs/source_original.mp4','original_sha256':sha(original),'provenance_file':'inputs/source_provenance.json','provenance_sha256':sha(provenance)},'targets':{'native':{'full_file':'inputs/native.mp4','full_sha256':sha(dest/'native.mp4'),'history_file':'inputs/native_history.json','history_sha256':sha(history),'run_id':row['run_id'],'gate_video_keys':['runs','native','video'],'gate_run_keys':['runs','native','run_id'],'method_label':'ordinary edit; cat addition task passed'}},'interpretation':{'basic_edit_task':'PASS: cat added beside man, original scene and overhead stretch retained; timing already close','guidance_run':'SKIPPED','algorithm_benefit_comparison':False}}
put(D/'SPEC.json',spec);put(D/'INTAKE_RECEIPT.json',{'passed':True,'input_manifest_sha256':sha(manifest),'input_sources':{name:{'file':str(path),'sha256':sha(path)} for name,path in copies.items()},'consumer_freeze_sha256':sha(C/'CONSUMER_FREEZE.json'),'GPU_started':False})
q=subprocess.run([PY,str(R/'scripts/prepare.py'),'--case',case,'--ffmpeg','/opt/homebrew/bin/ffmpeg','--ffprobe','/opt/homebrew/bin/ffprobe'],capture_output=True,text=True,timeout=300);(R/'audit/PREPARE.log').write_text(q.stdout+q.stderr);assert q.returncode==0
put(R/'audit/READY_FOR_TRACKER_BINDING.json',{'case':case,'passed':True,'input_sha256':sha(D/'INPUTS.json'),'roles':['source','native'],'valid_frames':109,'GPU_started':False,'scope':'Auxiliary secondary-object addition; task passed, guidance skipped, no method comparison','priority':'after main paired metrics'})
print(json.dumps(read(R/'audit/READY_FOR_TRACKER_BINDING.json')))
