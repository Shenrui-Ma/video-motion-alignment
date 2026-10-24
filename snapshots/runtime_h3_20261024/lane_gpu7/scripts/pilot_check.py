"""Read-only native first-forward evidence; root freezes returned contract."""
from pathlib import Path
import json,os,sys,time

def inspect(root):
 root=Path(root);c=json.loads((root/'CONFIG.json').read_text())
 boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();assert boot==c['boot_id']
 identities={}
 for name in ['worker_pid','service']:
  rec=json.loads((root/(name+'.json')).read_text());proc=Path('/proc')/str(rec['pid'])
  fields=(proc/'stat').read_text().rsplit(')',1)[1].split();cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode()
  assert proc.stat().st_uid==c['uid'] and fields[19]==rec['start_ticks'] and fields[0]!='Z' and str(root) in cmd
  identities[name]={'pid':rec['pid'],'start_ticks':fields[19],'uid':proc.stat().st_uid,'state':fields[0]}
 attempt='interval_short_0177_native__a1'
 a=json.loads((root/'audit/router'/f'{attempt}.json').read_text());t=json.loads((root/'audit/timing'/f'{attempt}.json').read_text());d=json.loads((root/'logs/backend_dispatch_audit.json').read_text())
 assert a['completed_forward_calls']>=1 and a['calls_by_forward'][0]==50 and a['routed_calls']==0 and 'error' not in a
 assert a['schedule']=='native' and a['expected_sampling_steps']==20 and a['alpha']==1
 assert a['first_attention']['dtype']=='torch.bfloat16' and a['first_attention']['flash_lse']
 assert a['backend']=='aten._scaled_dot_product_flash_attention.default'
 steps=t['steps'];assert len(steps)>=1 and steps[0]['step']==1 and steps[0]['seconds']>0 and t['status']!='failed'
 operations=d['operations'];counts={b:sum(v['successful_calls'] for k,v in operations.items() if k.startswith(b+'.')) for b in ['cuda','triton','eager']}
 assert not d['logging_errors'] and all(v['failed_calls']==0 for v in operations.values())
 active=[b for b in counts if counts[b]>0];assert len(active)==1 and active[0] in ['cuda','triton'], 'Mixed or eager dispatch'
 assert d['pid']==identities['service']['pid']
 mem={x.split(':')[0]:int(x.split(':')[1].split()[0]) for x in Path('/proc/meminfo').read_text().splitlines()}
 return {'passed':True,'checked_unix':time.time(),'boot_id':boot,'identities':identities,'completed_forward_calls':a['completed_forward_calls'],'first_forward_block_count':a['calls_by_forward'][0],'native_routed_calls':a['routed_calls'],'first_synchronized_step_seconds':steps[0]['seconds'],'first_block_dispatch_wall_seconds':a['forward_wall_seconds'][0],'qkv':a['first_attention'],'backend_process_counts':counts,'host_mem_available_gib':mem['MemAvailable']/1024**2,'contract_to_freeze':{'schema':'h3-int8-backend-contract-v1','boot_id':boot,'backend':active[0],'pilot_root':str(root),'pilot_attempt':attempt,'pilot_service':identities['service'],'source':'observed native first completed 50-block forward; retain existing registry selection','frozen_at_unix':time.time()}}
if __name__=='__main__':print(json.dumps(inspect(sys.argv[1]),indent=2))
