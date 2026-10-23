from pathlib import Path
import json,subprocess,shlex,hashlib
D=Path(__file__).resolve().parent
HOST='H3_HOST_PRIMARY'
TARGET='/data4/research-user/h3_metrics_qwen_20261022/qwen_runtime/extension_live_incremental_20261023'
for n in ('launch.py','batch_eval.py'):
 subprocess.run(['scp','-q',str(D/n),HOST+':'+TARGET+'/'+n],check=True)
code=r'''
from pathlib import Path
import json,hashlib,subprocess,sys,time,fcntl,os
r=Path(ROOT);d=r/'run';expected=json.load(sys.stdin)
for name,sha in expected.items():assert hashlib.sha256((r/name).read_bytes()).hexdigest()==sha
assert len(json.loads((d/'expected_manifest.json').read_text())['jobs'])==10
with (d/'start.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 def alive(rec):
  try:
   p=Path('/proc')/str(rec['pid']);stat=(p/'stat').read_text().rsplit(')',1)[1].split();return p.stat().st_uid==rec['uid'] and stat[19]==str(rec['start_ticks']) and stat[0]!='Z'
  except FileNotFoundError:return False
 for f in [r.parent/'fixed_budget_incremental_20261023/run/supervisor_identity.json',r.parent/'fixed_budget_incremental_20261023/run/worker_identity.json']:
  assert not alive(json.loads(f.read_text()))
 for f in [d/'supervisor_identity.json',d/'worker_identity.json',d/'STARTED.json']:
  if f.exists() and alive(json.loads(f.read_text())):raise RuntimeError('own process already running')
 with (d/'supervisor.log').open('a') as log:
  p=subprocess.Popen(['python3','-u',str(r/'launch.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 proc=Path('/proc')/str(p.pid);rec={'pid':p.pid,'uid':proc.stat().st_uid,'start_ticks':(proc/'stat').read_text().rsplit(')',1)[1].split()[19],'time':time.time()};(d/'STARTED.json').write_text(json.dumps(rec,indent=2));print(json.dumps(rec))
'''.replace('ROOT',repr(TARGET))
x=subprocess.run(['ssh',HOST,shlex.join(['python3','-c',code])],input=json.dumps({n:hashlib.sha256((D/n).read_bytes()).hexdigest() for n in ['launch.py','batch_eval.py']}),capture_output=True,text=True,check=True)
(D/'STARTED.json').write_text(x.stdout);print(x.stdout)
