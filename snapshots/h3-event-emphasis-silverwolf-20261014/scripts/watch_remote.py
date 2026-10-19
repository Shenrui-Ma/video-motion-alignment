import json,subprocess,time,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
deadline=time.monotonic()+5400
while time.monotonic()<deadline:
 p=subprocess.run([sys.executable,str(root/'scripts/probe_live.py')],capture_output=True,text=True,timeout=60)
 if p.returncode:
  print(json.dumps({'probe_error':p.stderr[-1200:]}),flush=True)
 else:
  d=json.loads(p.stdout); c=d.get('controller',{}); h=d.get('hooks',{})
  tail=d.get('log_tail','').replace('\r','\n').splitlines()
  print(json.dumps({'unix':d.get('unix'),'controller':c,'hooks':h,'gpu':d.get('gpu_csv'),'last_log_lines':tail[-3:]},ensure_ascii=False),flush=True)
  if c.get('status') in ['failed','all_queued_jobs_complete','awaiting_review_or_additional_controls','complete_wait_window_expired']:break
 time.sleep(35)
else:raise TimeoutError('monitor deadline')
