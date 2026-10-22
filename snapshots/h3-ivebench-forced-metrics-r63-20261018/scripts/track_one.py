"""Use the original tracker, with measured-memory admission on a shared GPU."""
import argparse,os,sys,subprocess,time
from common import *
sys.path.insert(0,str(RUNTIME/'metric_runtime'))
import run_tracks
REQUIRED_FREE_BYTES=16*1024**3

def resource_check(uuid):
 if not isinstance(uuid,str) or not uuid.startswith('GPU-') or os.environ.get('CUDA_VISIBLE_DEVICES')!=uuid:raise ValueError('exact root-admitted UUID required')
 q=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10,check=True)
 rows=[];owned=set()
 for line in q.stdout.splitlines():
  if not line.strip():continue
  pid,gpu=[s.strip() for s in line.split(',')];p=Path('/proc')/pid
  if not p.exists():raise ValueError('process ownership changed during resource query')
  uid=p.stat().st_uid
  if uid==os.getuid():owned.add(gpu)
  rows.append({'pid':int(pid),'uid':uid,'gpu_uuid':gpu})
 if len(owned|{uuid})>2:raise ValueError('tracking would exceed two owned GPUs')
 q=subprocess.run(['nvidia-smi','--id='+uuid,'--query-gpu=uuid,memory.free,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10,check=True)
 lines=[r.split(',') for r in q.stdout.splitlines() if r.strip()]
 if len(lines)!=1 or len(lines[0])!=3 or lines[0][0].strip()!=uuid or q.stderr.strip():raise ValueError('GPU snapshot invalid')
 free,temp=map(float,lines[0][1:])
 if not 0<=temp<85 or free*1024**2<REQUIRED_FREE_BYTES:raise ValueError('tracker requires16GiB current free memory and healthy GPU')
 return {'observed_unix':time.time(),'gpu_uuid':uuid,'required_free_bytes':REQUIRED_FREE_BYTES,'memory_free_mib':free,'temperature_c':temp,'processes':rows,'scope':'allow foreign sharing; measured source peak10.98GB plus conservative headroom'}

def main(arguments=None):
 p=argparse.ArgumentParser();p.add_argument('--source',choices=PAIRS,required=True);p.add_argument('--method',choices=['native','forced'],required=True);p.add_argument('--gpu-uuid',required=True);p.add_argument('--attempt',type=int,default=1);p.add_argument('--check-only',action='store_true');a=p.parse_args(arguments)
 freeze=verify_runtime();manifest=ROOT/'prepared'/a.source/'METRIC_INPUTS.json'
 if a.attempt<1:raise ValueError('positive attempt required')
 output=ROOT/('preflight' if a.check_only else 'tracks')/a.method/a.source/('attempt'+str(a.attempt))
 args=argparse.Namespace(input_manifest=str(manifest),selection=str(SELECTION),pair=a.source,method=a.method,gpu_uuid=a.gpu_uuid,check_only=a.check_only,output=str(output),ffmpeg='/usr/bin/ffmpeg',ffprobe='/usr/bin/ffprobe')
 run_tracks.check_gpu=resource_check
 run_tracks.main(args)
 save(output/'R63_BINDING.json',{'runtime_freeze_sha256':freeze,'input_manifest':bound(manifest),'report':bound(output/('PREFLIGHT.json' if a.check_only else 'REPORT.json')),'administrative_gate':bound(__file__),'numerical_tracker':'unchanged official CoTracker3 offline grid10/window60','new_actual_tracking':not a.check_only})
if __name__=='__main__':main()
