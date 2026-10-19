"""Bind the actual 0092 ordinary-only MF; no tracker is launched."""
from pathlib import Path
import ast, hashlib, json, shutil
H=Path(__file__).resolve().parent
case='r102_short_0092_native';r=H/case
assert r.is_dir() and not (r/'SEAL.json').exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
put=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
m=r/'cases'/case/'INPUTS.json';d=json.loads(m.read_text())
assert set(d['roles'])=={'source','native'} and d['valid_frames']==58
source=H/'r102_short_0263/audit/run_authorized.py'
t=source.read_text().replace('r102_short_0263',case).replace('source/native/forced sequential trackers','source/native sequential trackers')
t=t.replace('7b1b8dfd2792118c6761ea14188b60c0f4ece33a193d4bf0070cdf824549ce88',sha(m)).replace('[1,74,100,2]','[1,58,100,2]').replace("==74,'authorized physical domain", "==58,'authorized physical domain")
t=t.replace("['source','native','forced']","['source','native']").replace("['native','forced']","['native']").replace("'all_three_trackers_released':True","'all_trackers_released':True,'algorithm_benefit_comparison':False,'task_status':'PARTIAL'")
ast.parse(t);assert 'forced' not in t
(r/'audit/run_authorized.py').write_text(t)
shutil.copyfile(source.parent/'cgroup_memory.py',r/'audit/cgroup_memory.py')
check=(H/'check_package.py').read_text().replace("{'source','native','forced'}","{'source','native'}").replace("['source','native','forced']","['source','native']")
(r/'audit/check_package.py').write_text(check)
put(r/'audit/RECOVERY_BINDING.json',{'case':case,'valid_frames':58,'input_sha256':sha(m),'fresh_roles':['source','native'],'task_status':'PARTIAL','algorithm_benefit_comparison':False,'priority':'after R101/R107/R1020263 paired scores','preload_cgroup_GiB':12,'runtime_cgroup_GiB':8,'R107_exact_release':{'pid':1226044,'start_ticks':'15372732','uid':1004},'requires_root_scheduling':True,'GPU_started':False})
files={str(p.relative_to(r)):sha(p) for p in sorted(r.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
put(r/'SEAL.json',{'schema':'ive-post-r107-actual-native-mf-v1','files':files})
print(json.dumps({'case':case,'seal_sha256':sha(r/'SEAL.json'),'files':len(files),'GPU_started':False}))
