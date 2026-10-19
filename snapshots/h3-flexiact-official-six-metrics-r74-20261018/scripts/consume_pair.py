"""Remote CPU phases only. Root separately schedules every tracker CUDA run."""
import argparse,os,subprocess,sys,time
os.environ['CUDA_VISIBLE_DEVICES']=''
from common import *
def complete_jobs(producer,pair):
 rows=[]
 for method in METHODS:
  p=producer/'logs'/f'r74_{pair}_seed2026101701_{method}_job.json'
  if not p.is_file():return False
  rows.append(read(p).get('status')=='success')
 return all(rows)
def run(pair,phase):
 cfg=verify_runtime();producer=Path(cfg['producer_root_host41']);require(pair in PAIR_KEYS,'unknown pair')
 require(sha(producer/'deploy_manifest.json')==cfg['producer_seal_sha256'],'actual producer seal changed')
 if phase=='status':return {'jobs_success':complete_jobs(producer,pair),'gate':(producer/'analysis/postrun'/pair/'PAIR_RUNTIME_GATE.json').is_file(),'intake':(ROOT/'incoming'/pair/'COLLECTION.json').is_file(),'prepared':(ROOT/'prepared'/pair/'READY.json').is_file(),'rendered':(ROOT/'showcase'/f'{pair}_PRESENTATION.json').is_file(),'physical':(ROOT/'scores/physical'/pair/'COMPLETE.json').is_file()}
 if phase=='verify':
  require(complete_jobs(producer,pair),'actual completed pair pending');gate=producer/'analysis/postrun'/pair/'PAIR_RUNTIME_GATE.json'
  if not gate.exists():subprocess.run([sys.executable,str(producer/'analysis/postrun/verify_pair.py'),'--pair',pair],check=True,timeout=600,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2'))
  verify_gate(read(gate),pair);return bound(gate)
 if phase=='collect':
  from collect_pair import collect
  return str(collect(producer,pair))
 if phase=='prepare':
  from prepare_pair import prepare
  return str(prepare(pair))
 if phase=='render':
  import make_triptych
  output=make_triptych.run(pair)
  subprocess.run([sys.executable,str(ROOT/'scripts/make_checkpoints.py'),'--pair',pair],check=True,timeout=180)
  return str(output)
 raise ValueError('unsupported CPU phase')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--pair',required=True,choices=PAIR_KEYS);p.add_argument('--phase',required=True,choices=['status','verify','collect','prepare','render']);a=p.parse_args()
 try:
  with cpu_lock():print(json.dumps(run(a.pair,a.phase),allow_nan=False))
 except BlockingIOError:raise SystemExit(75)
