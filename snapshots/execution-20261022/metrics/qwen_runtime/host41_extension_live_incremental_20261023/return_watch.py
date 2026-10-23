from pathlib import Path
import subprocess,sys,json,time
D=Path(__file__).parent
for _ in range(2880):
 p=subprocess.run([sys.executable,str(D/'sync_results.py')],capture_output=True,text=True)
 (D/'return_watch_last.json').write_text(json.dumps({'returncode':p.returncode,'stdout':p.stdout[-2000:],'stderr':p.stderr[-1500:],'time':time.time()},indent=2))
 if (D/'RETURNED.json').exists():
  subprocess.run([sys.executable,str(D.parent/'host60_extra/sync_results.py')],check=True)
  subprocess.run([sys.executable,str(D.parent/'export_adaptive_awq.py'),'--refresh'],check=True)
  break
 if p.returncode==0:
  s=json.loads((D/'snapshot_status.json').read_text())
  if s['target_status']=='failed':break
 time.sleep(60)
