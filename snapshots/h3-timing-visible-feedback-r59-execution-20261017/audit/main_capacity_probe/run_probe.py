"""Explicit root-executed GPU probe; always reaps its exact own service group."""
import argparse,importlib.util,json,os,signal,socket,subprocess,sys,time,urllib.request,urllib.error
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'scripts'))
import process_identity
s=importlib.util.spec_from_file_location('probe_contract',HERE/'H3MainCapacityProbe/contract.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
def identity(pid):
 return process_identity.hashed_record(process_identity.snapshot(pid),include_pid=True)

def compute():
 text=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_gpu_memory','--format=csv,noheader,nounits'],text=True,timeout=10)
 rows=[]
 for line in text.splitlines():
  if line.strip():
   u,p,m=[x.strip() for x in line.split(',')];rows.append({'gpu_uuid':u,'pid':int(p),'used_memory_MiB':m})
 return rows

def request(port,route,data=None):
 req=urllib.request.Request('http://127.0.0.1:'+str(port)+route,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)

def command(root,cfg):
 r=cfg['runtime']
 return [r['python'],'-u',str(root/'scripts/capacity_entry.py'),str(root/'scripts/compatibility_bootstrap.py'),str(Path(r['core'])/'main.py'),'--listen','127.0.0.1','--port',str(cfg['port']),'--base-directory',str(root),'--models-directory',r['models'],'--disable-auto-launch','--disable-dynamic-vram','--disable-cuda-malloc','--use-pytorch-cross-attention','--enable-triton-backend','--preview-method','none','--disable-all-custom-nodes','--whitelist-custom-nodes','ComfyUI-KJNodes','H3EventAudit','H3PairAudit','H3TemporalRouter','H3X0Readout','H3AutomaticWindowRouter','H3MainCapacityProbe','--input-directory',str(root/'input'),'--output-directory',str(root/'output'),'--temp-directory',str(root/'temp'),'--user-directory',str(root/'user'),'--database-url','sqlite:///'+str(root/'probe.db'),'--reserve-vram','8']

def main():
 p=argparse.ArgumentParser();p.add_argument('--run-root',type=Path,required=True);p.add_argument('--root-admitted',action='store_true');p.add_argument('--bootstrap-free-mib',type=int,default=45000);a=p.parse_args();c.require(a.root_admitted,'root-admitted flag required');root=a.run_root.resolve();cfg=c.read(root/'configs/probe.json');seal=c.read(root/'configs/package.json')
 c.require(str(root)==cfg['run_root'] and c.sha(root/'configs/probe.json')==seal['probe_sha256'],'probe config changed')
 for path,digest in cfg['bound_files'].items():c.require(c.sha(path)==digest,'bound source/input changed: '+path)
 gpu=cfg['runtime']['gpu_uuid'];rows=compute();owned=set()
 for row in rows:
  try:uid=(Path('/proc')/str(row['pid'])).stat().st_uid
  except FileNotFoundError:raise RuntimeError('GPU owner disappeared; rerun admission')
  if uid==os.getuid():owned.add(row['gpu_uuid'])
 c.require(len(owned|{gpu})<=2,'own UID would exceed two GPU cards')
 text=subprocess.check_output(['nvidia-smi','--id='+gpu,'--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'],text=True,timeout=10);values=[v.strip() for v in text.strip().split(',')]
 c.require(len(values)==2 and values[0]==gpu and int(values[1])>=a.bootstrap_free_mib>0,'insufficient bootstrap free memory')
 c.write_new(root/'audit/admission.json',{'status':'bootstrap_only_not_capacity_certificate','required_free_MiB':a.bootstrap_free_mib,'observed_gpu_csv':text,'compute':rows,'own_GPU_cards':sorted(owned),'planned_gpu':gpu})
 with socket.socket() as sock:sock.bind(('127.0.0.1',cfg['port']))
 env=dict(os.environ,H3_CAPACITY_PARENT=json.dumps(identity(os.getpid())),CUDA_VISIBLE_DEVICES=gpu,PYTHONPATH=os.pathsep.join([str(root/'scripts'),cfg['runtime']['dependencies'],str(Path(cfg['producer_root'])/'extensions')]),OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',TOKENIZERS_PARALLELISM='false',PYTHONUNBUFFERED='1',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(root/'temp'),TMP=str(root/'temp'),TEMP=str(root/'temp'))
 def interrupted(signum,frame):raise SystemExit(128+signum)
 signal.signal(signal.SIGTERM,interrupted)
 proc=entry=None;history=None;verdict={'inference_complete':False,'capacity_passed':False};started=time.monotonic()
 try:
  with (root/'logs/service.log').open('xb') as log:
   proc=subprocess.Popen(command(root,cfg),cwd=cfg['runtime']['core'],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
  entry=process_identity.hashed_record(process_identity.bind_or_reap(proc,command(root,cfg)),include_pid=True)
  c.require(entry is not None and entry['uid']==os.getuid(),'cannot bind own service generation');c.write_new(root/'audit/service_identity.json',{'identity':entry,'command':command(root,cfg)})
  while time.monotonic()-started<600:
   c.require(proc.poll() is None and identity(proc.pid)==entry,'service exited or changed')
   try:request(cfg['port'],'/system_stats');break
   except (urllib.error.URLError,TimeoutError):time.sleep(1)
  else:raise TimeoutError('service startup600s')
  queued=request(cfg['port'],'/prompt',{'prompt':c.read(root/'configs/graph.json'),'client_id':'capacity-probe'});c.write_new(root/'audit/queue.json',queued);pid=queued['prompt_id'];deadline=time.monotonic()+1800
  while time.monotonic()<deadline:
   c.require(proc.poll() is None and identity(proc.pid)==entry,'own service exited or changed')
   with (root/'audit/resources.jsonl').open('a') as f:f.write(json.dumps({'unix':time.time(),'compute':compute()})+'\n')
   history=request(cfg['port'],'/history/'+pid).get(pid)
   if history:break
   time.sleep(1)
  if not history:raise TimeoutError('capacity graph1800s')
  c.write_new(root/'audit/history.json',history)
  report=c.read(root/'audit/capacity_complete.json');c.successful_capacity(report)
  messages=history.get('status',{}).get('messages',[])
  c.require(any(tag=='execution_error' and 'CapacityProbeComplete' in str(row.get('exception_type','')) for tag,row in messages),'expected controlled graph stop missing')
  verdict.update(capacity_passed=True,graph_status='expected_controlled_stop',report_sha256=c.sha(root/'audit/capacity_complete.json'))
 except BaseException as error:verdict['error']=type(error).__name__+': '+str(error);raise
 finally:
  primary=sys.exc_info()[1]
  try:
   if proc is not None:
    if entry is not None and proc.poll() is None and identity(proc.pid)==entry:os.killpg(proc.pid,signal.SIGTERM)
    try:proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
     if entry is not None and identity(proc.pid)==entry:os.killpg(proc.pid,signal.SIGKILL)
     proc.wait(timeout=10)
    deadline=time.monotonic()+15;tail=[]
    while time.monotonic()<deadline:
     now=identity(proc.pid)
     tail=[] if now is not None and now!=entry else [r for r in compute() if r['pid']==proc.pid]
     if not tail:break
     time.sleep(.25)
    verdict['cleanup']={'original_generation_absent':identity(proc.pid)!=entry,'own_compute_absent':not tail,'child_returncode':proc.returncode,'remaining_pid_rows':tail}
    c.require(verdict['cleanup']['original_generation_absent'] and verdict['cleanup']['own_compute_absent'],'own service cleanup incomplete')
  except BaseException as cleanup:
   verdict['cleanup_error']=repr(cleanup)
   if primary is None:
    verdict['wall_seconds']=time.monotonic()-started;c.write_new(root/'audit/run_result.json',verdict)
    raise
  verdict['wall_seconds']=time.monotonic()-started;c.write_new(root/'audit/run_result.json',verdict)
 print(json.dumps(verdict))
if __name__=='__main__':main()
