"""Read-only 45s Sam queue observer; saves only small JSON/log files, never tensors/media."""
from pathlib import Path
import json,subprocess,time,hashlib,sys
BASE=Path(__file__).resolve().parent/'cases/05_real_megumi_v';OUT=BASE/'audit/sam_attempt3_monitor';OUT.mkdir(exist_ok=True)
REMOTE='/home/researcher/h3_runs/guidance_schedule_r149_host9_20261020/cases/05_real_megumi_v'
SCRIPT='ROOT='+repr(REMOTE)+'\n'+r'''
from pathlib import Path
import json,time,sys
p=Path(ROOT);sys.path.insert(0,str(p/'scripts'));import process_identity
s=json.loads((p/'configs/scientific_contract.json').read_text());owner=json.loads((p/'processes/service.json').read_text());actual=process_identity.snapshot(owner['pid']);status={'unix':time.time(),'service_pid':owner['pid'],'same_generation':actual is not None and process_identity.service_record(actual)==owner['identity'],'runs':[]};files={}
def take(rel):
 q=p/rel
 if not q.exists():return None
 if q.stat().st_size>3*1024*1024:raise ValueError('small evidence exceeded bound: '+rel)
 text=q.read_text();files[rel]=text
 return json.loads(text) if q.suffix=='.json' else text
status['controller']=take('logs/controller_state.json')
for c in s['cases']:
 run=c['run_id'];row={'run':run,'arm':c['arm']}
 r=take('audit/router/'+run+'.json')
 if r:row.update(started=r['started_calls'],completed=r['completed_calls'],forwards=r['completed_forward_calls'],forward_dispatch_seconds=r.get('forward_wall_seconds',[]))
 x=take('audit/x0/'+run+'/manifest.json')
 if x:row.update(callbacks=x['callback_count'],x0_status=x['status'])
 t=take('audit/x0/'+run+'/timing.json')
 if t:row['timing']=t
 gate=take('analysis/postrun/05_real_megumi_v/'+run+'_GATE.json')
 if gate:row['gate']={'passed':gate['passed'],'video':gate.get('video'),'role':gate.get('role')}
 status['runs'].append(row)
for name in ['COMPLETE.json','ROOT_EXIT_RECEIPT.json','FAILURE.json','CAPACITY_MONITOR_EXIT.json']:
 v=take('audit/root_r149_sam_host9_attempt3/'+name)
 if v:status[name]=v
cap=p/'audit/root_r149_sam_host9_attempt3/CAPACITY_TRIAL.jsonl'
if cap.exists():
 with cap.open('rb') as f:f.seek(max(0,cap.stat().st_size-20000));tail=f.read().decode().splitlines()
 row=json.loads(tail[-1])
 if 'decision' in row:status['capacity']={'passed':row['decision']['passed'],'host_available_GiB':row['decision'].get('host_available_bytes',0)/2**30,'reasons':row['decision'].get('reasons')}
 else:status['capacity_terminal']=row
for rel in ['logs/comfyui.log','logs/controller.log','audit/root_r149_sam_host9_attempt3/execution.log']:
 q=p/rel
 if q.exists():
  with q.open('rb') as f:f.seek(max(0,q.stat().st_size-100000));files[rel+'.tail']=f.read().decode(errors='replace')
if 'COMPLETE.json' in status:take('analysis/postrun/05_real_megumi_v/SCHEDULE_RUNTIME_GATE.json')
print(json.dumps({'status':status,'files':files}))
'''
last=None;errors=0
while True:
 start=time.monotonic()
 try:
  r=subprocess.run(['ssh','H3_SERVER_A','env PYTHONDONTWRITEBYTECODE=1 python3 -'],input=SCRIPT,text=True,capture_output=True,timeout=30)
  if r.returncode:raise RuntimeError(r.stderr[-2000:])
  result=json.loads(r.stdout);status=result['status'];errors=0
  for rel,text in result['files'].items():
   target=OUT/rel;target.parent.mkdir(parents=True,exist_ok=True)
   if not target.exists() or target.read_text()!=text:target.write_text(text)
  (OUT/'latest.json').write_text(json.dumps(status,indent=2)+'\n')
  with (OUT/'observations.jsonl').open('a') as f:f.write(json.dumps(status)+'\n')
  compact={'service_pid':status['service_pid'],'same_generation':status['same_generation'],'controller':status['controller'],'runs':[{k:v for k,v in row.items() if k in ['arm','callbacks','forwards','gate','forward_dispatch_seconds']} for row in status['runs']],'capacity_passed':status.get('capacity',{}).get('passed'),'complete':'COMPLETE.json' in status,'failure':status.get('FAILURE.json')}
  encoded=json.dumps(compact,sort_keys=True)
  if encoded!=last:print(json.dumps({'observed_unix':status['unix'],**compact}),flush=True);last=encoded
  if status.get('COMPLETE.json',{}).get('passed'):
   receipt=status.get('ROOT_EXIT_RECEIPT.json',{});assert receipt.get('passed') and receipt.get('process_absent') and receipt.get('CUDA_allocation_absent');assert not status['same_generation'];print('FOUR_ARM_COMPLETE_AND_RELEASED',flush=True);break
  if 'FAILURE.json' in status:print('ROOT_ATTEMPT_FAILED_DIAGNOSIS_REQUIRED',flush=True);break
 except Exception as error:
  errors+=1;print(json.dumps({'observer_error':repr(error),'consecutive':errors}),flush=True)
  if errors>=3:raise
 time.sleep(max(0,45-(time.monotonic()-start)))
