def verify_completed(root,states,ids):
 rows=[]
 for jid in ids:
  if states.get(jid,{}).get('status')!='completed':raise ValueError('Job incomplete '+jid)
  attempt=states[jid]['attempt_id'];p=root/'audit/partial_temporal_rope'/f'{attempt}.json'
  row=verify_partial_audit(read(p));result=read(root/'queue_state/results'/f'{jid}.json');assert result['files']
  for f in result['files']:
   path=Path(f['path']);assert path.stat().st_size>0
   h=hashlib.sha256()
   with path.open('rb') as stream:
    for part in iter(lambda:stream.read(1048576),b''):h.update(part)
   assert h.hexdigest()==f['sha256']
  timing=read(root/'audit/timing'/f'{attempt}.json');assert len(timing['steps'])==20
  rows.append({'id':jid,'attempt_id':attempt,'audit':row,'files':result['files'],'sampler_wall_seconds':timing.get('sampler_wall_seconds'),'mean_sampling_step_seconds':timing.get('mean_sampling_step_seconds')})
 return rows

def guard(req):
 root=Path(req['root']);directory=root/'innovation_handoff';status=directory/'partial_remaining8_status.json'
 with (directory/'partial_remaining8.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  atomic(directory/'partial_remaining8_pid.json',{'pid':os.getpid(),'start_ticks':Path('/proc',str(os.getpid()),'stat').read_text().rsplit(')',1)[1].split()[19],'uid':os.getuid()})
  expires=time.time()+24*3600;activated=False;verified=False
  while time.time()<expires:
   states=read(root/'queue_state/state.json',{'jobs':{}})['jobs']
   if not activated:
    if not preceding_status(states,req['pilot_ids']):
     atomic(status,{'status':'waiting_two_pilots','unix':time.time(),'states':{i:states.get(i,{}).get('status') for i in req['pilot_ids']}});time.sleep(30);continue
    if not verified:
     rows=verify_completed(root,states,req['pilot_ids']);atomic(directory/'partial_remaining8_pilot_verification.json',{'status':'passed','rows':rows,'unix':time.time()});verified=True
    first=activate_request({**req,'action':'prepare'})
    if first['status']=='not_ready':
     atomic(status,{'status':'waiting_natural_exit','unix':time.time(),'snapshot':first});time.sleep(30);continue
    result=first if first['status']=='already_activated' else activate_request({**req,'action':'activate'})
    if result['status']=='not_ready':time.sleep(30);continue
    atomic(directory/'partial_remaining8_active_manifest.json',result['manifest']);activated=True
   ids=[j['id'] for j in req['pilots']['jobs']]
   failed=[j for j in ids if states.get(j,{}).get('status') in ('failed','failed_exhausted','blocked','invalid')]
   if failed:raise RuntimeError('Partial remaining8 failed: '+','.join(failed))
   if all(states.get(j,{}).get('status')=='completed' for j in ids):
    rows=verify_completed(root,states,ids);atomic(directory/'partial_remaining8_verified.json',{'status':'passed','rows':rows,'unix':time.time()});atomic(status,{'status':'completed','count':8,'unix':time.time()});return
   atomic(status,{'status':'running','unix':time.time(),'states':{j:states.get(j,{}).get('status','not_started') for j in ids}});time.sleep(60)
  raise TimeoutError('Partial remaining8 24h guard expired')
