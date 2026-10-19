"""One read-only capacity snapshot; invoked manually, no watcher or GPU work."""
from pathlib import Path
import json,os,time,hashlib,subprocess
R=Path('/data4/researcher/h3_runs/timing_ive_native_screen_r96_20261018')
EXPECTED_PID=951112;EXPECTED_START='10923395'
def read(p):return json.loads(p.read_text())
owner=read(R/'processes/service.json')
assert owner['pid']==EXPECTED_PID and str(owner['identity']['start_ticks'])==EXPECTED_START
snapshot={'observed_unix':time.time(),'owner':owner,'files':{},'proc':{},'cgroups':{},'gpu':{}}
paths=['processes/controller.json','audit/CGROUP_STARTUP.json','audit/root_native_screen_attempt1/CGROUP_PRE_GO.json','audit/root_native_screen_attempt1/STARTED.json','logs/controller_state.json','logs/resources.jsonl','logs/residency.jsonl','logs/backend_dispatch_audit.json','logs/int8_row_chunking.jsonl','logs/comfyui.log','logs/r96_long_0047_seed2026101701_native_job.json','logs/r96_long_0047_seed2026101701_native_history.json','audit/router/r96_long_0047_seed2026101701_native.json','audit/x0/r96_long_0047_seed2026101701_native/manifest.json','analysis/postrun/long_0047/NATIVE_RUNTIME_GATE.json']
for rel in paths:
 p=R/rel
 if not p.exists():snapshot['files'][rel]={'present':False};continue
 raw=p.read_bytes();snapshot['files'][rel]={'present':True,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'text':raw.decode(errors='replace')}
proc=Path('/proc')/str(EXPECTED_PID)
if proc.exists():
 stat=(proc/'stat').read_text();start=stat[stat.rfind(')')+2:].split()[19];assert start==EXPECTED_START
 snapshot['proc']={'present':True,'start_ticks':start,'uid':proc.stat().st_uid,'cmdline_sha256':hashlib.sha256((proc/'cmdline').read_bytes()).hexdigest()}
 membership=(proc/'cgroup').read_text();relative=Path([x.split(':',2)[2] for x in membership.splitlines() if x.startswith('0::')][0])
 for rel in [relative,*relative.parents]:
  base=Path('/sys/fs/cgroup')/str(rel).lstrip('/');row={}
  for name in ['memory.current','memory.peak','memory.high','memory.max','memory.events','memory.stat','memory.pressure','io.pressure']:
   p=base/name
   if p.exists():row[name]=p.read_text()
  snapshot['cgroups'][str(rel)]=row
else:snapshot['proc']={'present':False}
for label,argv in [('device',['nvidia-smi','--id='+owner['gpu_uuid'],'--query-gpu=index,uuid,memory.used,memory.free,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits']),('compute',['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'])]:
 try:q=subprocess.run(argv,capture_output=True,text=True,timeout=15,check=True);snapshot['gpu'][label]={'available':True,'stdout':q.stdout,'stderr':q.stderr}
 except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as e:snapshot['gpu'][label]={'available':False,'error':repr(e)}
print(json.dumps(snapshot,indent=2))
