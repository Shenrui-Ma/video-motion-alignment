def check_v2(a):
 assert a['schema']=='h3-temporal-coverage-v2' and a['status']!='failed'
 assert a['completed_forward_calls']==20 and a['completed_calls']==1000 and a['native_override_calls']==1000
 assert a['alpha']==.25 and a['step_interval_half_open']==[0,20] and a['block_interval_half_open']==[0,50]
 c=a['coverage_config'];assert c['solver']=='damped_newton_cpu_float64' and c['fallback_policy']=='same_time_weak' and c['iterations']==64 and c['tolerance']==.0002
 calls=a['coverage_calls'];assert len(calls)==1000 and len({(x['forward'],x['block']) for x in calls})==1000
 solved=[x for x in calls if x.get('routing_solved')];fallback=[x for x in calls if x.get('reason')=='same_time_fallback']
 assert len(solved)+len(fallback)==1000 and a['routed_calls']==1000
 assert a['coverage_solved_calls']==len(solved) and a['same_time_fallback_calls']==len(fallback)
 assert solved,'No successfully solved coverage calls'
 for x in calls:assert x['applied'] and x['solver_iterations']<=64 and math.isfinite(x['solver_seconds']) and x['solver_seconds']>=0
 for x in solved:assert x['row_error']<=c['tolerance'] and x['column_error']<=c['tolerance']
 layers=[l for f in a['forward_summaries'] for l in f.get('layer_stats',[])];assert len(layers)==1000
 assert all(x['finite'] and math.isfinite(x['correction_ratio']) for x in layers)
 assert any(x['correction_ratio']>0 for x in layers)
 return {'status':'passed','solved_calls':len(solved),'same_time_fallback_calls':len(fallback),'solved_fraction':len(solved)/1000,'solver_seconds_total':a['solver_wall_seconds'],'solver_iterations_mean':sum(x['solver_iterations'] for x in calls)/1000,'solver_iterations_max':max(x['solver_iterations'] for x in calls),'fallback_reasons':{k:sum(x.get('fallback_reason')==k for x in fallback) for k in {x.get('fallback_reason') for x in fallback}},'coverage_config':c}

def install_service_at_boundary(req):
 root=Path(req['root']);change=req['service_change'];path=Path(change['path'])
 with (root/'innovation_handoff/activation.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  snap=snapshot(root)
  if not snap['ready_for_deployment']:return False
  assert snap['manifest_sha256'] in (digest(req['base']),digest(merge_manifest(req['base'],req['pilots'])))
  oldhash=hashlib.sha256(path.read_bytes()).hexdigest()
  if oldhash==change['after_sha256']:return True
  assert oldhash==change['before_sha256'],'Service script changed outside handoff'
  staged=Path(change['staged_path']);raw=staged.read_bytes();assert hashlib.sha256(raw).hexdigest()==change['after_sha256']
  compile(raw,str(path),'exec')
  temp=path.with_name(path.name+'.coverage_v2.tmp');temp.write_bytes(raw);os.replace(temp,path)
  atomic(root/'innovation_handoff/coverage_v2_service_installed.json',{'status':'installed_at_natural_exit','before':oldhash,'after':change['after_sha256'],'unix':time.time()});return True

def guard(req):
 root=Path(req['root']);d=root/'innovation_handoff';status=d/'coverage_v2_status.json'
 with (d/'coverage_v2.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  atomic(d/'coverage_v2_pid.json',{'pid':os.getpid(),'start_ticks':Path('/proc',str(os.getpid()),'stat').read_text().rsplit(')',1)[1].split()[19],'uid':os.getuid()})
  deadline=time.time()+48*3600;activated=False;verified=False
  while time.time()<deadline:
   reap_finished_children();states=read(root/'queue_state/state.json',{'jobs':{}})['jobs']
   if not activated:
    if any(states.get(j,{}).get('status') in ('failed','failed_exhausted','invalid') for j in req['prerequisite_ids']):raise RuntimeError('Prerequisite failed')
    if not all(states.get(j,{}).get('status')=='completed' for j in req['prerequisite_ids']):
     atomic(status,{'status':'waiting_running_v1_job','unix':time.time()});time.sleep(30);continue
    if not verified:
     rows=[]
     for j in req['prerequisite_ids']:
      row=verify_outputs_and_timing(root,states,j);a=read(root/'audit/temporal_coverage'/f"{row['attempt_id']}.json")
      assert a['schema']=='h3-temporal-coverage-v1' and a['completed_forward_calls']==20 and a['completed_calls']==1000
      row['old_routed_calls']=a['routed_calls'];rows.append(row)
     atomic(d/'coverage_v2_prerequisite_verified.json',{'rows':rows,'unix':time.time()});verified=True
    if not install_service_at_boundary(req):atomic(status,{'status':'waiting_natural_exit','unix':time.time()});time.sleep(30);continue
    result=activate_request({**req,'action':'prepare'})
    if result['status']=='not_ready':time.sleep(30);continue
    if result['status']!='already_activated':result=activate_request({**req,'action':'activate'})
    if result['status']=='not_ready':time.sleep(30);continue
    activated=True;atomic(d/'coverage_v2_active_manifest.json',result['manifest'])
   ids=[j['id'] for j in req['pilots']['jobs']]
   if any(states.get(j,{}).get('status') in ('failed','failed_exhausted','invalid') for j in ids):raise RuntimeError('V2 pilot failed')
   if all(states.get(j,{}).get('status')=='completed' for j in ids):
    rows=[]
    for j in ids:
     row=verify_outputs_and_timing(root,states,j);row['audit']=check_v2(read(root/'audit/temporal_coverage_v2'/f"{row['attempt_id']}.json"));rows.append(row)
    atomic(d/'coverage_v2_verified.json',{'status':'passed','rows':rows,'unix':time.time()});atomic(status,{'status':'two_pilots_complete_waiting_review','unix':time.time()});return
   atomic(status,{'status':'pilots_running','states':{j:states.get(j,{}).get('status','not_started') for j in ids},'unix':time.time()});time.sleep(60)
  raise TimeoutError('V2 pilot guard expired')
