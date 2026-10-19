"""Freeze an actual paired IVE evaluation for the exclusive post-R107 slot; no GPU start."""
from pathlib import Path
import json,hashlib,sys,shutil
HERE=Path(__file__).resolve().parent;case=sys.argv[1];R=HERE/case
assert case in ('r102_short_0263','r107_long_0174') and R.is_dir() and not(R/'SEAL.json').exists()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
manifest=R/'cases'/case/'INPUTS.json';count=json.loads(manifest.read_text())['valid_frames'];digest=sha(manifest)
T=(HERE/'r100_short_0114/audit/run_authorized.py').read_text().replace('r100_short_0114',case).replace('099f18e9ed25ac98a5780f5eb336aa5d1f9c875267cd49e4b6de1fc6ce86c325',digest).replace('[1,105,100,2]',f'[1,{count},100,2]').replace("==105,'authorized physical domain",f"=={count},'authorized physical domain")
T=T.replace("PEER=Path('/data4/researcher/h3_runs/timing_ive_native_screen_r96_20261018')", "PEER=Path('/data4/researcher/h3_runs/timing_ive_long0174_guidance_r107_20261019')")
T=T.replace("PEER/'scripts/cgroup_memory.py'", "R/'audit/cgroup_memory.py'")
a=T.index('def owner_check():');b=T.index('def capacity():',a)
T=T[:a]+'''def owner_check():
 owner=read(PEER/'processes/service.json');require(owner['pid']==1226044 and str(owner['identity']['start_ticks'])=='15372732' and owner['identity']['uid']==1004,'R107 release barrier generation differs')
 require(process_identity.snapshot(owner['pid']) is None,'R107 process remains or PID was reused; wait')
 require(owner['pid'] not in cuda_pids(),'R107 CUDA allocation remains')
 released=read(PEER/'processes/cleanup.json')
 require(released['pid']==owner['pid'] and released['process_absent'] is True and released['own_compute_absent'] is True,'R107 exact cleanup receipt pending')
 return None

'''+T[b:]
a=T.index('def peer_change(');b=T.index('def cuda_pids()',a);T=T[:a]+T[b:]
T=T.replace(" if registered:peer_change(ready,False)", " require(not registered,'exclusive tracker never registers peer')")
T=T.replace("  if owner_check() is not None:peer_change(ready,True);registered=True", "  require(owner_check() is None,'exclusive tracker requires R107 released')")
T=T.replace("OUT/'R96_OWNER.json'", "OUT/'R107_RELEASE_BARRIER.json'")
T=T.replace("Root authorization:","Root scheduling required:")
(R/'audit/run_authorized.py').write_text(T)
source=HERE.parents[2]/'h3-timing-ive-long0174-guidance-r107-20261019/scripts/cgroup_memory.py'
source=Path('/Users/researcher/DevProjects/h3-timing-ive-long0174-guidance-r107-20261019/scripts/cgroup_memory.py')
shutil.copyfile(source,R/'audit/cgroup_memory.py')
cfg=json.loads((R/'configs/RUNTIME.json').read_text());cfg['GPU_execution_status']='CPU_READY_EXCLUSIVE_POST_R107_SLOT_ROOT_SCHEDULE';put(R/'configs/RUNTIME.json',cfg)
put(R/'audit/RECOVERY_BINDING.json',dict(case=case,valid_frames=count,input_sha256=digest,fresh_roles=['source','native','forced'],preload_cgroup_GiB=12,runtime_cgroup_GiB=8,R107_exact_release={'pid':1226044,'start_ticks':'15372732','uid':1004},same_host_same_GPU_for_all_tracks=True,requires_root_scheduling=True,GPU_started=False))
files={str(p.relative_to(R)):sha(p) for p in sorted(R.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
put(R/'SEAL.json',dict(schema='ive-post-r107-actual-pair-mf-v1',files=files));print(json.dumps(dict(case=case,seal_sha256=sha(R/'SEAL.json'),files=len(files),GPU_started=False)))
