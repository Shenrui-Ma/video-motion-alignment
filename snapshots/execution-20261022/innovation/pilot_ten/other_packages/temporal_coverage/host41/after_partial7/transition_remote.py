import signal
R=Path('/data4/research-user/h3_runs/benchmark_schedule_20261022');di=R/'innovation_handoff';cancel=['innov41_short_0114_partial_temporal_rope','innov41_crouch__movie_man_4_partial_temporal_rope','innov41_long_0167_partial_temporal_rope'];current='innov41_short_0343_partial_temporal_rope'
with (di/'activation.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 before=snapshot(R);assert before['worker']=={'state':'owned_alive','pid':109058,'uid':1004,'start_ticks':'1218569'};assert before['service']['pid']==109103 and before['service']['state']=='owned_alive'
 assert [q['job_id'] for q in before['api_queue']]==[current]
 assert all(j not in before['states'] for j in cancel)
 timing=read(R/'audit/timing'/f"{before['states'][current]['attempt_id']}.json",{});assert len(timing.get('steps',[]))<20
 old=before['manifest'];assert len(old['jobs'])==46
 guards=[('coverage_pilots_pid.json',149136,'1563906','coverage_pilots_handoff.py'),('partial_remaining8_pid.json',105514,'1202597','partial_remaining8_handoff.py')]
 stopped=[]
 for name,pid,ticks,script in guards:
  rec=read(di/name);assert rec['pid']==pid and rec['start_ticks']==ticks and rec['uid']==1004;ident=identity(rec,str(R/'scripts'/script));assert ident['state']=='owned_alive'
  os.kill(pid,signal.SIGTERM);stopped.append({'pid':pid,'start_ticks':ticks,'script':script})
 new={**old,'jobs':[j for j in old['jobs'] if j['id'] not in cancel]};assert len(new['jobs'])==43
 atomic(di/'partial7_before_manifest.json',old);atomic(R/'jobs.json',new)
 after=snapshot(R);assert after['worker']==before['worker'] and after['service']==before['service'];assert all(j not in after['states'] for j in cancel);assert all(q['job_id'] not in cancel for q in (after['api_queue'] or []))
 receipt={'status':'user_cancelled_unsubmitted','reason':'User ends partial frequency sweep after already started jobs; proceed to other methods','cancelled_jobs':[j for j in old['jobs'] if j['id'] in cancel],'kept_partial_ids':[j['id'] for j in new['jobs'] if j['metadata'].get('method')=='partial_temporal_rope'],'old_count':46,'new_count':43,'stopped_cpu_guards':stopped,'worker_unchanged':after['worker'],'service_unchanged':after['service'],'active_api':after['api_queue'],'unix':time.time(),'no_failed_state_written':True}
 atomic(di/'partial7_user_scope_transition.json',receipt);atomic(di/'partial_remaining8_status.json',{'status':'ended_by_user_scope_change','remaining_unsubmitted_cancelled':cancel,'replacement':'coverage after retained 7 partial jobs','unix':time.time()});atomic(di/'coverage_pilots_status.json',{'status':'superseded_by_partial7_scope','unix':time.time()});print(json.dumps(receipt))
