"""CPU-only source-versus-itself MF using frozen source tracks and official code."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['OMP_NUM_THREADS']='2'
import json,sys,time,math,hashlib
from pathlib import Path
m=json.loads(Path(sys.argv[1]).read_text())
sys.path.insert(0,m['runtime_metric_path'])
import torch
import score_cached_tracks as cached
from ive_mf_adapter import official_class,verify_vendor
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for p,h in m['runtime_files'].items():assert sha(p)==h,p
vendor=verify_vendor();torch.set_num_threads(2)
cls=official_class();evaluator=cls.__new__(cls)
results={};reused={}
for sid,row in m['cases'].items():
 for kind in ['report','tracks']:assert sha(row[kind]['remote_file'])==row[kind]['sha256'],(sid,kind)
 report=json.loads(Path(row['report']['remote_file']).read_text());assert report['method']=='source'
 assert report['effective_frame_count']==row['valid_frames'] and report['source_score_sha256']==row['source_score_sha256']
 cached.SELECTION_SHA=row['selection_sha256']
 r,t,v=cached.load_cache(Path(row['report']['remote_file']).parent)
 identity=(row['tracks']['sha256'],row['report']['sha256'])
 start=time.monotonic()
 if identity in reused:value=reused[identity]['score'];reuse=reused[identity]['case']
 else:value=float(evaluator._compute_similarity_from_tracks(t,v,t,v));reuse=None;reused[identity]={'score':value,'case':sid}
 assert math.isfinite(value) and not torch.cuda.is_initialized()
 results[sid]={'score':value,'valid_frames':row['valid_frames'],'fps':24,'source_score_sha256':row['source_score_sha256'],'selection_sha256':row['selection_sha256'],'source_report':row['report'],'source_tracks':row['tracks'],'evidence':row['evidence'],'reused_identical_source_case':reuse,'cpu_seconds':time.monotonic()-start}
out={'schema':'r150-official-mf-source-self-cpu-v1','passed':True,'cases':results,'metric':'IVEBench official Motion Fidelity','operation':'Identical frozen source tracks and visibility used as both arguments of unchanged official _compute_similarity_from_tracks','official_vendor':vendor,'runtime_files':m['runtime_files'],'new_tracker_calls':0,'model_loads':0,'cuda_initialized':torch.cuda.is_initialized(),'unique_source_caches':len(reused),'python':sys.executable,'torch_version':torch.__version__,'created_unix':time.time()}
Path(sys.argv[2]).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False))
