import json,pathlib,importlib.util,fcntl,os,signal,time,subprocess
r=pathlib.Path('/data4/research-user/h3_runs/benchmark_schedule_20261022');p=r/'scripts/coverage_v2_remaining8_handoff.py';s=importlib.util.spec_from_file_location('g',p);g=importlib.util.module_from_spec(s);s.loader.exec_module(g)
jid='innov41_short_0085_temporal_coverage_v2';receipt=r/'innovation_handoff/coverage_v2_short0085_source_release.json'
with (r/'innovation_handoff/activation.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert not receipt.exists(),'Already released; inspect receipt'
 snap=g.snapshot(r);g.validate_drain(snap)
 assert jid not in snap['states'] and jid not in {x['job_id'] for x in snap['api_queue'] or []},'Already selected at source'
 old=snap['manifest'];assert len(old['jobs'])==56
 job=next(j for j in old['jobs'] if j['id']==jid)
 guard=g.read(r/'innovation_handoff/coverage_v2_remaining8_pid.json');ident=g.identity(guard,str(p));assert ident['state']=='owned_alive'
 os.kill(guard['pid'],signal.SIGTERM)
 new={**old,'jobs':[j for j in old['jobs'] if j['id']!=jid]};g.atomic(r/'jobs.json',new)
 post=g.snapshot(r)
 if jid in post['states'] or jid in {x['job_id'] for x in post['api_queue'] or []}:
  g.atomic(r/'jobs.json',old);raise RuntimeError('Source selection raced removal; restored manifest, restart source monitor')
 rec={'status':'released_unsubmitted_to_host9','job':job,'destination':'H3_HOST_CONFIGURE_LOCALLY','destination_root':'/home/research-user/h3_runs/benchmark_schedule_20261022_host9a','destination_verified_receipt':'innovation_handoff/coverage_v2_short0085_verified.json','previous_guard_stopped':ident,'source_manifest_count':55,'source_manifest_sha256':g.digest(new),'worker':post['worker'],'service':post['service'],'api_queue':post['api_queue'],'unix':time.time()}
 g.atomic(receipt,rec);g.atomic(r/'innovation_handoff/coverage_v2_remaining8_status.json',{'status':'superseded_by_delegation_monitor','delegated_id':jid,'unix':time.time()})
with (r/'logs/coverage_v2_delegated_monitor.log').open('ab') as log:c=subprocess.Popen(['python3','-u',str(r/'scripts/coverage_v2_delegated_monitor.py')],cwd=r,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({k:v for k,v in rec.items() if k!='job'}));print('monitor_pid',c.pid)
