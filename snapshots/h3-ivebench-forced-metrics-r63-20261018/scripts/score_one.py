"""Compute official MF as soon as a single actual target cache has finished."""
import argparse,sys
from common import *
sys.path.insert(0,str(RUNTIME/'metric_runtime'))
from score_cached_tracks import score

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',choices=PAIRS,required=True);p.add_argument('--method',choices=['native','forced'],required=True);p.add_argument('--attempt',type=int,default=1);a=p.parse_args();verify_runtime()
 with cpu_lock():
  target=ROOT/'tracks'/a.method/a.source/('attempt'+str(a.attempt));b=read(target/'R63_BINDING.json');m=ROOT/'prepared'/a.source/'METRIC_INPUTS.json'
  if b['input_manifest']!=bound(m) or b['report']!=bound(target/'REPORT.json') or not b['new_actual_tracking']:raise ValueError('new actual target tracking is unbound')
  result=score(ROOT/'tracks/source'/a.source,target)
  if result['cuda_initialized']:raise ValueError('CPU score initialized CUDA')
  result.update(fixed_denominator=5,runtime_freeze_sha256=sha(ROOT/'RUNTIME_FREEZE.json'),actual_target_tracker=True)
  path=ROOT/'results'/a.source/(a.method+'_attempt'+str(a.attempt)+'.json');save(path,result);print(json.dumps(result))
if __name__=='__main__':
 try:main()
 except BlockingIOError:print('CPU_LOCK_BUSY');raise SystemExit(75)
