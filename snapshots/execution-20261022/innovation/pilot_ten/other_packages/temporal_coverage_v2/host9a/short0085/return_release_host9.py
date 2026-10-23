import pathlib,json,importlib.util,fcntl,time
r=pathlib.Path('/home/research-user/h3_runs/benchmark_schedule_20261022_host9a');p=r/'scripts/short0177_pair_guard.py';s=importlib.util.spec_from_file_location('g',p);g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
jid='innov41_short_0085_temporal_coverage_v2'
with (r/'innovation_handoff/activation.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 snap=g.snapshot(r);assert snap['ready_for_deployment'],{k:v for k,v in snap.items() if k not in ('manifest','states')}
 assert snap['states'][jid]['status']=='failed'
 old=snap['manifest'];assert sum(j['id']==jid for j in old['jobs'])==1
 g.atomic(r/'jobs.json',{**old,'jobs':[j for j in old['jobs'] if j['id']!=jid]})
 rec={'status':'failed_host9_attempt_released_to_host41','job_id':jid,'reason':'18GiB allocator OOM at first block MLP fc1 full output allocation472MiB; routing solved1; no completed step','failed_attempt_preserved':True,'retry_same_host_config':False,'worker':snap['worker'],'service':snap['service'],'locks':snap['locks'],'api_queue':snap['api_queue'],'unix':time.time()};g.atomic(r/'innovation_handoff/coverage_v2_short0085_return_release.json',rec);print(json.dumps(rec))
