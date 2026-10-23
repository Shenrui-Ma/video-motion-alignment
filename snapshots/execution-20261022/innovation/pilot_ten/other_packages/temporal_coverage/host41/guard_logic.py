def verify_outputs_and_timing(root,states,jid):
 attempt=states[jid]['attempt_id'];result=read(root/'queue_state/results'/f'{jid}.json');assert result['files']
 for f in result['files']:
  p=Path(f['path']);assert p.stat().st_size>0
  h=hashlib.sha256()
  with p.open('rb') as stream:
   for chunk in iter(lambda:stream.read(1048576),b''):h.update(chunk)
  assert h.hexdigest()==f['sha256']
 timing=read(root/'audit/timing'/f'{attempt}.json');assert len(timing['steps'])==20 and timing['passed'] and timing['status']=='complete'
 for k in ('sampler_wall_seconds','mean_sampling_step_seconds'):assert math.isfinite(timing[k]) and timing[k]>0
 return {'id':jid,'attempt_id':attempt,'files':result['files'],'sampler_wall_seconds':timing['sampler_wall_seconds'],'mean_sampling_step_seconds':timing['mean_sampling_step_seconds']}

def verify_coverage_audit(a):
 assert a['schema']=='h3-temporal-coverage-v1' and a['status']!='failed'
 assert a['completed_forward_calls']==20 and a['completed_calls']==1000 and a['native_override_calls']==1000
 assert a['alpha']==.25 and a['step_interval_half_open']==[0,20] and a['block_interval_half_open']==[0,50]
 c=a['coverage_config'];expected={'radius':2,'entropy':.5,'temporal_penalty':.25,'iterations':128,'tolerance':.0002,'min_quality_span':.001,'minimum_mean_gap':0.}
 assert all(c[k]==v for k,v in expected.items())
 calls=a['coverage_calls'];assert len(calls)==1000 and len({(r['forward'],r['block']) for r in calls})==1000
 applied=[r for r in calls if r['applied']];assert len(applied)==a['routed_calls']>0
 for r in applied:
  assert r['reason'] in ('balanced','identity')
  assert all(math.isfinite(r[k]) for k in ('row_error','column_error','quality_span','transport_fraction'))
  assert r['row_error']<=c['tolerance'] and r['column_error']<=c['tolerance']
 layers=[l for f in a['forward_summaries'] for l in f.get('layer_stats',[])];assert len(layers)==len(applied)
 assert all(l['finite'] and math.isfinite(l['correction_ratio']) for l in layers)
 assert any(l['correction_ratio']>0 for l in layers)
 reasons={}
 for r in calls:reasons[r['reason']]=reasons.get(r['reason'],0)+1
 return {'status':'passed','completed_forward_calls':20,'completed_calls':1000,'effective_routed_calls':len(applied),'fallback_and_route_reasons':reasons,'coverage_config':c,'mean_sampled_correction_ratio':sum(l['correction_ratio'] for l in layers)/len(layers)}

def guard(req):
 root=Path(req['root']);di=root/'innovation_handoff';status=di/'coverage_pilots_status.json'
 with (di/'coverage_pilots.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  atomic(di/'coverage_pilots_pid.json',{'pid':os.getpid(),'start_ticks':Path('/proc',str(os.getpid()),'stat').read_text().rsplit(')',1)[1].split()[19],'uid':os.getuid()})
  deadline=time.time()+48*3600;verified=False;activated=False
  while time.time()<deadline:
   reap_finished_children()
   states=read(root/'queue_state/state.json',{'jobs':{}})['jobs']
   if not activated:
    if not preceding_status(states,req['prerequisite_ids']):
     atomic(status,{'status':'waiting_partial_ten','completed':sum(states.get(j,{}).get('status')=='completed' for j in req['prerequisite_ids']),'total':10,'unix':time.time()});time.sleep(60);continue
    if not verified:
     rows=[]
     for jid in req['prerequisite_ids']:
      row=verify_outputs_and_timing(root,states,jid);row['audit']=verify_partial_audit(read(root/'audit/partial_temporal_rope'/f"{row['attempt_id']}.json"));rows.append(row)
     atomic(di/'coverage_partial_prerequisites_verified.json',{'status':'passed','rows':rows,'unix':time.time()});verified=True
    first=activate_request({**req,'action':'prepare'})
    if first['status']=='not_ready':atomic(status,{'status':'waiting_natural_exit','snapshot':first,'unix':time.time()});time.sleep(30);continue
    result=first if first['status']=='already_activated' else activate_request({**req,'action':'activate'})
    if result['status']=='not_ready':time.sleep(30);continue
    atomic(di/'coverage_pilots_active_manifest.json',result['manifest']);activated=True
   ids=[j['id'] for j in req['pilots']['jobs']]
   if preceding_status(states,ids):
    rows=[]
    for jid in ids:
     row=verify_outputs_and_timing(root,states,jid);row['audit']=verify_coverage_audit(read(root/'audit/temporal_coverage'/f"{row['attempt_id']}.json"));rows.append(row)
    atomic(di/'coverage_pilots_verified.json',{'status':'passed','rows':rows,'unix':time.time()});atomic(status,{'status':'two_pilots_complete_waiting_review','unix':time.time()});return
   atomic(status,{'status':'pilots_running','states':{j:states.get(j,{}).get('status','not_started') for j in ids},'unix':time.time()});time.sleep(60)
  raise TimeoutError('Coverage pilot guard 48h timeout')
