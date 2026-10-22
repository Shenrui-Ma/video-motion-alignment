"""Preserve two hardware-failed segments and run only remaining global on GPU0."""
import hashlib,io,json,shutil,subprocess,sys,tarfile,time
from pathlib import Path
P=Path(__file__).resolve().parents[1];H=P/'final_global_host41';S=P/'recovery_host41/cases/long_0039';T=H/'cases/long_0039'
OLD='/data4/researcher/h3_runs/guidance_schedule_r150_recovery_host41_20261021/cases/long_0039';NEW='/data4/researcher/h3_runs/guidance_schedule_r150_final_global_host41_20261021/cases/long_0039';HOST='H3_SERVER_B';SEG='book_final_global_host41';ATT='root_r150_book_recovery_host41_attempt1';SEAL='70023888e520ac448b9bab5ec3d2324677bb61a0584ef1ad375d7db9fb1842f8'
def rd(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def wr(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
assert not T.exists() and sha(S/'deploy_manifest.json')==SEAL
for rel,v in rd(S/'deploy_manifest.json')['files'].items():
 assert sha(S/rel)==v['sha256'],rel
 q=T/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(S/rel,q)
for name in ['producer','logs','processes','input','output','temp','user','custom_nodes','audit/router','audit/x0']:(T/name).mkdir(parents=True,exist_ok=True)
r=rd(T/'configs/runtime.json');r.update(remote_root=NEW,port=8654,gpu_uuid='GPU-REDACTED',gpu_index=0,expected_gpu_index=0,profile_scope='Only original blue-book global; GPU7 hardware failure recovery');wr(T/'configs/runtime.json',r)
q=rd(T/'configs/gpu_quarantine.json');q['known_requires_reset'].append({'index':7,'uuid':'GPU-REDACTED'});wr(T/'configs/gpu_quarantine.json',q)
science=rd(T/'configs/scientific_contract.json');runs=science['case_order'];global_run=runs[-1]
for f in (T/'configs/graphs').glob('*.json'):f.write_text(f.read_text().replace(OLD,NEW))
for rel in ['scripts/r132_contract.py','analysis/postrun/verify_schedule.py','audit/root_run_batch.py']:
 f=T/rel;s=f.read_text().replace('book_late_split_global_host41',SEG)
 if rel.endswith('r132_contract.py'):
  s=s.replace('jobs[r]["arm"] in ("late", "split", "global_weak")','jobs[r]["arm"] == "global_weak"').replace('"allowed_roles": ["late", "split", "global_weak"]','"allowed_roles": ["global_weak"]').replace('len(selected) == 3','len(selected) == 1').replace('only original late/split/global_weak','only original global_weak')
 f.write_text(s)
wr(T/'configs/execution_segment.json',{'schema':'r149-execution-segment-v1','segment_id':SEG,'allowed_runs':[global_run],'allowed_roles':['global_weak'],'all_other_registered_runs_external':True});wr(T/'configs/queue.json',{'jobs':[global_run],'finalize':True})
f=T/'tests/test_schedule.py';s=f.read_text().replace('len(jobs), 3','len(jobs), 1').replace('["late", "split", "global_weak"])','["global_weak"])').replace('run_queue.subprocess.run.call_count, 4','run_queue.subprocess.run.call_count, 2');f.write_text(s)
query='''
from pathlib import Path
import json,hashlib,sys,time
r=Path(OLD);sys.path.insert(0,str(r/'scripts'));import service
rd=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
d=rd(r/'audit'/ATT/'HARDWARE_FAILURE_EXIT_CHECK.json');assert d['all_recorded_generations_exited'] and d['CUDA_allocation_absent'] is None and d['GPU_requires_reset']
gens={}
for row in d['recorded_processes']:
 now=service.current_identity(row['pid']);assert now!=row['expected_identity'];gens[row['file']]={'pid':row['pid'],'expected_identity':row['expected_identity'],'actual_identity':now,'generation_absent':True}
rels=['deploy_manifest.json','processes/service.json','audit/ATTEMPT1_LAUNCH.json','audit/'+ATT+'/FAILURE.json','audit/'+ATT+'/CLEANUP_FAILURE.json','audit/'+ATT+'/HARDWARE_FAILURE_EXIT_CHECK.json','audit/'+ATT+'/CAPACITY_MONITOR_EXIT.json','logs/'+RUNS[-1]+'_job.json','audit/router/'+RUNS[-1]+'.json']+['analysis/postrun/long_0039/'+x+'_GATE.json' for x in RUNS[1:3]]
files={x:{'path':str(r/x),'sha256':sha(r/x),'content':rd(r/x)} for x in rels}
assert files['deploy_manifest.json']['sha256']==SEAL
assert files['logs/'+RUNS[-1]+'_job.json']['content']['status']=='error'
owner=rd(r/'processes/service.json')
for run in RUNS[1:3]:
 g=files['analysis/postrun/long_0039/'+run+'_GATE.json']['content'];assert g['passed'] and g['producer_seal_sha256']==SEAL and g['service_owner']==owner
assert not(r/'audit'/ATT/'COMPLETE.json').exists()
print(json.dumps({'files':files,'generations':gens,'owner':owner,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'observed_unix':time.time()}))
'''
q='\n'.join(k+'='+repr(v) for k,v in {'OLD':OLD,'ATT':ATT,'RUNS':runs,'SEAL':SEAL}.items())+'\n'+query
rr=subprocess.run(['ssh',HOST,'python3 -'],input=q,text=True,capture_output=True,check=True);ev=json.loads(rr.stdout);wr(H/'SECOND_SOURCE_EVIDENCE.json',ev)
parent=rd(P/'recovery_host41/MIGRATION_MANIFEST.json');science_meta=parent['science'].copy();science_meta['target_graph_sha256']={c['arm']:sha(T/'configs/graphs'/(c['run_id']+'.json')) for c in science['cases']}
m={'schema':'r150-three-segment-hardware-recovery-migration-v1','source_id':'long_0039','created_unix':time.time(),'segment_order':['host41_prefix','host41_middle','host41_global'],'segments':{'host41_prefix':parent['segments']['host41_prefix'],'host41_middle':{'host':HOST,'remote_root':OLD,'roles':['late','split'],'run_ids':runs[1:3],'producer_seal_sha256':SEAL,'service_owner':ev['owner'],'attempt':ATT,'stop_kind':'hardware_failure'},'host41_global':{'host':HOST,'remote_root':NEW,'roles':['global_weak'],'run_ids':[global_run],'segment_id':SEG,'actual_producer_seal_binding':'MIGRATION_DEPLOYMENT.json','aggregate_gate':'analysis/postrun/long_0039/SCHEDULE_RUNTIME_GATE.json','aggregate_schema':'r149-fixed-schedule-segment-gate-v1','COMPLETE_schema':'r149-schedule-segment-completion-v1'}},'prior_hardware_recovery':{key:{'file':str(P/'recovery_host41'/name),'sha256':sha(P/'recovery_host41'/name)} for key,name in [('manifest','MIGRATION_MANIFEST.json'),('prefix_release','PREFIX_PARTIAL_RELEASE.json'),('source_evidence','SOURCE_EVIDENCE.json')]},'science':science_meta,'boundary':{'stop_kind':'hardware_failure','old_segments_COMPLETE_remain_absent':True,'same_persistent_service_across_segments':False},'failure':{'failed_run':global_run,'completed_callbacks':10,'routed_calls':526,'failed_sampler_seconds':620.3294716990022,'GPU7_requires_reset':True,'replay_from_original_noise':True}}
wr(H/'MIGRATION_MANIFEST.json',m);wr(T/'configs/MIGRATION_MANIFEST.json',m)
partial={'schema':'r149-schedule-hardware-partial-release-v1','passed':True,'source_id':'long_0039','segment_id':'host41_middle','stop_kind':'hardware_failure','migration_manifest_sha256':sha(H/'MIGRATION_MANIFEST.json'),'source_root':OLD,'producer_seal_sha256':SEAL,'service_owner':ev['owner'],'completed_runs':runs[1:3],'completed_roles':['late','split'],'remaining_runs':[global_run],'registered_generations':ev['generations'],'process_generation_absent':True,'CUDA_allocation_absent':None,'release_state':'processes_exited_gpu_unqueryable','gpu_health':'requires_reset','gpu_uuid':ev['owner']['gpu_uuid'],'original_segment_COMPLETE':False,'evidence':{k:{'path':v['path'],'sha256':v['sha256']} for k,v in ev['files'].items()},'created_unix':ev['observed_unix']}
wr(H/'SECOND_PARTIAL_RELEASE.json',partial);wr(T/'producer/SECOND_PARTIAL_RELEASE.json',partial)
for rel in ['configs/scientific_contract.json','configs/CONDITION_CACHE.json','design/conditioning.json']:assert sha(T/rel)==sha(S/rel)
for rel in rd(S/'configs/numerical_reuse.json'):assert sha(T/rel)==sha(S/rel)
for name in ['check_fresh_paths.py','watch_queue.py']:shutil.copy2(S/'producer'/name,T/'producer'/name)
sys.path.insert(0,str(T/'scripts'));import r132_contract,execution_gate
assert r132_contract.registry()[1]==[global_run];execution_gate.seal(T);seal=sha(T/'deploy_manifest.json')
deployment={'schema':'r150-three-segment-hardware-recovery-deployment-v1','source_id':'long_0039','migration_manifest_sha256':sha(H/'MIGRATION_MANIFEST.json'),'second_partial_release_sha256':sha(H/'SECOND_PARTIAL_RELEASE.json'),'segments':{k:{x:y for x,y in v.items() if x in ['host','remote_root','roles','run_ids','producer_seal_sha256']} for k,v in m['segments'].items()},'created_unix':time.time()};deployment['segments']['host41_global']['producer_seal_sha256']=seal;wr(H/'MIGRATION_DEPLOYMENT.json',deployment)
s=(S/'producer/launch_recovery.py').read_text().replace(SEAL,seal).replace(ATT,'root_r150_book_final_global_host41_attempt1').replace('/guidance_schedule_r150_20261021/cases/long_0039','/guidance_schedule_r150_recovery_host41_20261021/cases/long_0039').replace('PREFIX_PARTIAL_RELEASE.json','SECOND_PARTIAL_RELEASE.json').replace('root_r150_long0039_host41_attempt1',ATT).replace("'-i','7'","'-i','0'").replace("parts[0]=='7'","parts[0]=='0'").replace('GPU7 free','GPU0 free').replace('GPU7 requires','GPU0 requires').replace('source_gpu6_release','source_gpu7_release').replace('blue-book late/split/global recovery on healthy GPU7; original early retained','blue-book remaining global on healthy GPU0; original early/late/split retained');(T/'producer/launch_recovery.py').write_text(s)
wr(T/'producer/SCIENTIFIC_EQUIVALENCE.json',{'passed':True,'numerical_modules_byte_identical':True,'scientific_contract_byte_identical':True,'conditioning_and_noise_unchanged':True,'actual_registry':[global_run],'previous_seal':SEAL,'new_seal':seal})
buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode='w:gz') as tar:
 for f in T.rglob('*'):
  if f.is_file() and '__pycache__' not in f.parts:tar.add(f,arcname=str(f.relative_to(T)))
setup="import pathlib,tarfile,sys; r=pathlib.Path("+repr(NEW)+"); r.mkdir(parents=True,exist_ok=False); tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz').extractall(r)"
import shlex
subprocess.run(['ssh',HOST,'python3 -c '+shlex.quote(setup)],input=buf.getvalue(),check=True)
print(json.dumps({'root':str(T),'remote_root':NEW,'seal':seal,'manifest':sha(H/'MIGRATION_MANIFEST.json'),'deployment':sha(H/'MIGRATION_DEPLOYMENT.json')}))
