"""Read small experiment metadata over SSH; no videos or server writes."""
import json
from pathlib import Path
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parent
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10']
METRICS=r'''
import json,collections
from pathlib import Path
r=Path('/data/research-user/h3_metrics_20261022')
p=r/'evaluation/summary.json';d=json.loads(p.read_text());m=json.loads((r/'code/manifest.json').read_text())
scopes=['main_all','main_IVEBench','expansion_all']
last=[json.loads(p.read_text()) for p in (r/'evaluation/results/new_long_0167_global_weak').glob('*.json')]
actual=[]
for j in m['jobs']:
 actual.append({k:j[k] for k in ['id','task_id','dataset','method','cohort','timing'] if k in j})
print(json.dumps({'summary_mtime_unix':p.stat().st_mtime,'means':{k:d['means'][k] for k in scopes},'last_job_metrics':[{k:x[k] for k in ['metric','status','score','error'] if k in x} for x in last if 'metric' in x], 'actual_jobs':actual,'expected_count':len(m.get('expected_jobs',[]))}))
'''
INFERENCE=r'''
import json
from pathlib import Path
r=Path('/data4/research-user/h3_runs/benchmark_schedule_20261022');m=json.loads((r/'jobs.json').read_text());s=json.loads((r/'queue_state/state.json').read_text())
rows=[]
for j in m['jobs']:
 if not j['id'].startswith('new_'):continue
 p=r/'queue_state/results'/(j['id']+'.json');v=json.loads(p.read_text()) if p.exists() else {}
 rows.append({'id':j['id'],'task_id':j['metadata']['task_id'],'method':j['metadata']['method'],'valid_frames':j['metadata'].get('valid_frames'),'status':s['jobs'].get(j['id'],{}).get('status'),'timing':v.get('timing',{})})
print(json.dumps(rows))
'''
def run(host,script):
 p=subprocess.run(SSH+[host,'python3','-'],input=script,text=True,capture_output=True,check=True,timeout=60)
 return json.loads(p.stdout)
def main():
 metrics=run('H3_HOST_CONFIGURE_LOCALLY',METRICS)
 inference=run('H3_HOST_CONFIGURE_LOCALLY',INFERENCE)
 result={'collected_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'metrics':metrics,'new24_inference':inference}
 (ROOT/'snapshot.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps({'collected_at':result['collected_at'],'new24_complete':sum(x['status']=='completed' for x in inference),'last_job':metrics['last_job_metrics'],'main_global_MF':metrics['means']['main_all']['methods']['global_weak']['motion_fidelity']},ensure_ascii=False))
if __name__=='__main__':main()
