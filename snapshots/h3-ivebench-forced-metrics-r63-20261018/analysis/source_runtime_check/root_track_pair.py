"""Root-only sequential actual tracking of the completed R63 pair on GPU0."""
import hashlib,json,os,subprocess,time
from pathlib import Path
ROOT=Path('/data5/researcher/h3_runs/ivebench_forced_metrics_r63_20261018')
OUT=ROOT/'analysis/source_runtime_check/root_execution'
GPU='GPU-REDACTED'
def read(p):return json.loads(p.read_text())
def write(p,d):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
def identity(pid):
 p=Path('/proc')/str(pid)
 return {'pid':pid,'uid':p.stat().st_uid,'start_ticks':p.joinpath('stat').read_text().rsplit(')',1)[1].split()[19],'cmdline_sha256':hashlib.sha256(p.joinpath('cmdline').read_bytes()).hexdigest()}
def check_resource():
 r=subprocess.check_output(['nvidia-smi','--id='+GPU,'--query-gpu=uuid,memory.free,temperature.gpu','--format=csv,noheader,nounits'],text=True).strip().split(',')
 assert r[0].strip()==GPU and float(r[1])>=16384 and 0<=float(r[2])<85
 rows=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid','--format=csv,noheader,nounits'],text=True)
 owned=set()
 for l in rows.splitlines():
  pid,gpu=map(str.strip,l.split(','));p=Path('/proc')/pid
  assert p.exists()
  if p.stat().st_uid==os.getuid():owned.add(gpu)
 assert len(owned|{GPU})<=2
 return {'unix':time.time(),'gpu':r,'own_gpu_uuids':sorted(owned)}
def main():
 OUT.mkdir(exist_ok=True)
 jobs=read(ROOT/'analysis/source_runtime_check/ROOT_CURRENT_PAIR.json')['jobs'];done=[]
 for name in ['fresh_source','native','forced']:
  row=jobs[name];argv=row['argv'];old=argv[1].split('=',1)[1]
  argv=[a.replace(old,GPU) for a in argv]
  control=Path(argv[argv.index('--control')+1]);report=Path(row['report'])
  assert not control.exists() and not report.exists(), 'Keep previous attempts immutable'
  snap=check_resource()
  with (OUT/(name+'.log')).open('xb') as log:
   child=subprocess.Popen(argv,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
  deadline=time.monotonic()+120
  while not (control/'ready.json').exists():
   assert child.poll() is None and time.monotonic()<deadline
   time.sleep(.2)
  ready=read(control/'ready.json');assert ready['identity']==identity(child.pid)
  assert ready['gpu_uuid']==GPU and ready['CUDA_started'] is False
  check_resource();write(OUT/(name+'_ROOT_ADMITTED.json'),{'ready':ready,'resource':snap})
  write(control/'go.json',ready)
  assert child.wait(timeout=900)==0
  result=read(report);assert result['tracking_forwards']>0
  assert not Path('/proc',str(child.pid)).exists()
  done.append({'method':name,'pid':child.pid,'report':str(report),'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest()})
  write(OUT/'PROGRESS.json',{'completed':done});print(json.dumps(done[-1]),flush=True)
 write(OUT/'COMPLETE.json',{'passed':True,'completed':done,'unix':time.time()})
if __name__=='__main__':
 try:main()
 except BaseException as e:
  OUT.mkdir(exist_ok=True);write(OUT/'FAILURE.json',{'error':repr(e),'unix':time.time()});raise
