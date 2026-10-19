"""One root-authorized short tracker with raw memory headroom and observed PSI."""
from pathlib import Path
import hashlib,json,shutil,ast,subprocess,os,tarfile
H=Path(__file__).resolve().parent;PY='/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text())
name='r111_long_0174_spatial';old=H/(name+'_capacity3');r=H/(name+'_capacity4');assert not r.exists()
# Restore sealed administrative snapshot; retain the newer deployment receipt separately.
p=old/'audit/TARGET_CPU_CHECK.json';seal=read(old/'SEAL.json')
if sha(p)!=seal['files']['audit/TARGET_CPU_CHECK.json']:
 shutil.copy2(p,old/'audit/ACTUAL_TARGET_CPU_CHECK_CAPACITY3.json')
 with tarfile.open(H/(old.name+'_passive.tar.gz')) as t:p.write_bytes(t.extractfile('audit/TARGET_CPU_CHECK.json').read())
for n,h in seal['files'].items():assert sha(old/n)==h,n
shutil.copytree(old,r,ignore=shutil.ignore_patterns('actual_host41','CAPACITY_RESULTS.tar.gz'))
(r/'SEAL.json').rename(r/'audit/CAPACITY3_SEAL.json')
module='''"""Single short MF tracker; raw headroom admission, PSI observed, no limit changes."""
import importlib.util,math
from pathlib import Path
GIB=2**30
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('mf_cgroup_snapshot',ROOT/'audit/cgroup_memory.py');cg=importlib.util.module_from_spec(s);s.loader.exec_module(cg)
def assess(v,raw_required_gib):
 assert raw_required_gib in (8,12)
 assert v['uid']==1004 and v['host_available_bytes']>=32*GIB,'host/UID capacity'
 parent=next(r for r in v['ancestors'] if r['path']=='/user.slice')
 assert (parent['high_bytes'],parent['max_bytes'])==(100*GIB,112*GIB),'parent limits changed'
 rows=[]
 for r in v['ancestors']:
  if r.get('high_bytes') is None and r.get('max_bytes') is None:continue
  assert type(r['current_bytes']) is int and r['current_bytes']>=0,'invalid memory.current'
  if raw_required_gib==12 and r.get('high_bytes') is not None:assert r['high_bytes']-r['current_bytes']>=12*GIB,'raw high headroom'
  if r.get('max_bytes') is not None:assert r['max_bytes']-r['current_bytes']>=raw_required_gib*GIB,'raw max headroom'
  for kind in ['some','full']:
   x=r['pressure'][kind]['avg10'];assert isinstance(x,(int,float)) and math.isfinite(x) and x>=0,'invalid memory pressure'
  for key in ['oom','oom_kill']:
   assert type(r['events'].get(key)) is int and r['events'][key]>=0,'invalid OOM counter'
  rows.append({'path':r['path'],'raw_high_headroom':r['high_bytes']-r['current_bytes'] if r.get('high_bytes') is not None else None,'raw_max_headroom':r['max_bytes']-r['current_bytes'] if r.get('max_bytes') is not None else None})
 assert rows,'no finite ancestor'
 return {'passed':True,'raw_required_gib':raw_required_gib,'raw_high_initial_gib':12,'PSI_observation_only':True,'cache_credit_bytes':0,'rows':rows,'snapshot':v}
def check(raw_required_gib):return assess(cg.snapshot(),raw_required_gib)
''';ast.parse(module);(r/'scripts/mf_capacity.py').write_text(module)
p=r/'audit/run_authorized.py';t=p.read_text().replace('_capacity_attempt3','_capacity_attempt4');t=t.replace("wait_with_telemetry(child);require(child.returncode==0", "wait_with_telemetry(child);require_no_new_oom();require(child.returncode==0")
fn='''\ndef require_no_new_oom():
 before=read(OUT/'PREFLIGHT.json')['cgroup']['snapshot'];after=read(OUT/'RESOURCE_OBSERVATIONS.json')['final_snapshot'];delta=cg.delta(after,before);save(OUT/'OOM_DELTA.json',delta)
 changed={path:row for path,row in delta['paths'].items() if row['counter_reset_detected'] or any(row['events_delta'].get(k,0)>0 for k in ('oom','oom_kill','oom_group_kill'))}
 require(not changed,'new OOM/counter reset; stop subsequent submissions')
\n''';t=t.replace('\ndef run_one():',fn+'def run_one():');ast.parse(t);p.write_text(t)
p=r/'configs/RUNTIME.json';c=read(p);c['remote_root']=c['remote_root'].replace('_capacity3','_capacity4');p.write_text(json.dumps(c,indent=2)+'\n')
(r/'audit/CAPACITY_REVISION.json').write_text(json.dumps({'root_authorization':'REDACTED_CREDENTIAL','one_fresh_tracker':True,'case':name,'scientific_input_unchanged':sha(next((r/'cases').iterdir())/'INPUTS.json'),'official_numerics_unchanged':True,'cache_credit_bytes':0,'source_previous_seal_sha256':sha(old/'SEAL.json')},indent=2)+'\n')
# The boundary program is included in the seal and never imports CUDA.
tests='''import copy,sys,json
from pathlib import Path
r=Path(sys.argv[1]).resolve();sys.path.insert(0,str(r/'scripts'));from mf_capacity import assess
G=2**30;v={'uid':1004,'host_available_bytes':32*G,'ancestors':[{'path':'/user.slice','current_bytes':88*G,'high_bytes':100*G,'max_bytes':112*G,'pressure':{'some':{'avg10':99},'full':{'avg10':99}},'events':{'oom':0,'oom_kill':0}}]};out=[]
def test(name,q,n,expected):
 try:assess(q,n);passed=True
 except (AssertionError,KeyError,StopIteration):passed=False
 assert passed==expected,name;out.append(name)
def changed(path,val):
 q=copy.deepcopy(v);x=q
 for key in path[:-1]:x=x[key]
 x[path[-1]]=val;return q
row=['ancestors',0]
test('raw high exact12 PSI99 accepted',v,12,True)
test('raw high one byte short',changed(row+['current_bytes'],88*G+1),12,False)
test('host one byte short',changed(['host_available_bytes'],32*G-1),12,False)
test('UID wrong',changed(['uid'],1016),12,False)
test('parent limit changed',changed(row+['high_bytes'],101*G),12,False)
test('runtime raw8 exact high not gate',changed(row+['current_bytes'],104*G),8,True)
test('runtime raw8 short',changed(row+['current_bytes'],104*G+1),8,False)
test('nonfinite PSI',changed(row+['pressure','some','avg10'],float('nan')),12,False)
test('invalid OOM counter',changed(row+['events','oom'],-1),12,False)
q=copy.deepcopy(v);q['ancestors'].append(dict(copy.deepcopy(q['ancestors'][0]),path='/leaf',current_bytes=88*G,high_bytes=None,max_bytes=100*G));test('leaf rawmax12 exact',q,12,True);q['ancestors'][1]['current_bytes']+=1;test('leaf rawmax12 short',q,12,False)
assert 'torch' not in sys.modules;print(json.dumps({'passed':True,'test_count':len(out),'tests':out,'CUDA_started':False}))
''';(r/'audit/check_raw_capacity.py').write_text(tests)
for n,h in seal['files'].items():
 if n.startswith(('cases/','runtime/')):assert sha(r/n)==h,n
res=json.loads(subprocess.check_output([PY,str(r/'audit/check_raw_capacity.py'),str(r)],text=True));(r/'audit/CAPACITY_BOUNDARY_CHECK.json').write_text(json.dumps(res,indent=2)+'\n')
files={str(p.relative_to(r)):sha(p) for p in sorted(r.rglob('*')) if p.is_file() and '__pycache__' not in p.parts};(r/'SEAL.json').write_text(json.dumps({'schema':'ive-mf-raw-capacity-single-trial-v4','files':files},indent=2)+'\n')
subprocess.run([PY,str(r/'audit/check_package.py'),str(r)],check=True);print(json.dumps({'path':str(r),'seal':sha(r/'SEAL.json'),'tests':res['test_count'],'GPU_started':False}))
