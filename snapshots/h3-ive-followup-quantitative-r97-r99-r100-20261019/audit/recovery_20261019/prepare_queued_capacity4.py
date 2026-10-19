"""Bind an existing exact scientific package to approved serial raw-capacity MF scheduling."""
from pathlib import Path
import hashlib,json,shutil,ast,subprocess,sys,tarfile
H=Path(__file__).resolve().parent;name=sys.argv[1];old=H/name;template=H/'r106_short_0252_solvers_capacity4';r=H/(name+'_capacity4');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text());PYTHON='/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python'
seal=read(old/'SEAL.json')
for n,h in seal['files'].items():
 if sha(old/n)!=h and n=='audit/TARGET_CPU_CHECK.json':
  shutil.copy2(old/n,old/'audit/ACTUAL_TARGET_CPU_CHECK_PRESERVED.json')
  with tarfile.open(H/(old.name+'_passive.tar.gz')) as z:(old/n).write_bytes(z.extractfile(n).read())
 assert sha(old/n)==h,n
assert not r.exists();shutil.copytree(old,r,ignore=shutil.ignore_patterns('actual_host41','ACTUAL_RESULTS.tar.gz','CAPACITY_RESULTS.tar.gz'));(r/'SEAL.json').rename(r/'audit/PREVIOUS_SEAL.json')
for rel in ['scripts/common.py','scripts/mf_capacity.py','audit/check_raw_capacity.py','audit/check_package.py']:shutil.copy2(template/rel,r/rel)
cfg=read(r/'configs/RUNTIME.json');cfg['remote_root']+='_capacity4';(r/'configs/RUNTIME.json').write_text(json.dumps(cfg,indent=2)+'\n')
c=next((r/'cases').iterdir());spec=read(c/'SPEC.json');inp=read(c/'INPUTS.json');n=inp['valid_frames'];assert 0<n<=145;targets=list(spec['targets']);roles=targets if spec.get('source_cache_reuse') else ['source',*targets]
t=(template/'audit/run_authorized.py').read_text().replace('r106_short_0252_solvers',name).replace('[1,98,100,2]',f'[1,{n},100,2]').replace("['valid_frames']==98",f"['valid_frames']=={n}").replace('6224d26910a70a346bd8150fce8e81c846795e598a3dce744eeae30e9e6706a3',sha(c/'INPUTS.json')).replace("['source', 'euler', 'res_multistep']",repr(roles)).replace("['euler', 'res_multistep']",repr(targets));t=t.replace("'source_cache_reused':False","'source_cache_reused':"+repr(bool(spec.get('source_cache_reuse'))));ast.parse(t);(r/'audit/run_authorized.py').write_text(t)
rev={'root_authorization':'REDACTED_CREDENTIAL','fresh_roles':roles,'targets':targets,'source_previous_seal_sha256':sha(old/'SEAL.json'),'scientific_input_sha256':sha(c/'INPUTS.json'),'official_numerics_unchanged':True};(r/'audit/CAPACITY_REVISION.json').write_text(json.dumps(rev,indent=2)+'\n')
for rel,h in seal['files'].items():
 if rel.startswith(('cases/','runtime/')):assert sha(r/rel)==h,rel
res=json.loads(subprocess.check_output([PYTHON,str(r/'audit/check_raw_capacity.py'),str(r)],text=True));(r/'audit/CAPACITY_BOUNDARY_CHECK.json').write_text(json.dumps(res,indent=2)+'\n');files={str(p.relative_to(r)):sha(p) for p in sorted(r.rglob('*')) if p.is_file() and '__pycache__' not in p.parts};(r/'SEAL.json').write_text(json.dumps({'schema':'ive-mf-raw-capacity-sequential-v4','files':files},indent=2)+'\n');subprocess.run([PYTHON,str(r/'audit/check_package.py'),str(r)],check=True);print(json.dumps({'package':str(r),'seal':sha(r/'SEAL.json'),'roles':roles,'CPU_tests':res['test_count'],'GPU_started':False}))
