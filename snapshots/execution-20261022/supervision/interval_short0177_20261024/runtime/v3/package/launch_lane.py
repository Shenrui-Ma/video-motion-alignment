"""Explicit finite lane launch. Never called by a scheduled task."""
import fcntl,json,os,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parent/('gpu'+sys.argv[1]);assert sys.argv[1] in ['5','6','7']
with (root/'launch.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 receipt=root/'LAUNCH_RECEIPT.json'
 assert not receipt.exists(), 'One launch only; existing receipt retained'
 sys.path.insert(0,str(root/'scripts'))
 from admission import preflight
 preflight(root)
 with (root/'logs/worker.log').open('ab',buffering=0) as log:
  p=subprocess.Popen(['python3','-u',str(root/'scripts/single_attempt_worker.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
 stat=(Path('/proc')/str(p.pid)/'stat').read_text().rsplit(')',1)[1].split()
 data={'pid':p.pid,'uid':os.getuid(),'start_ticks':stat[19],'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'root':str(root),'started_unix':time.time()}
 receipt.write_text(json.dumps(data,indent=2));print(json.dumps(data))
