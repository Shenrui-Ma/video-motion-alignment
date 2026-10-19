from pathlib import Path
import sys,json,os,time,fcntl
r=Path('/data3/researcher/h3_runs/timing_flexiact_forced_r84_20261018');sys.path.insert(0,str(r/'scripts'));sys.path.insert(0,str(r/'analysis/postrun'));os.environ['CUDA_VISIBLE_DEVICES']=''
import torch
torch.set_num_threads(1)
from r84_contract import registry,read,sha
from capture_checks import inspect_capture,inspect_blob,condition_files
from legacy_checks import walk_blobs,video_properties,output_file,reference_geometry_matches
lock=Path('/data3/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:print(json.dumps({'status':'CPU_BUSY','retry_code':75}));raise SystemExit(75)
started=time.monotonic();out=[]
for row in registry(r)[0].values():
 c=row['case'];old=Path(c['baseline_root']);run=c['baseline_run'];g=read(r/c['parent_graph']);grid=torch.tensor([float(x) for x in g['9']['inputs']['sigmas'].split(',')],dtype=torch.float32).tolist()
 m,files,_=inspect_capture(old/'audit/x0'/run,run,grid,c['seed'])
 shared=read(old/'audit'/(c['baseline_reference_cache_id']+'_conditioning.json'));manifest=read(old/'audit'/(run+'_conditioning.json'));assert len(condition_files(shared))==8
 seen=set();blobs=[]
 for value in walk_blobs(shared):
  if value['tensor_file'] not in seen:seen.add(value['tensor_file']);blobs.append(inspect_blob(old/'audit',value))
 router=read(old/'audit/router'/(run+'.json'));assert reference_geometry_matches(manifest,c,router['validated_layout'])
 hist=read(old/'logs'/(run+'_history.json'));video=output_file(old,hist);prop=video_properties(video)
 out.append({'source':c['source_id'],'baseline_run':run,'actual_captures':len(files),'actual_condition_blobs':len(blobs),'condition_geometry_passed':True,'actual_video':{'file':str(video),'sha256':sha(video),'properties':prop},'capture_files':files})
result={'passed':True,'GPU_initialized':torch.cuda.is_initialized(),'sources':out,'wall_seconds':time.monotonic()-started};assert not result['GPU_initialized'];(r/'audit/BASELINE_ACTUAL_CPU_CHECK.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':True,'GPU_initialized':False,'source_count':len(out),'wall_seconds':result['wall_seconds']}))
