"""Wait for ten extension/control real prepared clips, then claim/launch one unique AWQ increment."""
from pathlib import Path
import subprocess,json,time,sys,fcntl,os
D=Path(__file__).parent;ready=set(['expand_short_0135_native', 'expand_short_0135_global_weak', 'expand_long_0161_native', 'expand_long_0161_global_weak', 'expand2_short_0166_native', 'expand2_short_0166_global_weak', 'expand2_short_0185_native', 'expand2_short_0185_global_weak', 'live_phase_short0358_native_20261023', 'live_phase_short0358_global_weak_20261023'])
with (D/'coordinate.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for _ in range(1440):
  r=subprocess.run([sys.executable,str(D.parent/'host60_extra/continue_new.py')],capture_output=True,text=True)
  (D/'DISCOVERY_CHECK.json').write_text(json.dumps({'returncode':r.returncode,'stdout':r.stdout[-1600:],'stderr':r.stderr[-1000:],'time':time.time()},indent=2))
  if r.returncode==0:
   found=json.loads((D.parent/'host60_extra/discovery_latest.json').read_text())
   if ready<=set(found.get('new_ready',[])):break
  time.sleep(60)
 else:raise TimeoutError('Prepared clips unavailable after24hours')
 for script in ['prepare.py','deploy_start.py']:
  r=subprocess.run([sys.executable,str(D/script)]);assert r.returncode==0,script
 with (D/'return_watch.log').open('a') as log:
  p=subprocess.Popen([sys.executable,str(D/'return_watch.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 (D/'return_watch_identity.json').write_text(json.dumps({'pid':p.pid,'time':time.time()}));print('AWQ_increment_launched',flush=True)
