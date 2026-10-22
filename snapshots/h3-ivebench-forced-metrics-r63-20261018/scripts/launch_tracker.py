"""Wait for an exact-process root go record before any tracker CUDA initialization."""
import argparse,os,sys,time,runpy
from common import *
def identity():
 p=Path('/proc')/str(os.getpid());raw=(p/'cmdline').read_bytes()
 if not raw:raise ValueError('current argv unavailable')
 return {'pid':os.getpid(),'uid':p.stat().st_uid,'start_ticks':p.joinpath('stat').read_text().rsplit(')',1)[1].split()[19],'cmdline_sha256':sha(p/'cmdline')}
def main():
 p=argparse.ArgumentParser();p.add_argument('--control',type=Path,required=True);p.add_argument('arguments',nargs=argparse.REMAINDER);a=p.parse_args();args=a.arguments[1:] if a.arguments[:1]==['--'] else a.arguments
 if '--source' not in args or '--method' not in args or '--gpu-uuid' not in args or '--check-only' in args:raise ValueError('actual source/method/GPU arguments required')
 source=args[args.index('--source')+1];method=args[args.index('--method')+1];gpu=args[args.index('--gpu-uuid')+1]
 if source not in PAIRS or method not in ('native','forced') or os.environ.get('CUDA_VISIBLE_DEVICES')!=gpu:raise ValueError('tracker identity differs')
 manifest=ROOT/'prepared'/source/'METRIC_INPUTS.json';freeze=verify_runtime();a.control.mkdir(parents=True,exist_ok=False)
 ready={'schema':'r63-mf-root-preCUDA-v1','identity':identity(),'gpu_uuid':gpu,'arguments':args,'runtime_freeze_sha256':freeze,'input_manifest':bound(manifest),'CUDA_started':False,'required_free_bytes':16*1024**3}
 save(a.control/'ready.json',ready);print(json.dumps({'ready':str(a.control/'ready.json'),'identity':ready['identity']}),flush=True)
 start=time.monotonic()
 while not (a.control/'go.json').exists():
  if time.monotonic()-start>600:raise TimeoutError('root tracker admission timed out after600 seconds')
  time.sleep(.2)
 if read(a.control/'go.json')!=ready or identity()!=ready['identity'] or verify_runtime()!=freeze or bound(manifest)!=ready['input_manifest']:raise ValueError('root approval or bound input changed')
 sys.argv=[str(ROOT/'scripts/track_one.py')]+args
 runpy.run_path(str(ROOT/'scripts/track_one.py'),run_name='__main__')
if __name__=='__main__':main()
