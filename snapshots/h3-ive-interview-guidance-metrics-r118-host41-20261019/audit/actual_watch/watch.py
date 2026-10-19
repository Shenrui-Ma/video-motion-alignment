from pathlib import Path
import json, subprocess, time, traceback, os
ROOT=Path('/Users/researcher/DevProjects/h3-ive-interview-guidance-metrics-r118-host41-20261019')
WATCH=ROOT/'audit/actual_watch'
PYTHON='/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python'
ATTEMPT='host41_interview_attempt1'
def save(name,value):
 p=WATCH/name;tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(p)
started=time.time();save('STARTED.json',{'pid':os.getpid(),'started_unix':started,'GPU_submission':False,'attempt':ATTEMPT})
while time.time()-started<6*3600:
 try:
  p=subprocess.run([PYTHON,str(ROOT/'audit/host41_attempt_adapter/consume_host41.py'),'--attempt',ATTEMPT,'--status'],capture_output=True,text=True,timeout=120,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
  if p.returncode:raise RuntimeError(p.stderr)
  state=json.loads(p.stdout);save('STATUS.json',{'unix':time.time(),**state,'GPU_submission':False})
  if state['pair_present'] and state['complete_present']:
   with (WATCH/'consume.log').open('a') as log:
    q=subprocess.run([PYTHON,str(ROOT/'audit/host41_attempt_adapter/consume_host41.py'),'--attempt',ATTEMPT],stdout=log,stderr=log,timeout=1800,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
   if q.returncode:raise RuntimeError('consume failed; inspect consume.log')
   if (ROOT/'incoming/long_0047/COLLECTION.json').exists() and (ROOT/'prepared/long_0047/MF_INPUTS.json').exists():
    save('READY_FOR_REVIEW.json',{'passed':True,'unix':time.time(),'GPU_submission':False,'attempt':ATTEMPT});break
 except BaseException as e:
  save('ERROR.json',{'error':repr(e),'traceback':traceback.format_exc(),'unix':time.time(),'GPU_submission':False})
  # Intakes may leave auditable partial stages; stop for owner review instead of hiding errors.
  raise
 time.sleep(300)
else:save('WATCH_TIMEOUT.json',{'unix':time.time(),'GPU_submission':False})
