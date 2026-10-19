"""Retain all five outcomes while collecting four new incremental case releases."""
from pathlib import Path
import json,hashlib
POST=Path(__file__).resolve().parents[1];ROOT=POST.parent.parent
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
plan=read(ROOT/'configs/recovery/execution_plan.json');p=read(POST/'PROTOCOL.json');rows=[]
for case in p['cases']:
 run=case['run_id']
 if run==plan['external_chest']['run_id']:
  e=plan['external_chest']['evidence']['ready'];ready=Path(e['local_file']);ready=ready if ready.exists() else Path(e['remote_file']);assert sha(ready)==e['sha256'];r=read(ready)
  rows.append({'source':case['source_id'],'status':'external_complete','producer_root':str(ready),'summary':r['summary']})
 else:
  ready=POST/'completed_cases'/run/'CASE_READY.json';r=read(ready) if ready.exists() else None
  rows.append({'source':case['source_id'],'status':'complete' if r else 'pending','case_ready':str(ready),'case_ready_sha256':sha(ready) if r else None,'summary':r['summary'] if r else None})
print(json.dumps({'planned_denominator':5,'complete':sum(r['status']!='pending' for r in rows),'rows':rows,'failed_prior_cost':plan['failed_crouch_cost'],'GPU_tracker_scores':'separate root-controlled lane'},indent=2))
