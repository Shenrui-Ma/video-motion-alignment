"""Bind the already prepared R106 scientific inputs to the approved serial short-MF gate."""
from pathlib import Path
import hashlib,json,shutil,ast,subprocess
H=Path(__file__).resolve().parent;old=H/'r106_short_0252_solvers';template=H/'r111_long_0174_spatial_capacity4';r=H/'r106_short_0252_solvers_capacity4';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text());PYTHON='/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python'
seal=read(old/'SEAL.json')
for n,h in seal['files'].items():assert sha(old/n)==h,n
assert not r.exists();shutil.copytree(old,r);(r/'SEAL.json').rename(r/'audit/PREVIOUS_SEAL.json')
for rel in ['scripts/common.py','scripts/mf_capacity.py','audit/check_raw_capacity.py','audit/check_package.py']:
 shutil.copy2(template/rel,r/rel)
cfg=read(r/'configs/RUNTIME.json');cfg['remote_root']+='_capacity4';(r/'configs/RUNTIME.json').write_text(json.dumps(cfg,indent=2)+'\n')
t=(template/'audit/run_authorized.py').read_text();t=t.replace('r111_long_0174_spatial','r106_short_0252_solvers').replace('[1,145,100,2]','[1,98,100,2]').replace("['valid_frames']==145","['valid_frames']==98").replace('997526944c6ba45f295ad4564d35d3a6cfacd23cba82d08fd1dfc89f44351694','6224d26910a70a346bd8150fce8e81c846795e598a3dce744eeae30e9e6706a3')
# Restore the exact R111 producer release barrier after the case-name substitution.
t=t.replace("timing_ive_long0174_spatial_marginal_r111_20261019","timing_ive_long0174_spatial_marginal_r111_20261019")
t=t.replace("for role in ['spatial']:\n  ROLE=role", "for role in ['source', 'euler', 'res_multistep']:\n  ROLE=role")
t=t.replace("for role in ['spatial']:","for role in ['euler', 'res_multistep']:").replace("for k in ['spatial']","for k in ['euler', 'res_multistep']").replace("'source_cache_reused':True","'source_cache_reused':False")
t=t.replace('one fresh spatial tracker with immutable cached source','three sequential fresh source/Euler/res_multistep trackers')
t=t.replace("before=read(OUT/'PREFLIGHT.json')['cgroup']['snapshot'];after=read(OUT/'RESOURCE_OBSERVATIONS.json')['final_snapshot']", "before=read(BATCH/'OOM_BASE.json');after=cg.snapshot()")
t=t.replace("OUT.mkdir(parents=True,exist_ok=False);os.environ", "OUT.mkdir(parents=True,exist_ok=False);require_no_new_oom();os.environ")
t=t.replace("BATCH.mkdir(parents=True,exist_ok=False)\n", "BATCH.mkdir(parents=True,exist_ok=False)\n save(BATCH/'OOM_BASE.json',cg.snapshot())\n")
ast.parse(t);(r/'audit/run_authorized.py').write_text(t)
revision={'root_authorization':'REDACTED_CREDENTIAL','fresh_trackers':['source','euler','res_multistep'],'source_previous_seal_sha256':sha(old/'SEAL.json'),'scientific_inputs_sha256':sha(r/'cases/r106_short_0252_solvers/INPUTS.json'),'runtime_unchanged':True}
(r/'audit/CAPACITY_REVISION.json').write_text(json.dumps(revision,indent=2)+'\n')
for n,h in seal['files'].items():
 if n.startswith(('cases/','runtime/')):assert sha(r/n)==h,n
res=json.loads(subprocess.check_output([PYTHON,str(r/'audit/check_raw_capacity.py'),str(r)],text=True));(r/'audit/CAPACITY_BOUNDARY_CHECK.json').write_text(json.dumps(res,indent=2)+'\n')
files={str(p.relative_to(r)):sha(p) for p in sorted(r.rglob('*')) if p.is_file() and '__pycache__' not in p.parts};(r/'SEAL.json').write_text(json.dumps({'schema':'ive-mf-raw-capacity-sequential-v4','files':files},indent=2)+'\n')
subprocess.run([PYTHON,str(r/'audit/check_package.py'),str(r)],check=True);print(json.dumps({'path':str(r),'seal':sha(r/'SEAL.json'),'CPU_tests':res['test_count'],'GPU_started':False}))
