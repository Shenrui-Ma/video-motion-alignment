"""Existing DWPose only, CPU-only, full-source pass; no scientific selection here."""
import argparse,fcntl,hashlib,json,os,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;OLD=Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 a=argparse.ArgumentParser();a.add_argument('source_id',choices=['40372','51317','51304']);args=a.parse_args();cid=args.source_id
 lock=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 b=json.loads((P/'source_selection_inputs.json').read_text());item=b['sources'][cid];v=P/'inputs'/f'{cid}_full24.mp4';out=P/'full_pose'/cid
 if sha(v)!=item['full_sha256']:raise ValueError('video binding')
 if sha(OLD/'scripts/pose_probe.py')!=b['pose_probe_sha256']:raise ValueError('pose script binding')
 out.mkdir(parents=True,exist_ok=True)
 if (out/'COMPLETE.json').exists():raise ValueError('existing complete preserved')
 env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4')
 cmd=[sys.executable,str(OLD/'scripts/pose_probe.py'),'--video',str(v),'--output-dir',str(out),'--threads','4']
 for n in [0,item['frames']//2,item['frames']-1]:cmd+=['--overlay-frame',str(n)]
 t=time.time()
 with (out/'extract.log').open('x') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
 p=out/f'{cid}_full24.pose.json';raw=json.loads(p.read_text())
 if raw['video']['sha256']!=item['full_sha256'] or raw['video']['fps']!=24 or (raw['video']['width'],raw['video']['height'])!=(1312,736) or [r['frame'] for r in raw['frames']]!=list(range(item['frames'])):raise ValueError('actual source frames/geometry')
 for k,v in b['model_provenance'].items():
  if raw['provenance'][k]!=v:raise ValueError('model/code provenance '+k)
 if raw['provenance']['script_sha256']!=b['pose_probe_sha256'] or raw['provenance']['device']!='cpu' or raw['provenance']['providers']!=['CPUExecutionProvider']:raise ValueError('CPU/frozen script')
 done={'passed':True,'source_id':cid,'pose_sha256':sha(p),'input_sha256':item['full_sha256'],'binding_sha256':sha(P/'source_selection_inputs.json'),'script_sha256':sha(Path(__file__)),'elapsed_seconds':time.time()-t,'frame_count':item['frames'],'GPU_used':False}
 (out/'COMPLETE.json').write_text(json.dumps(done,indent=2)+'\n');print(json.dumps(done),flush=True)
if __name__=='__main__':
 try:main()
 except BlockingIOError:print('CPU_LOCK_BUSY');raise SystemExit(75)
