"""Recover only unfinished blue-book schedules after the recorded GPU6 driver failure."""
import hashlib,json,shutil,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parents[1]; S=P/'cases/long_0039'; H=P/'recovery_host41'; T=H/'cases/long_0039'
R149=P.parent/'h3-guidance-schedule-r149-20261020'
TEMPLATE=R149/'final_global_host41/cases/short_0358'
HOST='H3_SERVER_B'; OLD='/data4/researcher/h3_runs/guidance_schedule_r150_20261021/cases/long_0039'; NEW='/data4/researcher/h3_runs/guidance_schedule_r150_recovery_host41_20261021/cases/long_0039'
SEG='book_late_split_global_host41'; ATT='root_r150_long0039_host41_attempt1'; SEAL='3c2740dae3c8637f0c4813a20c8fb718cfb1f536ac2d9b5feadb07f3c2a1f997'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def replace1(s,a,b):
 assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
assert not T.exists();assert sha(S/'deploy_manifest.json')==SEAL
for rel,item in read(S/'deploy_manifest.json')['files'].items():
 assert sha(S/rel)==item['sha256'];out=T/rel;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(S/rel,out)
for d in ('producer','processes','logs','input','output','temp','user','custom_nodes','audit/router','audit/x0'):(T/d).mkdir(parents=True,exist_ok=True)
r=read(T/'configs/runtime.json');r.update(remote_root=NEW,gpu_uuid='GPU-REDACTED',gpu_index=7,expected_gpu_index=7,port=8654,profile_scope='Original late/split/global; GPU6 hardware failure recovery')
write(T/'configs/runtime.json',r)
q=read(T/'configs/gpu_quarantine.json');q['known_requires_reset'].append({'index':6,'uuid':'GPU-REDACTED'});assert {x['index'] for x in q['known_requires_reset']}=={4,5,6};write(T/'configs/gpu_quarantine.json',q)
sci=read(T/'configs/scientific_contract.json');allruns=sci['case_order'];selected=allruns[1:];roles=['late','split','global_weak']
p=T/'scripts/r132_contract.py';text=p.read_text();text=replace1(text,'RUN_ID = science()["case_order"][0]','RUN_ID = read(ROOT / "configs/execution_segment.json")["allowed_runs"][0]');text=replace1(text,'def registry(root=ROOT):','def full_registry(root=ROOT):');text=replace1(text,'    require(read(root / "configs/queue.json") == {"jobs": order, "finalize": True}, "queue changed")\n','')
seg=(R149/'recovery_host41/cases/short_0358/scripts/r132_contract.py').read_text().split('def registry(root=ROOT):',1)[1].split('\ndef validate_job(',1)[0]
seg=seg.replace('("split", "global_weak")','("late", "split", "global_weak")').replace('["split", "global_weak"]','["late", "split", "global_weak"]').replace('drink_split_global_host41',SEG).replace('len(selected) == 2','len(selected) == 3').replace('split/global_weak','late/split/global_weak')
text=replace1(text,'\ndef validate_job(','\ndef registry(root=ROOT):'+seg+'\ndef validate_job(');p.write_text(text)
write(T/'configs/execution_segment.json',{'schema':'r149-execution-segment-v1','segment_id':SEG,'allowed_runs':selected,'allowed_roles':roles,'all_other_registered_runs_external':True});write(T/'configs/queue.json',{'jobs':selected,'finalize':True})
for run in allruns:
 p=T/'configs/graphs'/(run+'.json');p.write_text(p.read_text().replace(OLD,NEW))
p=T/'audit/root_run_batch.py';p.write_text((TEMPLATE/'audit/root_run_batch.py').read_text().replace('short_0358','long_0039').replace('drink_final_global_host41',SEG))
p=T/'analysis/postrun/verify_schedule.py';p.write_text((TEMPLATE/'analysis/postrun/verify_schedule.py').read_text().replace('drink_final_global_host41',SEG))
query='''
import hashlib,json,pathlib,sys,time,subprocess
r=pathlib.Path(OLD);sys.path.insert(0,str(r/'scripts'));import service
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
owner=read(r/'processes/service.json');diag=read(r/'audit'/ATT/'HARDWARE_FAILURE_EXIT_CHECK.json')
assert diag['all_recorded_generations_exited'] and diag['GPU6_CUDA_allocation_absent'] is None
assert 'GPU requires reset' in diag['devices']['6']['health']
gens={}
for row in diag['exact_process_checks']:
 rel=str(pathlib.Path(row['file']).relative_to(r));current=service.current_identity(row['pid'])
 assert current is None, (rel,current)
 gens[rel]={'pid':row['pid'],'expected_identity':row['expected_identity'],'actual_identity':current,'generation_absent':True}
rels=['deploy_manifest.json','processes/service.json','audit/ATTEMPT1_LAUNCH.json','audit/'+ATT+'/FAILURE.json','audit/'+ATT+'/CLEANUP_FAILURE.json','audit/'+ATT+'/HARDWARE_FAILURE_EXIT_CHECK.json','audit/'+ATT+'/CAPACITY_MONITOR_EXIT.json','logs/'+RUNS[1]+'_job.json','audit/router/'+RUNS[1]+'.json','analysis/postrun/long_0039/'+RUNS[0]+'_GATE.json']
files={rel:{'path':str(r/rel),'sha256':sha(r/rel),'content':read(r/rel)} for rel in rels}
assert files['deploy_manifest.json']['sha256']==SEAL
assert files['logs/'+RUNS[1]+'_job.json']['content']['status']=='error'
for run in RUNS[2:]:assert not(r/'logs'/(run+'_job.json')).exists()
raw=subprocess.run(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,used_memory','--format=csv,noheader,nounits'],text=True,capture_output=True,timeout=15)
assert raw.returncode==0
print(json.dumps({'owner':owner,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'generations':gens,'files':files,'cuda_raw':raw.stdout,'observed_unix':time.time()}))
'''
q='\n'.join(k+'='+repr(v) for k,v in {'OLD':OLD,'ATT':ATT,'RUNS':allruns,'SEAL':SEAL}.items())+'\n'+query
rr=subprocess.run(['ssh','-o','BatchMode=yes',HOST,'python3 -'],input=q,text=True,capture_output=True)
if rr.returncode:raise RuntimeError(rr.stderr)
ev=json.loads(rr.stdout);write(H/'SOURCE_EVIDENCE.json',ev)
g=ev['files']['analysis/postrun/long_0039/'+allruns[0]+'_GATE.json']['content'];assert g['passed'] and g['producer_seal_sha256']==SEAL and g['service_owner']==ev['owner']
manifest={'schema':'r149-hardware-recovery-migration-v1','source_id':'long_0039','stop_kind':'hardware_failure','created_unix':time.time(),
 'segments':{'host41_prefix':{'host':HOST,'remote_root':OLD,'roles':['early'],'run_ids':allruns[:1],'attempt':ATT,'producer_seal_sha256':SEAL,'service_owner':ev['owner'],'boot_id':ev['boot_id']},'host41_recovery':{'host':HOST,'remote_root':NEW,'roles':roles,'run_ids':selected,'segment_id':SEG,'actual_producer_seal_binding':'MIGRATION_DEPLOYMENT.json','aggregate_gate':'analysis/postrun/long_0039/SCHEDULE_RUNTIME_GATE.json','aggregate_schema':'r149-fixed-schedule-segment-gate-v1','COMPLETE_schema':'r149-schedule-segment-completion-v1'}},
 'science':{'seed':sci['cases'][0]['seed'],'noise_file_sha256':sci['parent_noise_sha256'],'prompt_sha256':sci['cases'][0]['prompt_sha256'],'conditioning_sha256':sci['conditioning_sha256'],'geometry':sci['cases'][0]['geometry'],'valid_frames':sci['cases'][0]['valid_frame_count'],'schedules':{c['arm']:c['steps_zero_based'] for c in sci['cases']},'arms':{c['arm']:{'alpha':c['alpha'],'physical_query_window':c['physical_query_window'],'phase_displacement':0} for c in sci['cases']},'NFE':20,'blocks':[0,50],'core_sha256':sha(T/'extensions/H3TemporalRouter/core.py'),'layout_sha256':sha(T/'extensions/H3TemporalRouter/layout.py'),'source_graph_sha256':{c['arm']:sha(S/'configs/graphs'/(c['run_id']+'.json')) for c in sci['cases']},'target_graph_sha256':{c['arm']:sha(T/'configs/graphs'/(c['run_id']+'.json')) for c in sci['cases']}},
 'failure':{'failed_run':allruns[1],'completed_callbacks':4,'replay_from_original_noise':True,'source_evidence':{k:{'path':v['path'],'sha256':v['sha256']} for k,v in ev['files'].items()}},'boundary':{'original_four_arm_COMPLETE_remains_absent':True,'same_persistent_service_across_segments':False}}
write(H/'MIGRATION_MANIFEST.json',manifest);write(T/'configs/MIGRATION_MANIFEST.json',manifest)
prefix={'schema':'r149-schedule-hardware-partial-release-v1','passed':True,'source_id':'long_0039','segment_id':'host41_prefix','stop_kind':'hardware_failure','migration_manifest_sha256':sha(H/'MIGRATION_MANIFEST.json'),'source_root':OLD,'producer_seal_sha256':SEAL,'service_owner':ev['owner'],'completed_runs':allruns[:1],'completed_roles':['early'],'remaining_runs':selected,'gates':{allruns[0]:{k:v for k,v in ev['files']['analysis/postrun/long_0039/'+allruns[0]+'_GATE.json'].items() if k!='content'}},'registered_generations':ev['generations'],'process_generation_absent':True,'CUDA_allocation_absent':None,'release_state':'processes_exited_gpu_unqueryable','gpu_health':'requires_reset','gpu_uuid':ev['owner']['gpu_uuid'],'raw_compute_telemetry':ev['cuda_raw'],'original_four_arm_COMPLETE':False,'evidence':manifest['failure']['source_evidence'],'created_unix':ev['observed_unix']}
write(H/'PREFIX_PARTIAL_RELEASE.json',prefix);write(T/'producer/PREFIX_PARTIAL_RELEASE.json',prefix)
for p in (S/'extensions').rglob('*.py'):assert sha(p)==sha(T/p.relative_to(S))
for rel in ['configs/scientific_contract.json','configs/CONDITION_CACHE.json','design/conditioning.json']:assert sha(S/rel)==sha(T/rel)
for helper in ['check_fresh_paths.py','watch_queue.py']:shutil.copy2(S/'producer'/helper,T/'producer'/helper)
sys.path.insert(0,str(T/'scripts'));import r132_contract,execution_gate
assert r132_contract.registry()[1]==selected;execution_gate.seal(T)
deploy={'schema':'r149-hardware-recovery-deployment-v1','source_id':'long_0039','migration_manifest_sha256':sha(H/'MIGRATION_MANIFEST.json'),'prefix_partial_release_sha256':sha(H/'PREFIX_PARTIAL_RELEASE.json'),'segments':{k:{a:b for a,b in v.items() if a in ('host','remote_root','roles','run_ids','producer_seal_sha256')} for k,v in manifest['segments'].items()},'created_unix':time.time()};deploy['segments']['host41_recovery']['producer_seal_sha256']=sha(T/'deploy_manifest.json');write(H/'MIGRATION_DEPLOYMENT.json',deploy)
write(T/'producer/SCIENTIFIC_EQUIVALENCE.json',{'passed':True,'numerical_modules_byte_identical':True,'scientific_contract_byte_identical':True,'conditioning_byte_identical':True,'original_noise_reused':True,'old_seal':SEAL,'new_seal':sha(T/'deploy_manifest.json'),'actual_registry':selected,'GPU_started':False})
print(json.dumps({'root':str(T),'seal':sha(T/'deploy_manifest.json'),'registry':selected}))
