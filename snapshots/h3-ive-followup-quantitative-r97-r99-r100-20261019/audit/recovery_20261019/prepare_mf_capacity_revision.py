"""Copy sealed MF inputs and revise only resource admission for short trackers."""
from pathlib import Path
import argparse, hashlib, json, shutil, ast, subprocess

HERE=Path(__file__).resolve().parent
PY='/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python'
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')

MODULE='''"""Short MF admission; does not alter tracking, reclaim memory, or change limits."""
import importlib.util
from pathlib import Path
GIB=2**30
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('mf_cgroup_snapshot',ROOT/'audit/cgroup_memory.py')
cg=importlib.util.module_from_spec(s);s.loader.exec_module(cg)
def assess(v,raw_required_gib):
 assert raw_required_gib in (8,12)
 assert v['uid']==1004 and v['host_available_bytes']>=32*GIB,'host/UID capacity'
 parent=next(r for r in v['ancestors'] if r['path']=='/user.slice')
 assert (parent['high_bytes'],parent['max_bytes'])==(100*GIB,112*GIB),'parent limits changed'
 rows=[]
 for r in v['ancestors']:
  if r.get('high_bytes') is None and r.get('max_bytes') is None:continue
  stat=r['stat']
  for k in ['file','shmem','active_file','inactive_file','file_mapped','file_dirty','file_writeback']:
   assert type(stat.get(k)) is int and stat[k]>=0,'invalid stat '+k
  disk=min(max(0,stat['file']-stat['shmem']),stat['active_file']+stat['inactive_file'])
  clean=max(0,disk-stat['file_mapped']-stat['file_dirty']-stat['file_writeback'])
  credit=min(r['current_bytes'],max(0,clean-6*GIB))
  adjusted=r['current_bytes']-credit
  if r.get('high_bytes') is not None:assert r['high_bytes']-adjusted>=12*GIB,'adjusted high headroom'
  if r.get('max_bytes') is not None:assert r['max_bytes']-r['current_bytes']>=raw_required_gib*GIB,'raw max headroom'
  for kind in ['some','full']:
   x=r['pressure'][kind]['avg10'];assert isinstance(x,(int,float)) and 0<=x<=5,'startup memory pressure'
  rows.append({'path':r['path'],'clean_unmapped':clean,'credited':credit,'adjusted_current':adjusted})
 assert rows,'no finite ancestor'
 return {'passed':True,'raw_required_gib':raw_required_gib,'adjusted_high_required_gib':12,'retained_cache_gib':6,'rows':rows,'snapshot':v}
def check(raw_required_gib):return assess(cg.snapshot(),raw_required_gib)
'''

def main(source):
 source=source.resolve(); oldseal=read(source/'SEAL.json')
 for f,h in oldseal['files'].items():assert sha(source/f)==h,f
 case=next((source/'cases').iterdir());m=read(case/'INPUTS.json');assert m['valid_frames']<=145
 name=case.name;dest=HERE/(name+'_capacity2');assert not dest.exists()
 shutil.copytree(source,dest,ignore=shutil.ignore_patterns('__pycache__','actual_host41','ACTUAL_RESULTS.tar.gz'))
 for rel,digest in read(source/'configs/RUNTIME_INHERITANCE.json')['files'].items():
  src=source/'runtime'/rel;out=dest/'runtime'/rel;assert sha(src)==digest
  if not out.exists():out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,out)
 (dest/'SEAL.json').rename(dest/'audit/ORIGINAL_SEAL.json')
 for x in list((dest/'audit').glob('actual_*')):shutil.rmtree(x) if x.is_dir() else x.unlink()
 (dest/'scripts/mf_capacity.py').write_text(MODULE)
 common=dest/'scripts/common.py';text=common.read_text();start=text.index(" cg=Path('/sys/fs/cgroup/user.slice');");end=text.index('\n return ',start)
 text=text[:start]+" from mf_capacity import check as check_mf_capacity\n c=check_mf_capacity(8)"+text[end:];ast.parse(text);common.write_text(text)
 wrapper=dest/'audit/run_authorized.py';text=wrapper.read_text()
 old="owner=owner_check();headroom=cg.snapshot();require(headroom['effective_headroom_bytes']>=12*1024**3,'effective preload cgroup headroom below12GiB');g=resource_check(GPU)"
 assert old in text;text=text.replace(old,"owner=owner_check();from mf_capacity import check as check_mf_capacity;headroom=check_mf_capacity(12);g=resource_check(GPU)")
 text=text.replace("audit/actual_"+name+"_attempt1","audit/actual_"+name+"_capacity_attempt2")
 old="require(child.wait(timeout=600)==0,'tracker returned failure');d="
 new="wait_with_telemetry(child);require(child.returncode==0,'tracker returned failure');d="
 assert old in text;text=text.replace(old,new)
 fn='''\ndef wait_with_telemetry(child):
 samples=[];deadline=time.monotonic()+600
 while child.poll() is None:
  require(time.monotonic()<deadline,'tracker deadline')
  row={'unix':time.time()}
  try:
   row['cgroup']=cg.snapshot();status=Path('/proc/'+str(child.pid)+'/status').read_text();row['process_memory']={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in status.splitlines() if line.startswith(('VmRSS:','VmHWM:','RssAnon:','RssFile:','RssShmem:'))}
  except (OSError,ValueError) as error:row['error']=repr(error)
  samples.append(row);time.sleep(.25)
 child.wait();save(OUT/'RESOURCE_OBSERVATIONS.json',{'samples':samples,'returncode':child.returncode})
\n'''
 text=text.replace('\ndef run_one():',fn+'def run_one():');ast.parse(text);wrapper.write_text(text)
 check=dest/'audit/check_package.py';text=check.read_text().replace("'>=12*1024**3' in w and 'timeout=600' in w", "'check_mf_capacity(12)' in w and '+600' in w")
 check.write_text(text)
 cfg=read(dest/'configs/RUNTIME.json');cfg['remote_root']+='_capacity2';cfg['GPU_execution_status']='CPU_CAPACITY_REVISION_ROOT_AUTHORIZED';put(dest/'configs/RUNTIME.json',cfg)
 put(dest/'audit/CAPACITY_REVISION.json',{'original_package':str(source),'original_seal_sha256':sha(source/'SEAL.json'),'input_sha256_unchanged':sha(case/'INPUTS.json'),'case':name,'maximum_frames':145,'one_tracker_at_a_time':True,'official_numerical_runtime_unchanged':True,'policy':{'retained_clean_unmapped_file_cache_gib':6,'adjusted_high_headroom_gib':12,'raw_max_preload_gib':12,'raw_max_runtime_precheck_gib':8,'host_available_gib':32,'startup_psi_avg10_max':5},'historical_max_rss_kib':3051836,'authorization':'REDACTED_CREDENTIAL','old_blocked_attempt_retained':True})
 # Immutable scientific inputs and numerical implementation remain byte-identical.
 for f,h in oldseal['files'].items():
  if f.startswith(('cases/','runtime/')):assert sha(dest/f)==h,f
 files={str(p.relative_to(dest)):sha(p) for p in sorted(dest.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
 put(dest/'SEAL.json',{'schema':'ive-short-mf-capacity-v2','files':files})
 print(json.dumps({'package':str(dest),'remote':cfg['remote_root'],'seal_sha256':sha(dest/'SEAL.json'),'input_sha256':sha(dest/'cases'/name/'INPUTS.json')}))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);main(p.parse_args().source)
