"""Bind actual MF packages to the released R111 generation; CPU only."""
from pathlib import Path
import argparse,ast,hashlib,json,shutil,subprocess
H=Path(__file__).resolve().parent
PY='/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def bind(root):
 assert root.is_dir() and not(root/'SEAL.json').exists()
 cases=list((root/'cases').iterdir());assert len(cases)==1;c=cases[0];name=c.name
 m=read(c/'INPUTS.json');s=read(c/'SPEC.json');n=m['valid_frames'];targets=list(s['targets']);cached=bool(s.get('source_cache_reuse'));roles=targets if cached else ['source']+targets
 if cached:old=H/'r109_short_0114_plain';oldname='r109_short_0114_plain';oldcount=105
 elif len(targets)==1:old=H/'r102_short_0092_native';oldname='r102_short_0092_native';oldcount=58
 else:old=H/'r107_long_0174';oldname='r107_long_0174';oldcount=145
 oldm=old/'cases'/oldname/'INPUTS.json'
 t=(old/'audit/run_authorized.py').read_text().replace(oldname,name).replace(sha(oldm),sha(c/'INPUTS.json'))
 t=t.replace(f'[1,{oldcount},100,2]',f'[1,{n},100,2]').replace(f'=={oldcount},\'authorized physical domain',f'=={n},\'authorized physical domain')
 if cached and targets!=['plain']:
  t=t.replace("['plain']",repr(targets)).replace('one fresh plain tracker','one fresh '+targets[0]+' tracker')
 if not cached and len(targets)>1:
  t=t.replace("['source','native','forced']",repr(roles)).replace("['native','forced']",repr(targets))
 t=t.replace('timing_ive_long0174_guidance_r107_20261019','timing_ive_long0174_spatial_marginal_r111_20261019').replace('1226044','1251962').replace('15372732','15965864').replace('R107','R111')
 if len(targets)==1 and not cached:t=t.replace("'task_status':'PARTIAL'","'task_status':'PASS_AUXILIARY_SECONDARY_OBJECT_ADDITION'")
 if cached:t=t.replace("'algorithm_benefit_comparison':False", "'algorithm_benefit_comparison':"+str(targets==['spatial']))
 ast.parse(t);assert sha(c/'INPUTS.json') in t and '15965864' in t and '1251962' in t
 (root/'audit/run_authorized.py').write_text(t)
 shutil.copyfile(old/'audit/cgroup_memory.py',root/'audit/cgroup_memory.py')
 check='''"""Bounded CPU package validation; no imports initialize CUDA."""
import ast,copy,json,sys
from pathlib import Path
r=Path(sys.argv[1]).resolve();sys.path.insert(0,str(r/'scripts'));import common as c
c.verify_seal();c.verify_runtime();cases=list((r/'cases').iterdir());assert len(cases)==1
case=cases[0];s=c.read(case/'SPEC.json');m=c.read(case/'INPUTS.json');g=c.read(case/s['gate']['file']);c.validate_gate(s,g)
assert set(m['roles'])=={'source',*s['targets']}
assert c.sha(case/'SPEC.json')==m['spec_sha256'] and m['gate_sha256']==c.sha(case/s['gate']['file'])
for row in m['roles'].values():
 assert c.sha(case/row['full_file'])==row['full_sha256'] and c.sha(case/row['score_file'])==row['score_sha256']
 assert len(row['score_frame_md5'])==m['valid_frames']
def setvalue(q,path,value):
 for k in path[:-1]:q=q[k]
 q[path[-1]]=value
first=next(iter(s['targets'].values()))
for path,value in [(['passed'],False),(first['gate_video_keys']+['sha256'],'0'*64),(s['gate'].get('valid_frame_keys',['valid_frames']),-1),(first.get('gate_run_keys',['run_id']),'other')]:
 q=copy.deepcopy(g);setvalue(q,path,value)
 try:c.validate_gate(s,q)
 except ValueError:pass
 else:raise AssertionError('invalid gate accepted '+str(path))
if s.get('source_cache_reuse'):
 c.validate_reuse(s,m,c.read(case/'tracks/source/REPORT.json'),c.sha(case/'tracks/source/REPORT.json'),c.sha(case/'tracks/source/tracks.npz'))
 assert c.read(case/'SOURCE_REUSE_RECEIPT.json')['passed'] is True
w=(r/'audit/run_authorized.py').read_text();ast.parse(w)
assert c.sha(case/'INPUTS.json') in w and f'[1,{m["valid_frames"]},100,2]' in w
assert '>=12*1024**3' in w and 'timeout=600' in w and '1251962' in w and '15965864' in w
assert 'torch' not in sys.modules
print(json.dumps({'passed':True,'case':case.name,'valid_frames':m['valid_frames'],'negative_gate_checks':4,'source_cache_reuse':bool(s.get('source_cache_reuse')),'CUDA_started':False}))
'''
 ast.parse(check);(root/'audit/check_package.py').write_text(check)
 cfg=read(root/'configs/RUNTIME.json');cfg['GPU_execution_status']='CPU_READY_POST_R111_EXACT_RELEASE_SLOT';put(root/'configs/RUNTIME.json',cfg)
 put(root/'audit/RECOVERY_BINDING.json',{'case':name,'valid_frames':n,'input_sha256':sha(c/'INPUTS.json'),'fresh_roles':roles,'cached_roles':['source'] if cached else [],'R111_exact_release':{'pid':1251962,'start_ticks':'15965864','uid':1004},'preload_cgroup_GiB':12,'runtime_cgroup_GiB':8,'same_host_same_GPU_for_all_tracks':True,'requires_root_scheduling':True,'GPU_started':False})
 files={str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
 put(root/'SEAL.json',{'schema':'ive-post-r111-actual-input-mf-v1','files':files})
 x=subprocess.run([PY,str(root/'audit/check_package.py'),str(root)],capture_output=True,text=True,env={'PATH':'/usr/bin:/bin:/opt/homebrew/bin','PYTHONDONTWRITEBYTECODE':'1','CUDA_VISIBLE_DEVICES':''},timeout=120);(root/'audit/CPU_VERIFICATION.log').write_text(x.stdout+x.stderr);assert x.returncode==0,x.stderr
 print(json.dumps({'case':name,'seal_sha256':sha(root/'SEAL.json'),'files':len(files),'GPU_started':False,'CPU_validation':json.loads(x.stdout)}))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('package',type=Path);bind(a.parse_args().package.resolve())
