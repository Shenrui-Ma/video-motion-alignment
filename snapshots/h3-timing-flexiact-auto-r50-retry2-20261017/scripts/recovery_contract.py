"""Fixed-five scientific registry with four new executions and one bound external case."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SOURCES=['chest','crouch','fitness','one_leg','rotate']
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,message):
 if not ok:raise ValueError(message)
def plan(root=ROOT,verify_external=True):
 root=Path(root);p=read(root/'configs/recovery/execution_plan.json');cases=read(root/'configs/protocol.json')['cases']
 require([c['source_id'] for c in cases]==SOURCES,'fixed five sources differ')
 require(p['new_runs']==[c['run_id'] for c in cases[1:]],'remaining four execution order differs')
 require(p['planned_denominator']==5 and p['restart_from_original_noise'] is True,'recovery scientific scope differs')
 require(p['external_chest']['run_id']==cases[0]['run_id'],'external chest identity differs')
 if verify_external:
  for row in p['external_chest']['evidence'].values():
   q=Path(row['local_file']);q=q if q.exists() else Path(row['remote_file'])
   require(sha(q)==row['sha256'],'external chest receipt changed: '+str(q))
 return p
def queue(root=ROOT):
 p=plan(root);q=read(Path(root)/'configs/queue.json')
 require(set(q)=={'jobs','finalize'} and q['jobs']==p['new_runs'] and type(q['finalize']) is bool,'recovery queue differs')
 return q
