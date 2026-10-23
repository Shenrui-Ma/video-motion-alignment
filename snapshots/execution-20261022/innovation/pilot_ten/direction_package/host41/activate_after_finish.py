import sys,json,hashlib,subprocess,shlex,time
from pathlib import Path
P=Path(__file__).resolve().parent;EXEC=P.parents[3];H=EXEC/'supervision/innovation_handoff';sys.path.insert(0,str(H))
import handoff,activate_direction_pilots as activation
from remote_ops import atomic,digest
HOST='H3_HOST_CONFIGURE_LOCALLY';R='/data4/research-user/h3_runs/benchmark_schedule_20261022';RECORD=H/'records/host41'
RECONCILE=r'''
root=Path(ROOT);snap=snapshot(root);jid='expand_short_0131_global_weak'
if not (snap['worker']['state']=='exited' and snap['service']['state'] in ('exited','missing_record') and not any(snap['locks'].values()) and not snap['port_listening'] and snap['worker_status'].get('event')=='finished' and snap['worker_status'].get('cleanup_code')==0):
 print(json.dumps({'status':'not_ready','snapshot':{'worker':snap['worker'],'service':snap['service'],'status':snap['worker_status'],'locks':snap['locks']}}));sys.exit(75)
with (root/'worker.lock').open('a') as wl, (root/'queue_state/runner.lock').open('a') as ql:
 fcntl.flock(wl,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(ql,fcntl.LOCK_EX|fcntl.LOCK_NB)
 state=read(root/'queue_state/state.json');old=state['jobs'][jid]
 if old.get('resolution')!='aborted_by_host_reboot':
  assert old['status']=='submission_unknown'
  proof=read(root/'innovation_handoff/reboot_abort_evidence.json')
  assert proof['submitted_before_current_boot'] and not proof['history_matches'] and not proof['queue_matches'] and not proof['output_files'] and not proof['result_exists']
  assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==proof['boot_id']
  assert not list((root/'output'/jid).glob('**/*.mp4')) and not (root/'queue_state/results'/f'{jid}.json').exists()
  archive={**old,'status':'aborted_by_host_reboot','resolution_evidence':proof,'resolved_unix':time.time()}
  atomic(root/'innovation_handoff/aborted_by_host_reboot.json',archive)
  state['jobs'][jid]={**old,'status':'failed','resolution':'aborted_by_host_reboot','retry_policy':'deferred_expansion_after_innovation','resolved_unix':time.time()}
 native='expand_short_0131_native';native_result=root/'queue_state/results'/f'{native}.json'
 if state['jobs'][native].get('resolution')!='output_lost_after_reboot':
  result=read(native_result) or read(root/'innovation_handoff/invalid_results'/native_result.name);assert result
  for file in result['files']:
   out=Path(file['path']);assert out.exists() and out.stat().st_size==0
  atomic(root/'innovation_handoff/output_lost_after_reboot.json',{'state_before':state['jobs'][native],'result_before':result,'resolution':'output_lost_after_reboot','checked_unix':time.time(),'recovery_check':'Only zero-byte output in original task output; .81 target partial is zero bytes and target frames absent'})
  destination=root/'innovation_handoff/invalid_results'/native_result.name;destination.parent.mkdir(exist_ok=True)
  if native_result.exists():native_result.replace(destination)
  state['jobs'][native].update(status='failed',resolution='output_lost_after_reboot',retry_policy='deferred_expansion_after_innovation',resolved_unix=time.time())
 atomic(root/'queue_state/state.json',state)
 manifest=read(root/'jobs.json');parked=read(root/'innovation_handoff/parked_manifest.json',{'jobs':[]})
 original=read(root/'innovation_handoff/original_manifest.json');lost_ids=[native,jid]
 for lost_id in reversed(lost_ids):
  job=next(j for j in original['jobs'] if j['id']==lost_id)
  if not any(j['id']==lost_id for j in parked['jobs']):parked['jobs'].insert(0,job)
 atomic(root/'innovation_handoff/parked_manifest.json',parked)
 manifest['jobs']=[j for j in manifest['jobs'] if j['id'] not in lost_ids];atomic(root/'jobs.json',manifest)
print(json.dumps({'status':'reconciled','manifest':manifest,'parked':parked,'aborted':read(root/'innovation_handoff/aborted_by_host_reboot.json')}))
'''
def remote_code(code):
 r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12',HOST,'python3 -'],input=code,text=True,capture_output=True,timeout=120)
 if r.returncode==75:return {'status':'not_ready'}
 if r.returncode:raise RuntimeError(r.stderr[-4000:])
 return json.loads(r.stdout)
def invoke41(req):
 ops=(H/'remote_ops.py').read_text().split("if __name__ == '__main__':")[0]
 code=ops+'\n'+activation.REMOTE_BODY+'\nprint(json.dumps(activate_request(json.loads('+repr(json.dumps(req))+'))))\n'
 return remote_code(code)

def run():
 ops=(H/'remote_ops.py').read_text().split("if __name__ == '__main__':")[0]
 rec=remote_code(ops+'\nROOT='+repr(R)+'\n'+RECONCILE)
 if rec['status']=='not_ready':return rec
 atomic(RECORD/'aborted_by_host_reboot.json',rec['aborted']);atomic(RECORD/'parked_manifest.json',rec['parked']);atomic(EXEC/'inference/package/jobs.json',rec['manifest'])
 atomic(RECORD/'latest_boundary.json',rec)
 # Existing service is gone. Replace only the verified old lifecycle script.
 script=EXEC/'inference/package/scripts/manage_service.py';variant=P/'manage_service.variant.py';oldhash=hashlib.sha256(script.read_bytes()).hexdigest();newhash=hashlib.sha256(variant.read_bytes()).hexdigest()
 code="from pathlib import Path;import hashlib,json;p=Path("+repr(R+'/scripts/manage_service.py')+");s="+repr(variant.read_text())+";h=hashlib.sha256(p.read_bytes()).hexdigest();assert h in "+repr([oldhash,newhash])+";q=p.with_name(p.name+'.innovation.tmp');q.write_text(s);q.replace(p);print(json.dumps({'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}))"
 remote_code(code);script.write_text(variant.read_text())
 pilots=json.loads((P/'jobs.json').read_text());assets=[{'path':r['destination'],'sha256':r['sha256']} for r in json.loads((P/'deployment_receipt.json').read_text())['records']]
 assets.append({'path':R+'/scripts/manage_service.py','sha256':newhash})
 for name in ['core.py','layout.py','schedule.py']:
  assets.append({'path':R+'/custom_nodes/H3Study/'+name,'sha256':hashlib.sha256((EXEC/'inference/package/custom_nodes/H3Study'/name).read_bytes()).hexdigest()})
 req={'root':R,'base':rec['manifest'],'pilots':pilots,'assets':assets}
 handoff.HOST=HOST
 prepared=invoke41({**req,'action':'prepare'})
 if prepared['status']=='not_ready':return prepared
 atomic(EXEC/'inference/package/jobs.json',prepared['manifest'])
 if prepared['status']=='already_activated':return prepared
 result=invoke41({**req,'action':'activate'});atomic(RECORD/'activation_latest.json',result);return result
if __name__=='__main__':
 try:
  result=run();print(json.dumps({k:v for k,v in result.items() if k!='manifest'},indent=2));sys.exit(75 if result['status']=='not_ready' else 0)
 except Exception as e:
  atomic(RECORD/'activation_error.json',{'error':str(e),'unix':time.time()});raise
