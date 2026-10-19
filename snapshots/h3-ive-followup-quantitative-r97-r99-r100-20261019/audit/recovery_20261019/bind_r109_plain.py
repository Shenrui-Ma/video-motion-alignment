"""Bind one fresh ordinary R109 track using the verified R100 source; no GPU launch."""
from pathlib import Path
import json,hashlib,shutil,ast
H=Path(__file__).resolve().parent;case='r109_short_0114_plain';R=H/case
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
put=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
assert R.is_dir() and not(R/'SEAL.json').exists()
m=R/'cases'/case/'INPUTS.json';assert set(json.loads(m.read_text())['roles'])=={'source','plain'}
T=(H/'r102_short_0092_native/audit/run_authorized.py').read_text().replace('r102_short_0092_native',case).replace('source/native sequential trackers','one fresh plain tracker with immutable cached source')
T=T.replace('330080e200898f6f03116041fdac057812bc77906d1410eac0e71e26eb46a944',sha(m)).replace('[1,58,100,2]','[1,105,100,2]').replace("==58,'authorized physical domain", "==105,'authorized physical domain")
T=T.replace("['source','native']","['plain']").replace("['native']","['plain']").replace("'task_status':'PARTIAL'","'source_cache_reused':True,'task_status':'FULL_VISUAL_REVIEW_SEPARATE'")
ast.parse(T);(R/'audit/run_authorized.py').write_text(T)
shutil.copyfile(H/'r102_short_0092_native/audit/cgroup_memory.py',R/'audit/cgroup_memory.py')
C=(H/'r102_short_0092_native/audit/check_package.py').read_text().replace("{'source','native'}","{'source','plain'}").replace("['source','native']","['plain']")
C=C.replace("q['runs']['native']['video']", "q['video']").replace("q['runs']['native']['valid_frames']", "q['valid_frames']").replace("q['runs']['native']['run_id']", "q['run_id']")
C=C.replace("wrapper=(r/'audit/run_authorized.py').read_text()", "c.validate_reuse(s,m,c.read(case/'tracks/source/REPORT.json'),c.sha(case/'tracks/source/REPORT.json'),c.sha(case/'tracks/source/tracks.npz'))\nassert c.read(case/'SOURCE_REUSE_RECEIPT.json')['passed'] is True\nwrapper=(r/'audit/run_authorized.py').read_text()")
ast.parse(C);(R/'audit/check_package.py').write_text(C)
put(R/'audit/RECOVERY_BINDING.json',{'case':case,'valid_frames':105,'input_sha256':sha(m),'fresh_roles':['plain'],'cached_roles':['source'],'preload_cgroup_GiB':12,'runtime_cgroup_GiB':8,'R107_exact_release':{'pid':1226044,'start_ticks':'15372732','uid':1004},'requires_root_scheduling':True,'algorithm_benefit_comparison':False,'GPU_started':False})
files={str(p.relative_to(R)):sha(p) for p in sorted(R.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
put(R/'SEAL.json',{'schema':'ive-post-r107-ordinary-prompt-mf-v1','files':files});print(json.dumps({'seal_sha256':sha(R/'SEAL.json'),'files':len(files),'GPU_started':False}))
