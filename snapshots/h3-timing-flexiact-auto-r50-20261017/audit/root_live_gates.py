"""Root-only administration for the sealed R50 gates; no inference edits."""
import argparse, hashlib, json, os, runpy, subprocess, sys, time
from pathlib import Path
R=Path('/data5/researcher/h3_runs/timing_flexiact_auto_r50_20261017')
S=Path('/data5/researcher/h3_runs/timing_signed_source6980766_r53_20261017')
GPU='GPU-REDACTED'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def write(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+f'.{os.getpid()}.tmp');q.write_text(json.dumps(d,indent=2)+'\n');os.replace(q,p)
def ident(pid):
 p=Path('/proc')/str(pid)
 return {'uid':p.stat().st_uid,'start_ticks':(p/'stat').read_text().rsplit(')',1)[1].split()[19],'cmdline_sha256':sha(p/'cmdline')}
def check():
 assert sha(R/'deploy_manifest.json')=='4f1b4fbf3a30ea5baa27e9cd4feff3ac163628a61c66db14f5eb525a5c66e3f0'
 for n,v in read(R/'deploy_manifest.json')['files'].items():
  p=R/n;assert p.stat().st_size==v['bytes'] and sha(p)==v['sha256'],n
 own=set();raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True)
 for line in raw.splitlines():
  gpu,pid=[x.strip() for x in line.split(',')];assert gpu!=GPU,'target GPU occupied'
  q=Path('/proc')/pid
  if q.exists() and q.stat().st_uid==os.getuid():own.add(gpu)
 assert len(own|{GPU})<=2
 return raw

def register(pid):
 identity=ident(pid);assert identity['uid']==os.getuid()==1016
 if not Path('/proc/63582').exists():return {'peer':'R53 already absent','target':{'pid':pid,'identity':identity}}
 assert ident(63582)==dict(uid=1016,start_ticks='2625625538',cmdline_sha256='044785b36f8bea04b6e64bcebbbbf67b6bfd08a76ccd6e28f8a5841fbaf996d4')
 p=S/'configs/admission.json';before=read(p);after=read(p);rows=[]
 for x in before['permitted_compute_processes']:
  if (Path('/proc')/str(x['pid'])).exists():
   assert ident(x['pid'])==x['identity'],'peerPID reused'
   if x['pid']!=pid:rows.append(x)
 rows.append({'pid':pid,'identity':identity});after['permitted_compute_processes']=rows
 evidence={'before':before,'after':after,'unix':time.time(),'target_pid':pid}
 write(S/'audit'/f'root_R50_peer_{time.time_ns()}.json',evidence);write(p,after)
 return evidence

def main(phase):
 os.environ.update(CUDA_VISIBLE_DEVICES=GPU,OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',TMPDIR=str(R/'temp'),TMP=str(R/'temp'),TEMP=str(R/'temp'),PYTHONDONTWRITEBYTECODE='1')
 sys.path[:0]=[str(R/'scripts'),'/data5/researcher/h3_runs/short_event_pilot_20261013/runtime_deps']
 before=check()
 if phase=='kernel':
  target=R/'scripts/gpu_dynamic_union_smoke.py';out=R/'audit/gpu_dynamic_union_gate.json';assert not out.exists()
  peer=register(os.getpid());write(R/'audit/root_kernel_owner.json',{'pid':os.getpid(),'identity':ident(os.getpid()),'pre_compute':before,'peer_registration':peer})
  sys.argv=[str(target),'--root-admitted','--output',str(out)];runpy.run_path(str(target),run_name='__main__')
 elif phase=='decoder':
  target=R/'scripts/known_endpoint_158_gate.py';out=R/'audit/known_endpoint_158_gate.json';assert not out.exists()
  write(R/'audit/root_decoder_parent.json',{'pid':os.getpid(),'identity':ident(os.getpid()),'pre_compute':before})
  sys.argv=[str(target),'--root-admitted','--output',str(out)];runpy.run_path(str(target),run_name='__main__')
 elif phase=='decoder_go':
  d=R/'audit/observations/known_endpoint_158';ready=read(d/'decoder_ready.json');identity=ready['identity'];pid=identity['pid']
  actual=ident(pid);assert actual['uid']==identity['uid'] and actual['start_ticks']==str(identity['start_ticks'])
  assert str(R/'scripts/known_endpoint_decode_bridge.py') in (Path('/proc')/str(pid)/'cmdline').read_bytes().replace(b'\0',b' ').decode()
  assert ready['gpu_uuid']==GPU and not (d/'decoder_go.json').exists()
  peer=register(pid);write(R/'audit/root_decoder_peer.json',peer)
  write(d/'decoder_go.json',{'root_approved':True,'identity':identity,'gpu_uuid':GPU});print(json.dumps({'approved_decoder_pid':pid}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['kernel','decoder','decoder_go']);main(p.parse_args().phase)
