from pathlib import Path
import json,hashlib,subprocess,time
r=Path('/data5/researcher/h3_runs/timing_auto_source28289_r45_20261017')
s=json.loads((r/'processes/service.json').read_text());pid=s['pid'];p=Path('/proc')/str(pid);i={'uid':p.stat().st_uid,'start_ticks':p.joinpath('stat').read_text().rsplit(')',1)[1].split()[19],'raw_cmd_sha256':hashlib.sha256(p.joinpath('cmdline').read_bytes()).hexdigest()}
assert i['uid']==1016 and i['start_ticks']==s['identity']['start_ticks']
assert s['gpu_uuid']=='GPU-REDACTED' and s['port']==8507
rec={'unix':time.time(),'service_pid':pid,'identity':i,'service_sha256':hashlib.sha256((r/'processes/service.json').read_bytes()).hexdigest()}
(r/'audit/root_launch_identity.json').write_text(json.dumps(rec,indent=2)+'\n')
p=subprocess.run(['python3','-u',str(r/'scripts/start_controller.py'),'--pid',str(pid),'--start-ticks',i['start_ticks']],capture_output=True,text=True)
(r/'audit/root_controller_start.log').write_text(p.stdout+p.stderr);print(json.dumps(rec));print(p.stdout);print(p.stderr);raise SystemExit(p.returncode)
