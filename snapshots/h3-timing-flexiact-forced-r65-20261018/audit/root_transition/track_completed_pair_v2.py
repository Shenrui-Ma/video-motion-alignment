"""Root-only GPU tracking of a complete, CPU-verified FlexiAct pair."""
import argparse,hashlib,json,os,subprocess,sys,time,urllib.request
from pathlib import Path
BASE=Path('/data3/researcher/h3_runs')
LANES={'r65':('timing_flexiact_forced_r65_20261018','flexiact_forced_metrics_r65_20261018','--source',201359,'3125873'), 'r66':('timing_flexiact_expanded_r66_20261018','flexiact_expanded_evaluation_r66_20261018','--key',206295,'3158017')}
def read(p):return json.loads(p.read_text())
def write(p,d):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def main():
 a=argparse.ArgumentParser();a.add_argument('--lane',choices=LANES,required=True);a.add_argument('--key',required=True);a.add_argument('--service-lane',choices=LANES);args=a.parse_args()
 folder,metric,option,_,_=LANES[args.lane];root=BASE/folder;target=BASE/metric
 owner_lane=args.service_lane or args.lane
 owner_folder,_,_,pid,ticks=LANES[owner_lane];owner_root=BASE/owner_folder
 out=root/'audit/root_tracking'/args.key;out.mkdir(parents=True,exist_ok=False)
 sys.path.insert(0,str(owner_root/'scripts'));import service
 owner=read(owner_root/'processes/service.json');assert owner['pid']==pid and owner['identity']['start_ticks']==ticks;service.assert_owned(owner)
 gate=root/'analysis/postrun'/args.key/'PAIR_RUNTIME_GATE.json';assert read(gate)['passed']
 state=read(owner_root/'logs/controller_state.json');assert state['status'] in ('awaiting_first_pair_review','resident_hold') and state['current'] is None
 queue=service.queue_at(service.PORT);assert not queue['queue_running'] and not queue['queue_pending']
 prepared=target/'prepared'/args.key/'READY.json';assert read(prepared)['passed']
 peers=[]
 for other,(_,_,_,peerpid,_) in LANES.items():
  r=BASE/LANES[other][0]; rec=read(r/'processes/service.json')
  actual=service.current_identity(rec['pid'])
  if actual is not None:
   assert actual==rec['identity'];peers.append(r)
 request=urllib.request.Request(f'http://127.0.0.1:{service.PORT}/free',data=json.dumps({'unload_models':True,'free_memory':True}).encode(),headers={'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(request,timeout=10) as response:assert response.status==200
 write(out/'CACHE_RELEASE_REQUEST.json',{'unix':time.time(),'service':owner,'queue':queue,'reason':'Temporarily unload finished inference models for official target motion tracking on the same card; owner controller is at a verified empty-queue hold.'})
 deadline=time.monotonic()+120
 while True:
  sample=subprocess.check_output(['nvidia-smi','--id='+service.GPU,'--query-gpu=uuid,memory.free,temperature.gpu','--format=csv,noheader,nounits'],text=True).strip().split(',')
  assert sample[0].strip()==service.GPU and 0<=float(sample[2])<85
  if float(sample[1])>=40960:break
  assert time.monotonic()<deadline;time.sleep(1)
 done=[]
 for method in ['native','forced']:
  result=subprocess.run(['python3',str(target/'scripts/tracking_plan.py'),option,args.key,'--method',method,'--gpu-uuid',service.GPU],cwd=target,check=True,capture_output=True,text=True,timeout=120)
  argv=json.loads(result.stdout)['argv'];control=Path(argv[argv.index('--control')+1]);output=Path(argv[argv.index('--output')+1])
  with (out/(method+'.log')).open('xb') as log:
   child=subprocess.Popen(argv,cwd=target,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
  deadline=time.monotonic()+120
  while not (control/'ready.json').exists():
   assert child.poll() is None and time.monotonic()<deadline;time.sleep(.2)
  ready=read(control/'ready.json');assert ready['pid']==child.pid and ready['identity']==service.external_identity(child.pid) and ready['gpu_uuid']==service.GPU and ready['CUDA_started'] is False
  for r in peers:
   admission=read(r/'configs/admission.json');assert child.pid not in [x['pid'] for x in admission['permitted_compute_processes']]
   admission['permitted_compute_processes'].append({'pid':child.pid,'identity':ready['identity']});write(r/'configs/admission.json',admission)
  write(control/'go.json',ready)
  assert child.wait(timeout=900)==0
  report=read(output/'REPORT.json');assert report['passed'] and report['pid']==child.pid and report['tracks_shape']==[3025,49,2] and report['nonfinite_track_values']==0
  assert hashlib.sha256((output/'tracks.pt').read_bytes()).hexdigest()==report['tracks_sha256']
  assert not Path('/proc',str(child.pid)).exists()
  for r in peers:
   admission=read(r/'configs/admission.json');admission['permitted_compute_processes']=[x for x in admission['permitted_compute_processes'] if x['pid']!=child.pid];write(r/'configs/admission.json',admission)
  done.append({'method':method,'output':str(output),'report_sha256':hashlib.sha256((output/'REPORT.json').read_bytes()).hexdigest(),'wall_seconds':report['wall_seconds'],'peak_reserved_bytes':report['peak_reserved_bytes']})
  write(out/'PROGRESS.json',{'completed':done});print(json.dumps(done[-1]),flush=True)
 write(out/'COMPLETE.json',{'passed':True,'completed':done,'unix':time.time(),'producer_gate_sha256':hashlib.sha256(gate.read_bytes()).hexdigest()})
if __name__=='__main__':main()
