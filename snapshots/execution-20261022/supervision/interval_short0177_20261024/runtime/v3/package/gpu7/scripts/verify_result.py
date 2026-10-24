"""Require complete 20x50 routing, synchronized timing, raw geometry and SHA."""
import json,hashlib,math,time
from pathlib import Path

def verify(root,arm):
 root=Path(root);cfg=json.loads((root/'CONFIG.json').read_text())
 job='interval_short_0177_'+arm;state=json.loads((root/'queue_state/state.json').read_text())['jobs'][job]
 assert state['status']=='completed' and state['attempts']==1, 'Job incomplete or repeated'
 rid=state['attempt_id'];a=json.loads((root/'audit/router'/f'{rid}.json').read_text());t=json.loads((root/'audit/timing'/f'{rid}.json').read_text())
 expected=cfg['steps'][arm]
 assert 'error' not in a and a['completed_forward_calls']==20
 assert a['started_calls']==a['completed_calls']==a['native_override_calls']==1000
 assert a['calls_by_block']==[20]*50 and a['calls_by_forward']==[50]*20
 assert a['routed_calls']==50*len(expected)
 assert a['routed_by_forward']==[50 if i in expected else 0 for i in range(20)]
 assert a['routed_by_block']==[len(expected)]*50
 assert a['schedule']==arm and a['step_set_zero_based']==expected
 assert a['alpha']==(.25 if arm=='global_weak' else 1.)
 assert a['pixel_interval_inclusive']==[0,59] and a['block_interval_half_open']==[0,50]
 assert a['expected_sampling_steps']==20 and a['backend']=='aten._scaled_dot_product_flash_attention.default'
 assert t['status']=='complete' and t['passed'] and len(t['per_step_seconds'])==20
 assert all(math.isfinite(v) and v>0 for v in t['per_step_seconds']) and t['sampler_wall_seconds']>0
 r=json.loads((root/'queue_state/results'/f'{job}.json').read_text())
 assert len(r['files'])==1
 f=r['files'][0];s=f['probe']['streams'][0]
 assert (s['width'],s['height'],int(s['nb_frames']))==(1312,736,73)
 video=Path(f['path']);assert hashlib.sha256(video.read_bytes()).hexdigest()==f['sha256']
 d=json.loads((root/'logs/backend_dispatch_audit.json').read_text())
 ops=d['operations'];counts={b:sum(v['successful_calls'] for k,v in ops.items() if k.startswith(b+'.')) for b in ['triton','cuda','eager']}
 contract=json.loads((root/'BACKEND_CONTRACT.json').read_text())
 assert contract['boot_id']==cfg['boot_id'] and contract['backend'] in ['cuda','triton']
 expected_backend=contract['backend']
 assert counts[expected_backend]>0 and all(counts[b]==0 for b in counts if b!=expected_backend), 'INT8 backend differs from native pilot contract'
 assert not d['logging_errors'] and sum(v['failed_calls'] for v in ops.values())==0
 return {'checked_unix':time.time(),'passed':True,'job_id':job,'attempt_id':rid,'complete_forwards':20,'completed_blocks':1000,'routed_blocks':a['routed_calls'],'sampling_seconds':t['sampler_wall_seconds'],'mean_step_seconds':t['mean_sampling_step_seconds'],'video':f,'valid_frames':60,'dispatch_process_cumulative_successful_calls':counts}
if __name__=='__main__':
 import sys
 result=verify(sys.argv[1],sys.argv[2]);print(json.dumps(result,indent=2))
