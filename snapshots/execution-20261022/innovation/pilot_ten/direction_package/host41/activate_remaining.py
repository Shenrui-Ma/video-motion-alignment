"""Gate remaining direction runs on two successful, audited pilots and idle service."""
import sys,json,hashlib,math,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;EXEC=P.parents[3];H=EXEC/'supervision/innovation_handoff';sys.path.insert(0,str(H))
import activate_direction_pilots as activation
from remote_ops import atomic
ROOT='/data4/research-user/h3_runs/benchmark_schedule_20261022';HOST='H3_HOST_CONFIGURE_LOCALLY';RECORD=H/'records/host41'
CHECK=r'''
root=Path(ROOT);state=read(root/'queue_state/state.json')['jobs'];rows=[]
for task in ['short_0252','short_0358']:
 jid='innov41_'+task+'_direction_gated';s=state.get(jid,{})
 if s.get('status') in ('failed','failed_exhausted','blocked','invalid'):raise RuntimeError('pilot did not complete: '+jid+' '+str(s.get('error')))
 if s.get('status')!='completed':print(json.dumps({'status':'waiting_pilots','job':jid,'state':s.get('status')}));sys.exit(75)
for task in ['short_0252','short_0358']:
 jid='innov41_'+task+'_direction_gated';s=state[jid]
 attempt=s['attempt_id'];audit=read(root/'audit/direction'/f'{attempt}.json');timing=read(root/'audit/timing'/f'{attempt}.json');result=read(root/'queue_state/results'/f'{jid}.json')
 assert audit['routed_calls']==1000 and audit['native_override_calls']==1000
 assert len(audit['direction_forward_summaries'])==20
 assert audit['intermediate_vae_decode_calls']==0 and audit['full_dit_forward_calls_added']==0
 energy=audit['cumulative_applied_correction_energy'];assert math.isfinite(energy) and energy>0
 assert len(timing['steps'])==20 and all(math.isfinite(x['seconds']) and x['seconds']>0 for x in timing['steps'])
 assert result['files']
 for f in result['files']:
  p=Path(f['path']);assert p.stat().st_size>0
  assert hashlib.sha256(p.read_bytes()).hexdigest()==f['sha256']
 rows.append({'id':jid,'routed_calls':audit['routed_calls'],'correction_energy':energy,'sampler_wall_seconds':timing.get('sampler_wall_seconds'),'files':len(result['files'])})
print(json.dumps({'status':'pilots_verified','rows':rows}))
'''
def remote(code):
 try:
  r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12',HOST,'python3 -'],input=code,text=True,capture_output=True,timeout=180)
 except subprocess.TimeoutExpired:
  return {'status':'not_ready','reason':'ssh_transport_timeout_retry_idempotent'}
 if r.returncode==255:return {'status':'not_ready','reason':'ssh_transport_retry','error':r.stderr[-1000:]}
 if r.returncode==75:return json.loads(r.stdout)
 if r.returncode:raise RuntimeError(r.stderr[-4000:])
 return json.loads(r.stdout)
def run():
 ops=(H/'remote_ops.py').read_text().split("if __name__ == '__main__':")[0]
 check=remote(ops+'\nimport math\nROOT='+repr(ROOT)+'\n'+CHECK)
 if check['status'] in ('waiting_pilots','not_ready'):return check
 atomic(RECORD/'two_direction_pilots_verified.json',check)
 base=json.loads((RECORD/'activation_latest.json').read_text())['manifest']
 assets=json.loads((P/'remaining_deployment_receipt.json').read_text());assert assets['complete']
 originals=[r for r in json.loads((P/'deployment_receipt.json').read_text())['records'] if '/H3PartialRoPE/' not in r['destination'] and '/H3TemporalCoverage/' not in r['destination']]
 replay=json.loads((P/'CPU_REPLAY_REMAINING.json').read_text());assert replay['status']=='passed' and len(replay['cache_replays'])==4
 for name in ('core.py','layout.py','schedule.py'):
  originals.append({'destination':ROOT+'/custom_nodes/H3Study/'+name,'sha256':hashlib.sha256((EXEC/'inference/package/custom_nodes/H3Study'/name).read_bytes()).hexdigest()})
 combined={r['destination']:r for r in originals+assets['records']}
 req={'root':ROOT,'base':base,'pilots':json.loads((P/'remaining_jobs.json').read_text()),'assets':[{'path':r['destination'],'sha256':r['sha256']} for r in combined.values()]}
 body=activation.REMOTE_BODY.replace("directory/'direction_activation.json'","directory/'direction_remaining_activation.json'")
 def invoke(action):
  return remote(ops+'\n'+body+'\nprint(json.dumps(activate_request(json.loads('+repr(json.dumps(dict(req,action=action)))+'))))\n')
 prepared=invoke('prepare')
 if prepared['status']=='not_ready':return prepared
 atomic(EXEC/'inference/package/jobs.json',prepared['manifest'])
 result=prepared if prepared['status']=='already_activated' else invoke('activate')
 atomic(RECORD/'remaining_activation.json',result)
 if result['status'] in ('activated','already_activated') and (RECORD/'remaining_activation_error.json').exists():
  previous=json.loads((RECORD/'remaining_activation_error.json').read_text());atomic(RECORD/'remaining_activation_error.json',{**previous,'resolved':True,'resolution':result['status']})
 return result
if __name__=='__main__':
 try:
  out=run();print(json.dumps({k:v for k,v in out.items() if k!='manifest'},indent=2));sys.exit(75 if out['status'] in ('not_ready','waiting_pilots') else 0)
 except Exception as e:
  atomic(RECORD/'remaining_activation_error.json',{'error':str(e)});raise
