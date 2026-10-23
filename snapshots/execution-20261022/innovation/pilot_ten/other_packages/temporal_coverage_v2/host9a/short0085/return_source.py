import pathlib,json,importlib.util,fcntl,os,signal,time,subprocess
r=pathlib.Path('/data4/research-user/h3_runs/benchmark_schedule_20261022');s=importlib.util.spec_from_file_location('g',r/'scripts/coverage_v2_remaining8_handoff.py');g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
release=json.loads('{"status": "failed_host9_attempt_released_to_host41", "job_id": "innov41_short_0085_temporal_coverage_v2", "reason": "18GiB allocator OOM at first block MLP fc1 full output allocation472MiB; routing solved1; no completed step", "failed_attempt_preserved": true, "retry_same_host_config": false, "worker": {"state": "exited", "pid": 40079}, "service": {"state": "exited", "pid": 40086}, "locks": {"worker.lock": false, "queue_state/runner.lock": false}, "api_queue": null, "unix": 1792684095.5316021}');jid=release['job_id'];assert release['status']=='failed_host9_attempt_released_to_host41'
with (r/'innovation_handoff/activation.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 snap=g.snapshot(r);g.validate_drain(snap);assert jid not in snap['states'] and jid not in {j['id'] for j in snap['manifest']['jobs']}
 mon=g.read(r/'innovation_handoff/coverage_v2_delegated_monitor_pid.json');ident=g.identity(mon,str(r/'scripts/coverage_v2_delegated_monitor.py'));assert ident['state']=='owned_alive',ident;os.kill(mon['pid'],signal.SIGTERM)
 source=g.read(r/'innovation_handoff/coverage_v2_short0085_source_release.json');job=source['job'];assert job['id']==jid
 old=snap['manifest'];new={**old,'jobs':old['jobs']+[job]};g.atomic(r/'jobs.json',new)
 rec={'status':'returned_to_host41_after_host9_oom','job_id':jid,'host9_release':release,'manifest_count':len(new['jobs']),'manifest_sha256':g.digest(new),'worker':snap['worker'],'service':snap['service'],'api_queue':snap['api_queue'],'previous_monitor':ident,'unix':time.time()};g.atomic(r/'innovation_handoff/coverage_v2_short0085_returned.json',rec)
with (r/'logs/coverage_v2_returned_monitor.log').open('ab') as log:c=subprocess.Popen(['python3','-u',str(r/'scripts/coverage_v2_returned_monitor.py')],cwd=r,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
rec['monitor_pid']=c.pid;print(json.dumps(rec))
