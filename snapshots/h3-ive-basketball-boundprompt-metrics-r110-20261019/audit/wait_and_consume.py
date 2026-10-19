from pathlib import Path
import subprocess,time,json
R=Path(__file__).resolve().parents[1]
remote='/data5/researcher/h3_runs/timing_ive_basketball_boundprompt_r110_20261019'
cmd=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','H3_SERVER_A',"python3 - <<'REMOTE'\nfrom pathlib import Path\nimport json\nr=Path('"+remote+"');a=r/'audit/root_boundprompt_attempt1'\nprint(json.dumps({'complete':(a/'COMPLETE.json').exists(),'failure':(a/'FAILURE.json').exists(),'gate':(r/'analysis/postrun/NATIVE_RUNTIME_GATE.json').exists()}))\nREMOTE"]
end=time.monotonic()+1800
with (R/'audit/consumer_wait.log').open('a') as log:
 while time.monotonic()<end:
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=25)
  if p.returncode==0:
   state=json.loads(p.stdout);log.write(json.dumps({'unix':time.time(),**state})+'\n');log.flush()
   if state['failure']:raise RuntimeError('R110 launcher failure; inspect exact artifacts before recovery')
   if state['complete'] and state['gate']:break
  time.sleep(45)
 else:raise TimeoutError('R110 wait limit')
subprocess.run(['/Users/researcher/DevProjects/ComfyUI-dev/.venv/bin/python','scripts/consume.py'],cwd=R,check=True)
