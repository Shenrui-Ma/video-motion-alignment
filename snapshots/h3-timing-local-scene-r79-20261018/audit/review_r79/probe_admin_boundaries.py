"""Independent CPU probes; all network/process/GPU operations are mocked."""
import contextlib,io,json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import job,execution_gate,r79_contract,lease_watchdog,service
out={}
with tempfile.TemporaryDirectory() as temp:
 r=Path(temp);(r/'configs/graphs').mkdir(parents=True);(r/'logs').mkdir();(r/'processes').mkdir()
 name='r79_short_0144_seed2026101701_forced';graph={'1':{'inputs':{'a':1}}};data=json.dumps(graph).encode();(r/'configs/graphs'/f'{name}.json').write_bytes(data);(r/'configs/queue.json').write_text('{}')
 old={'pid':1,'identity':{'uid':1004,'start_ticks':'10'}};new={'pid':2,'identity':{'uid':1004,'start_ticks':'20'}}
 binding={'graph_sha256':job.hashlib.sha256(data).hexdigest()};calls=[]
 def request(route,body=None):
  calls.append(route)
  if route=='/queue':return {'queue_running':[],'queue_pending':[]}
  if route=='/prompt':return {'prompt_id':'simulated-only'}
  raise AssertionError(route)
 # Successful admitted_job belongs to old; simulated owner replacement occurs
 # after that check but before active_service is captured by submit.
 with patch.object(job,'RUN',r),patch.object(execution_gate,'admitted_job',return_value=True),patch.object(r79_contract,'validate_job',return_value=binding),patch.object(r79_contract,'prepare_loader_inputs'),patch.object(job,'active_service',return_value=new),patch.object(job,'wait_host_admission',return_value=0),patch.object(job,'request',side_effect=request),patch.object(service,'write_json',side_effect=lambda p,v:Path(p).write_text(json.dumps(v))),contextlib.redirect_stdout(io.StringIO()):
  result=job.submit(name)
 out['forced_submission_after_generation_change']={'approved_generation':old,'generation_seen_after_admission':new,'prompt_posted':'/prompt' in calls,'recorded_generation':result['service_identity'],'mock_only':True}
record={'pid':11,'identity':{'uid':1004,'start_ticks':'12'}}
with patch.object(lease_watchdog,'read',side_effect=[record,{'continuous':{'x':1}},record]),patch.object(service,'current_identity',return_value=record['identity']),patch.object(service,'queue_at',return_value={'queue_running':[],'queue_pending':[]}),patch.object(lease_watchdog,'reason',return_value='bounded_idle_review_expired'),patch.object(service,'write_json',side_effect=OSError('simulated disk full')),patch.object(service,'assert_owned'),patch.object(service,'stop') as stop:
 try:lease_watchdog.main()
 except OSError as e:out['watchdog_receipt_io_failure']={'exception':repr(e),'exact_stop_calls':stop.call_count,'mock_only':True}
(Path(__file__).parent/'ADMIN_BOUNDARY_PROBE.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
