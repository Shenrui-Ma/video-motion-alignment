from pathlib import Path
import json,shutil,hashlib,copy
R=Path(__file__).resolve().parents[1];B=Path('/Users/researcher/DevProjects');P=B/'h3-timing-ive-glasses-schedule-r97-20261018'
proof=B/'h3-benchmark-all-results-showcase-20261018/audit/user_reported_ive_failures_20261019';parents=json.loads((proof/'P1_PARENT_BINDINGS.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
for folder in ['scripts','extensions','source_snapshot']:
 for src in (P/folder).rglob('*'):
  if not src.is_file() or '__pycache__' in src.parts:continue
  dest=R/folder/src.relative_to(P/folder);dest.parent.mkdir(parents=True,exist_ok=True)
  if dest.exists():continue
  dest.write_bytes(src.read_bytes())
for folder in ['configs/graphs','configs/prompts','tests','analysis/postrun','input','inputs','output','temp','user','custom_nodes','processes','logs','audit/router','audit/x0','audit/tensor_blobs']:(R/folder).mkdir(parents=True,exist_ok=True)
for folder in ['scripts','extensions']:
 for f in (R/folder).rglob('*.py'):
  if '__pycache__' in f.parts:continue
  f.write_text(f.read_text().replace('r97_contract','r99_contract').replace('R97','R99').replace('r97_','r99_').replace('r97-','r99-'))
(R/'scripts/r97_contract.py').unlink()
for n in ['checkpoints.py']:
 pass
for name in ['parent_core_hashes.json','expected_checkpoint_hashes.json']:
 shutil.copyfile(P/'configs'/name,R/'configs'/name)
for n in ['P1_PARENT_BINDINGS.json','REMOTE_PARENT_EVIDENCE.json','REMOTE_PARENT_TENSOR_PRESENCE.json']:
 shutil.copyfile(proof/n,R/'design'/n)
remote='/data5/researcher/h3_runs/timing_ive_p1_guidance_r99_20261019'
runtime=json.loads((P/'configs/runtime.json').read_text());runtime.update(remote_root=remote,gpu_uuid='GPU-REDACTED',port=8563,expected_gpu_index=3,profile='host9_gpu3_r99_normal_reserve8',profile_scope='Three same-host historical P1 Native matched fixed controls; actual clean conditions/noise and predictions0..5 exact required; firstcontrol review then remaining2;40GiB admission,max2ownGPUs.')
save(R/'configs/runtime.json',runtime)
caseall=[];bindings={};records=json.loads((proof/'REMOTE_PARENT_EVIDENCE.json').read_text())['files']
for row in parents['parents']:
 source=row['source_id'];prior=Path(row['producer_local']);run='r99_'+source+'_seed2026101701_forced';dst=R/'design'/source
 for key,name in [('history','PARENT_HISTORY.json'),('job','PARENT_JOB.json')]:
  src=Path(row[key]['file']);assert sha(src)==row[key]['sha256'];shutil.copyfile(src,dst/name)
 for record_key,name in [('condition_manifest','PARENT_CONDITIONING.json'),('shared_manifest','PARENT_SHARED_CONDITIONING.json')]:
  item=records[row[record_key]['file']];assert item['sha256']==row[record_key]['sha256'];save(dst/name,item['value'])
 graph=json.loads((dst/'PARENT_GRAPH.json').read_text());parentcase=next(c for c in json.loads((prior/'configs/scientific_contract.json').read_text())['cases'] if c['run_id']==row['run_id'])
 case=copy.deepcopy(parentcase);case.update(run_id=run,arm='forced',source_id=source,parent_run=row['run_id'],parent_graph='design/'+source+'/PARENT_GRAPH.json',parent_graph_sha256=sha(dst/'PARENT_GRAPH.json'),prompt=graph['5']['inputs']['prompt'],valid_frame_count=row['valid_frames'],geometry={'width':1312,'height':736,'frames':90,'fps':24},seed=2026101701,reference_video_count=1,reference_image_count=0,evaluation_crop_xywh=[16,8,1280,720],prompt_version='parent_P1_exact')
 for key in ['video','provenance']:
  src=prior/'inputs'/case[key];shutil.copyfile(src,R/'inputs'/src.name);case[key+'_sha256']=sha(src)
 (R/'configs/prompts'/f'{source}.txt').write_text(case['prompt']);case['prompt_sha256']=sha(R/'configs/prompts'/f'{source}.txt')
 binding=copy.deepcopy(row);binding['original_gate_relative']='analysis/postrun/'+source+('/PAIR_RUNTIME_GATE.json' if source=='short_0210' else '/NATIVE_RUNTIME_GATE_HOST9_v2.json');binding['new_noise_relative']='audit/r99_'+source+'_seed2026101701_noise.pt'
 binding['local_snapshot_hashes']={str(p.relative_to(dst)):sha(p) for p in dst.iterdir() if p.is_file()}
 binding['parent_record_hashes']={f'configs/graphs/{row["run_id"]}.json':row['graph']['sha256'],f'logs/{row["run_id"]}_history.json':row['history']['sha256'],f'logs/{row["run_id"]}_job.json':row['job']['sha256'],str(Path(row['condition_manifest']['file']).relative_to(row['producer_remote'])):row['condition_manifest']['sha256'],str(Path(row['shared_manifest']['file']).relative_to(row['producer_remote'])):row['shared_manifest']['sha256']}
 # Actual original bytes remain remote; local extracted JSON values are named explicitly.
 binding['parent_noise_manifest']=records[str(Path(row['producer_remote'])/'audit'/(row['run_id']+'_noise.json'))]
 bindings[source]=binding;caseall.append(case)
save(R/'design/CASE_DEFINITIONS.json',caseall);save(R/'configs/parent_bindings.json',bindings)
s=json.loads((P/'configs/scientific_contract.json').read_text());s.update(schema='r99-historical-native-fixed-guidance-v1',geometry=caseall[0]['geometry'],arms=['forced'],cases=caseall,case_order=[x['run_id'] for x in caseall],source_ids=[x['source_id'] for x in caseall],prompt_version='exact actual parent P1;0210 legacy structuredP1,0230/0352P1-local-v1',router=dict(mode='mass_preserve',alpha=1.,blocks=[0,50],steps=[6,15],physical_frames='0..valid-1 per source',routed_calls=450),scope_note='Known fixed method added to three actual same-host successful P1 Native tasks; no novelty claim.',prefix_semantics='First allowed divergence is model prediction zero-based6. Actual AV x0 predictions0..5 bitwise equal to historical Native, not merely same seed.',evaluation={'manual_event_windows_used_for_guidance':False,'task_acceptance':'root confirms actual parent task before admission; visual evidence frozen','motion':'compare original/native/fixed at original 24fps valid domain','officialMF':'sameframe/crop tracker inputs after actual gate'})
s['continuous'].update(retain_service_between_jobs=True,idle_hold_seconds=1800,max_service_seconds=57600,job_timeout_seconds=14400)
save(R/'configs/scientific_contract.json',s);save(R/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
save(R/'configs/input_hashes.json',{x.name:sha(x) for x in (R/'inputs').iterdir() if x.is_file()})
save(R/'configs/predecessor.json',{'root':'/data5/researcher/h3_runs/timing_flexiact_character_repair_r98_20261019','service_pid':45858,'service_start_ticks':'2636922430','gpu_uuid':runtime['gpu_uuid'],'last_run':'r98_human2animal_1__game_man_4_seed2026101701_native','required':'Actual R98 successful Native and exact45858/start2636922430 PID/CUDA release; never stop predecessor.'})
save(R/'configs/storage_policy.json',{'startup_required_free_bytes':10*1024**3,'estimated_output_bytes':5*1024**3,'note':'Three90frame outputs/capture/reference blobs remain remote; estimate only.'})
save(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
numeric=json.loads((P/'configs/runtime_kernel_hashes.json').read_text());save(R/'configs/runtime_kernel_hashes.json',{f:{'parent_file':str(P/f),'parent_sha256':sha(P/f),'current_sha256':sha(R/f),'byte_equal':sha(P/f)==sha(R/f)} for f in numeric})
for file in ['test_attempt_cleanup.py','test_admission_resample.py','test_resource_peers.py','test_http_wait.py','test_watchdog_timers.py','test_spawn_identity.py','test_cuda_release.py']:
 (R/'tests'/file).write_text((P/'tests'/file).read_text().replace('r97_contract','r99_contract').replace('r97_','r99_').replace('r97-','r99-'))
shutil.copyfile(P/'audit/root_run_control.py',R/'audit/root_run_control.py')
p=R/'audit/root_run_control.py';p.write_text(p.read_text().replace('r97_contract','r99_contract').replace('r97_','r99_').replace('r97-','r99-'))
print('prepared local skeleton',len(caseall))
