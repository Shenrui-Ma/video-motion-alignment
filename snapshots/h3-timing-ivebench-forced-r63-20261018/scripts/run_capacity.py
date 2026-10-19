"""Root launches one bounded GPU service for Native+ON capacity, then always reaps it."""
import argparse,json,os,signal,socket,subprocess,sys,time,urllib.request,urllib.error
from pathlib import Path
import process_identity,service
from r63_contract import ROOT,read,sha,require

def request(port,route,data=None):
 q=urllib.request.Request('http://127.0.0.1:'+str(port)+route,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(q,timeout=10) as response:return json.load(response)
def command(cfg):
 root=Path(cfg['run_root']);producer=cfg['producer_root'];args=[value.replace(producer,str(root)) for value in service.command()]
 args[2]=str(root/'scripts/capacity_entry.py');args[args.index('--port')+1]=str(cfg['port']);args.insert(args.index('--input-directory'),'H3CapacityProbe')
 return args

def run(root,root_admitted=False,bootstrap_free_mib=20000):
 root=Path(root);cfg=read(root/'configs/probe.json');runtime=cfg['runtime'];require(root_admitted,'root-admitted flag required')
 require(cfg['producer_root']==str(ROOT) and str(ROOT)==runtime['remote_root'] and runtime==service.RUNTIME,'exact remote/profile required')
 for path,digest in cfg['bound_files'].items():require(sha(path)==digest,'capacity dependency changed: '+path)
 rows=service.compute_processes();cards={row['gpu_uuid'] for row in rows if service.proc_uid(row['pid'])==os.getuid()}
 require(len(cards|{runtime['gpu_uuid']})<=2,'own UID would exceed two GPU cards')
 query=subprocess.check_output(['nvidia-smi','--id='+runtime['gpu_uuid'],'--query-gpu=index,uuid,memory.free,temperature.gpu','--format=csv,noheader,nounits'],text=True,timeout=10)
 v=[x.strip() for x in query.strip().split(',')];require(len(v)==4 and int(v[0])==runtime['expected_gpu_index'] and v[1]==runtime['gpu_uuid'] and int(v[2])>=bootstrap_free_mib and 0<=int(v[3])<85,'fresh GPU identity/free-memory/temperature admission failed')
 with socket.socket() as sock:sock.bind(('127.0.0.1',cfg['port']))
 parent=process_identity.hashed_record(process_identity.snapshot(os.getpid()),include_pid=True);require(parent is not None,'capacity parent identity unavailable')
 env=dict(os.environ,H3_CAPACITY_PARENT=json.dumps(parent),CUDA_VISIBLE_DEVICES=runtime['gpu_uuid'],PYTHONPATH=os.pathsep.join([str(root/'scripts'),runtime['dependencies']]),OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',TOKENIZERS_PARALLELISM='false',TMPDIR=str(root/'temp'),TMP=str(root/'temp'),TEMP=str(root/'temp'))
 proc=None;identity=None;started=time.monotonic();result={'schema':'r63-capacity-run-v1','status':'running','runtime':runtime,'admission_gpu_csv':query,'bootstrap_free_mib':bootstrap_free_mib,'own_cards_at_admission':sorted(cards)}
 def interrupted(signum,frame):raise SystemExit(128+signum)
 signal.signal(signal.SIGTERM,interrupted)
 try:
  with (root/'logs/service.log').open('xb') as log:proc=subprocess.Popen(command(cfg),cwd=runtime['core'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
  identity=process_identity.bind_or_reap(proc,command(cfg));public=process_identity.hashed_record(identity,include_pid=True)
  service.write_json(root/'audit/service.json',{'identity':public,'command':command(cfg)})
  while time.monotonic()-started<600:
   require(proc.poll() is None and process_identity.snapshot(proc.pid)==identity,'capacity service generation changed')
   try:request(cfg['port'],'/system_stats');break
   except (urllib.error.URLError,TimeoutError):time.sleep(1)
  else:raise TimeoutError('capacity startup600s')
  submitted=request(cfg['port'],'/prompt',{'prompt':read(root/'configs/graph.json'),'client_id':'r63-capacity'});service.write_json(root/'audit/submission.json',submitted)
  require('prompt_id' in submitted,'capacity graph submission rejected')
  end=time.monotonic()+7200;history=None
  while time.monotonic()<end:
   require(proc.poll() is None and process_identity.snapshot(proc.pid)==identity,'capacity service generation changed')
   sample={'unix':time.time()}
   try:sample['compute']=service.compute_processes()
   except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:sample.update(compute=None,error=repr(error))
   with (root/'audit/resources.jsonl').open('a') as f:f.write(json.dumps(sample)+'\n')
   history=request(cfg['port'],'/history/'+submitted['prompt_id']).get(submitted['prompt_id'])
   if history:break
   time.sleep(1)
  require(history is not None,'capacity graph exceeded7200s');service.write_json(root/'audit/history.json',history)
  report=read(root/'audit/capacity_complete.json')
  require(report['status']=='pass' and report['model_forward_calls']==2 and report['Euler_updates']==0,'capacity report failed')
  require(any(tag=='execution_error' and 'CapacityProbeComplete' in str(value.get('exception_type')) for tag,value in history['status']['messages']),'expected capacity controlled stop missing')
  result.update(status='pass',report_sha256=sha(root/'audit/capacity_complete.json'))
 except BaseException as error:result.update(status='failed',error=repr(error));raise
 finally:
  primary=sys.exc_info()[1]
  try:
   if proc is not None:
    if proc.poll() is None and process_identity.snapshot(proc.pid)==identity:os.killpg(proc.pid,signal.SIGTERM)
    try:proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
     if process_identity.snapshot(proc.pid)==identity:os.killpg(proc.pid,signal.SIGKILL)
     proc.wait(timeout=10)
    end=time.monotonic()+20;remaining=[]
    while time.monotonic()<end:
     remaining=[row for row in service.compute_processes() if row['pid']==proc.pid]
     if not remaining:break
     time.sleep(.25)
    result['cleanup']={'original_process_exited':proc.poll() is not None,'own_compute_absent':not remaining,'returncode':proc.returncode}
    require(result['cleanup']['original_process_exited'] and result['cleanup']['own_compute_absent'],'capacity cleanup incomplete')
  except BaseException as cleanup:
   result['cleanup_error']=repr(cleanup)
   if primary is None:
    result['wall_seconds']=time.monotonic()-started;service.write_json(root/'audit/run_result.json',result);raise
  result['wall_seconds']=time.monotonic()-started;service.write_json(root/'audit/run_result.json',result)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--probe-root',type=Path,required=True);p.add_argument('--root-admitted',action='store_true');p.add_argument('--bootstrap-free-mib',type=int,default=20000);a=p.parse_args();print(json.dumps(run(a.probe_root,a.root_admitted,a.bootstrap_free_mib),indent=2))
