
def host9_guard(req):
 root=Path(req['root']);d=root/'innovation_handoff';status=d/'coverage_v2_short0085_status.json';jid=req['pilots']['jobs'][0]['id']
 with (d/'coverage_v2_short0085.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  atomic(d/'coverage_v2_short0085_pid.json',{'pid':os.getpid(),'start_ticks':Path('/proc',str(os.getpid()),'stat').read_text().rsplit(')',1)[1].split()[19],'uid':os.getuid()})
  release=read(d/'coverage_v2_short0085_source_release.json');assert release['status']=='released_unsubmitted_to_host9' and release['job']['id']==jid
  verify_assets(req['assets'])
  # The only mutations occur with no old service/worker/API work and under the
  # existing host admission lock. The worker rechecks memory before allocation.
  with open('/tmp/h3-20261022-admission.lock','a') as admission:
   fcntl.flock(admission,fcntl.LOCK_EX)
   snap=snapshot(root);assert snap['ready_for_deployment'],snap
   assert digest(snap['manifest'])==digest(req['base'])
   raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True,timeout=20);ours=set()
   processes=[]
   for row in raw.splitlines():
    uuid,pid=[x.strip() for x in row.split(',')]
    try:uid=Path('/proc',pid).stat().st_uid
    except FileNotFoundError:continue
    if uid==os.getuid():ours.add(uuid)
    if uuid=='GPU-REPLACE-WITH-DEVICE-UUID':processes.append({'pid':int(pid),'uid':uid})
   assert len(ours)<2,'Own GPU quota already reached'
   rows=subprocess.check_output(['nvidia-smi','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'],text=True,timeout=20)
   uuid='GPU-REPLACE-WITH-DEVICE-UUID';free=next(float(x.split(',')[1]) for x in rows.splitlines() if x.split(',')[0].strip()==uuid)
   old=read(root/'shared_gpu_authorization.json');assert old['torch_allocator_cap_gib']==18 and old['comfy_reserve_vram_gib']==14 and old['minimum_free_mib']==25000
   policy={**old,'gpu_uuid':uuid,'gpu_index':3,'scope':'one real same-main10 short0085 temporal_coverage_v2 transferred from host41; original 73 frames prompt seed cache; max_attempts1','updated_unix':time.time(),'selection_reason':'GPU3 available under existing25GB shared budget; CPU33 tests and cacheSHA verified'}
   atomic(root/'shared_gpu_authorization.json',policy)
   manager=root/'scripts/manage_service.py';assert hashlib.sha256(manager.read_bytes()).hexdigest()==req['service_before_sha256']
   staged=root/'scripts/manage_service.coverage_v2.staged.py';raw=staged.read_bytes();assert hashlib.sha256(raw).hexdigest()==req['service_after_sha256'];compile(raw,str(manager),'exec');tmp=manager.with_name(manager.name+'.v2.tmp');tmp.write_bytes(raw);os.replace(tmp,manager)
   assert "'--max-attempts','1'" in (root/'scripts/host_worker.py').read_text()
   atomic(d/'coverage_v2_short0085_admission.json',{'gpu_index':3,'gpu_uuid':uuid,'free_mib':free,'existing_gpu_processes':processes,'own_gpu_count':len(ours),'memory_requirement_mib':25000,'status':'ready' if free>=25000 else 'waiting_budget','unix':time.time()})
  first=activate_request({**req,'action':'prepare'});assert first['status'] in ('prepared','already_activated'),first
  result=first if first['status']=='already_activated' else activate_request({**req,'action':'activate'});assert result['status'] in ('activated','already_activated'),result
  atomic(d/'coverage_v2_short0085_active_manifest.json',result['manifest'])
  expires=time.time()+48*3600
  while time.time()<expires:
   reap_finished_children();states=read(root/'queue_state/state.json',{'jobs':{}})['jobs'];entry=states.get(jid,{})
   if entry.get('status')=='completed':
    row=verify_outputs_and_timing(root,states,jid);row['audit']=check_v2(read(root/'audit/temporal_coverage_v2'/f"{row['attempt_id']}.json"));atomic(d/'coverage_v2_short0085_verified.json',{'status':'passed','rows':[row],'source_release':release,'unix':time.time()});atomic(status,{'status':'completed','unix':time.time()});return
   if entry.get('status') in ('failed','failed_exhausted','invalid','blocked'):
    atomic(status,{'status':'failed_single_attempt','job':entry,'unix':time.time()});return
   atomic(status,{'status':'running_or_waiting_admission','job_status':entry.get('status','not_started'),'worker':read(root/'worker_status.json',{}),'unix':time.time()});time.sleep(30)
  raise TimeoutError('Host9 one-job48h wait expired')

if __name__=='__main__':
 try:host9_guard(REQ)
 except Exception as e:
  atomic(Path(REQ['root'])/'innovation_handoff/coverage_v2_short0085_status.json',{'status':'failed','error':repr(e),'unix':time.time()});raise
