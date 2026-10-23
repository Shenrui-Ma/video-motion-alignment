"""Host-local handoff logic. The generated launcher supplies existing safe helpers."""
import math

def preceding_status(states, ids):
    failed=[j for j in ids if states.get(j,{}).get('status') in ('failed','failed_exhausted','blocked','invalid')]
    if failed:raise RuntimeError('direction jobs failed: '+','.join(failed))
    return all(states.get(j,{}).get('status')=='completed' for j in ids)

def verify_partial_audit(audit):
    assert audit['status']=='complete'
    assert audit['completed_forwards']==20 and audit['completed_blocks']==1000 and audit['compensated_calls']==1000
    assert audit['delta_resolved'] and audit['delta_mode']=='reference_origin'
    rotation=audit['rotation'];assert rotation['frequency_mask']==[0]*8+[1]*8 and rotation['selected_pair_indices']==list(range(8,16))
    assert math.isfinite(rotation['delta_physical_frames']) and rotation['delta_physical_frames']!=0
    layers=[layer for forward in audit['forward_summaries'] for layer in forward.get('layers',[])]
    assert len(layers)==1000 and all(x['finite'] and math.isfinite(x['correction_rms']) for x in layers)
    assert any(x['correction_rms']>0 for x in layers)
    return {'status':'passed','completed_blocks':audit['completed_blocks'],'compensated_calls':audit['compensated_calls'],
            'delta_derivation':audit['delta_derivation'],'rotation':rotation,'correction_rms_mean':sum(x['correction_rms'] for x in layers)/len(layers)}

def guard(req):
    root=Path(req['root']);directory=root/'innovation_handoff';directory.mkdir(exist_ok=True)
    status_path=directory/'partial_guard_status.json'
    with (directory/'partial_guard.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        atomic(directory/'partial_guard_pid.json',{'pid':os.getpid(),'start_ticks':Path('/proc',str(os.getpid()),'stat').read_text().rsplit(')',1)[1].split()[19],'uid':os.getuid()})
        expires=time.time()+24*3600
        ids=[j['id'] for j in req['base']['jobs'] if j['id'].endswith('_direction_gated')];assert len(ids)==10
        activated=False
        while time.time()<expires:
            states=read(root/'queue_state/state.json',{'jobs':{}})['jobs']
            if not activated:
                if not preceding_status(states,ids):
                    atomic(status_path,{'status':'waiting_direction_ten','unix':time.time(),'completed':sum(states.get(j,{}).get('status')=='completed' for j in ids),'total':10});time.sleep(60);continue
                prepared=activate_request({**req,'action':'prepare'})
                if prepared['status']=='not_ready':
                    atomic(status_path,{'status':'waiting_natural_exit','unix':time.time(),'snapshot':prepared});time.sleep(30);continue
                result=prepared if prepared['status']=='already_activated' else activate_request({**req,'action':'activate'})
                if result['status']=='not_ready':time.sleep(30);continue
                atomic(directory/'partial_pilots_active_manifest.json',result['manifest'])
                atomic(directory/'partial_pilots_activation.json',{k:v for k,v in result.items() if k!='manifest'})
                activated=True
            ids2=[j['id'] for j in req['pilots']['jobs']]
            failures=[j for j in ids2 if states.get(j,{}).get('status') in ('failed','failed_exhausted','blocked','invalid')]
            if failures:raise RuntimeError('partial pilots failed: '+','.join(failures))
            if all(states.get(j,{}).get('status')=='completed' for j in ids2):
                rows=[]
                for jid in ids2:
                    attempt=states[jid]['attempt_id'];audit=read(root/'audit/partial_temporal_rope'/f'{attempt}.json');row=verify_partial_audit(audit)
                    result=read(root/'queue_state/results'/f'{jid}.json');assert result['files']
                    for f in result['files']:
                        p=Path(f['path']);assert p.stat().st_size>0 and hashlib.sha256(p.read_bytes()).hexdigest()==f['sha256']
                    timing=read(root/'audit/timing'/f'{attempt}.json');assert len(timing['steps'])==20
                    rows.append({'id':jid,'audit':row,'sampler_wall_seconds':timing.get('sampler_wall_seconds'),'mean_sampling_step_seconds':timing.get('mean_sampling_step_seconds')})
                atomic(directory/'partial_pilots_verified.json',{'status':'passed','rows':rows,'unix':time.time()})
                atomic(status_path,{'status':'partial_pilots_complete_waiting_review','unix':time.time()});return
            atomic(status_path,{'status':'partial_pilots_running','unix':time.time(),'states':{j:states.get(j,{}).get('status','not_started') for j in ids2}});time.sleep(60)
        raise TimeoutError('bounded 24 hour partial handoff guard expired')
