import pathlib,importlib.util,fcntl,os,time
r=pathlib.Path('/data4/research-user/h3_runs/benchmark_schedule_20261022');s=importlib.util.spec_from_file_location('g',r/'scripts/coverage_v2_remaining8_handoff.py');g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
d=r/'innovation_handoff';jid='innov41_short_0085_temporal_coverage_v2';ids=[j['id'] for j in g.REQ['pilots']['jobs']];assert len(ids)==8
with (d/'coverage_v2_returned_monitor.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 g.atomic(d/'coverage_v2_returned_monitor_pid.json',{'pid':os.getpid(),'start_ticks':pathlib.Path('/proc',str(os.getpid()),'stat').read_text().rsplit(')',1)[1].split()[19],'uid':os.getuid()})
 try:
  while True:
   states=g.read(r/'queue_state/state.json',{'jobs':{}})['jobs']
   completed=g.preceding_status(states,ids)
   status={'status':'eight_source_jobs_running','states':{j:states.get(j,{}).get('status','not_started') for j in ids},'returned_job_id':jid,'job_returned_from_host':'H3_HOST_CONFIGURE_LOCALLY','source_return_receipt':str(d/'coverage_v2_short0085_returned.json'),'unix':time.time()}
   if completed:
    rows=g.verify_completed(r,states,ids);g.atomic(d/'coverage_v2_all_remaining_eight_verified.json',{'status':'passed','rows':rows,'returned_job_id':jid,'unix':time.time()});status['status']='all_eight_complete_after_host9_failed_attempt_return';g.atomic(d/'coverage_v2_returned_monitor_status.json',status);break
   g.atomic(d/'coverage_v2_returned_monitor_status.json',status);time.sleep(60)
 except Exception as e:
  g.atomic(d/'coverage_v2_returned_monitor_status.json',{'status':'failed','error':repr(e),'unix':time.time()});raise
