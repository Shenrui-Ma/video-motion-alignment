from pathlib import Path
import json,shutil,hashlib,copy
R=Path(__file__).resolve().parents[1];B=R.parent/'h3-timing-ive-p1-guidance-r99-20261019';P=R.parent/'h3-timing-flexiact-character-repair-r98-20261019';C=R.parent/'h3-flexiact-character-repair-metrics-r98-20261019';S='human2animal_1__game_man_4';RUN='r101_'+S+'_seed2026101701_forced';REMOTE='/data5/researcher/h3_runs/timing_flexiact_character_guidance_r101_20261019'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
for folder in ('scripts','extensions','source_snapshot','tests'):
 shutil.copytree(B/folder,R/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'),dirs_exist_ok=True)
for folder in ('configs/graphs','configs/prompts','design','inputs','input','output','temp','user','custom_nodes','logs','processes','audit/router','audit/x0','audit/tensor_blobs','analysis/postrun'):(R/folder).mkdir(parents=True,exist_ok=True)
numeric=read(B/'configs/runtime_kernel_hashes.json')
for folder in ('scripts','extensions','source_snapshot','tests'):
 for p in (R/folder).rglob('*.py'):
  if str(p.relative_to(R)) not in numeric:p.write_text(p.read_text().replace('r99_contract','r101_contract').replace('r99_','r101_').replace('r99-','r101-').replace('R99','R101'))
(R/'scripts/r99_contract.py').rename(R/'scripts/r101_contract.py')
a=read(R/'audit/R98_SMALL_ACTUAL.json');assert a['uid']==1016;files=a['files'];pr=Path(a['root']);old='r98_'+S+'_seed2026101701_native';gate=files['analysis/postrun/NATIVE_RUNTIME_GATE.json']['value'];assert gate['passed'] and gate['NFE']==20 and gate['routed_blocks']==0
snap={'PARENT_ACTUAL_GATE.json':'analysis/postrun/NATIVE_RUNTIME_GATE.json','PARENT_GRAPH.json':'configs/graphs/'+old+'.json','PARENT_RUNTIME.json':'configs/runtime.json','PARENT_CONDITIONING.json':'audit/'+old+'_conditioning.json','PARENT_SHARED_CONDITIONING.json':'audit/r98_'+S+'_shared_conditioning.json','PARENT_NOISE.json':'audit/'+old+'_noise.json','PARENT_X0_MANIFEST.json':'audit/x0/'+old+'/manifest.json','PARENT_HISTORY.json':'logs/'+old+'_history.json','PARENT_JOB.json':'logs/'+old+'_job.json','PARENT_SERVICE.json':'processes/service.json','PARENT_CLEANUP.json':'processes/cleanup.json'}
for name,rel in snap.items():write(R/'design'/S/name,files[rel]['value'])
case=copy.deepcopy(files['configs/scientific_contract.json']['value']['cases'][0]);case.update(run_id=RUN,arm='forced',parent_run=old,parent_graph='design/'+S+'/PARENT_GRAPH.json',parent_graph_sha256=files['configs/graphs/'+old+'.json']['sha256'],reference_video_count=1,reference_image_count=1)
# Preserve exact original JSON bytes for the graph whose raw SHA is bound.
shutil.copy2(P/'configs/graphs'/f'{old}.json',R/case['parent_graph']);assert sha(R/case['parent_graph'])==case['parent_graph_sha256']
case.pop('prompt_file',None);case.pop('graph_template_only',None)
for key in ('video','portrait','provenance'):shutil.copy2(P/'inputs'/case[key],R/'inputs'/case[key])
original=read(P/'design/CASE_DEFINITION.json')['source'];shutil.copy2(P/'inputs'/original['original'],R/'inputs'/original['original']);write(R/'design/ORIGINAL_SOURCE.json',original)
(R/'configs/prompts'/f'{S}.txt').write_text(case['prompt']);write(R/'design/CASE_DEFINITIONS.json',[case])
noise=files['audit/'+old+'_noise.json']['value'];oldbindings=read(P/'configs/parent_bindings.json');noise['current_file']={'sha256':oldbindings['noise_cache_sha256']}
parent={'source_id':S,'producer_local':str(P),'producer_remote':str(pr),'run_id':old,'graph':{'sha256':case['parent_graph_sha256']},'gate':{'sha256':files['analysis/postrun/NATIVE_RUNTIME_GATE.json']['sha256']},'native_video':gate['video'],'runtime':files['configs/runtime.json']['value'],'condition_manifest':{'sha256':files['audit/'+old+'_conditioning.json']['sha256']},'noise':noise,'new_noise_relative':'audit/r101_'+S+'_seed2026101701_noise.pt','original_gate_relative':'analysis/postrun/NATIVE_RUNTIME_GATE.json','first_six_predictions':gate['snapshots'][:6],'condition_tensors':[{'file':x['file'],'gate_file_sha256':x['sha256']} for x in gate['condition_tensor_files']],'local_snapshot_hashes':{name:sha(R/'design'/S/name) for name in snap},'parent_record_hashes':{rel:files[rel]['sha256'] for rel in snap.values() if rel!='analysis/postrun/NATIVE_RUNTIME_GATE.json'},'task_acceptance':'Root observed successful new Native target identity; full49 review retained separately; identity drift must also be checked in guidance.'}
write(R/'configs/parent_bindings.json',{S:parent})
runtime=copy.deepcopy(read(B/'configs/runtime.json'));runtime.update(remote_root=REMOTE,port=8565,profile='host9_gpu3_r101_normal_reserve8',profile_scope='R98 actual Native matched fixed-guidance control;8 actualcondition tensors/rawAVnoise/prefix0..5 exact.40GiB/max2ownGPU.');write(R/'configs/runtime.json',runtime)
sci=copy.deepcopy(read(B/'configs/scientific_contract.json'));sci.update(schema='r101-historical-native-fixed-guidance-v1',source_ids=[S],cases=[case],case_order=[RUN],geometry=case['geometry']);sci['continuous'].update(max_service_seconds=21600);write(R/'configs/scientific_contract.json',sci);write(R/'configs/queue.json',{'jobs':[RUN],'finalize':True})
write(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir() if p.is_file()})
for name in ('expected_checkpoint_hashes.json','parent_core_hashes.json'):shutil.copy2(P/'configs'/name,R/'configs'/name)
for rel,row in numeric.items():
 shutil.copy2(P/rel,R/rel);row.update(parent_file=str(P/rel),parent_sha256=sha(P/rel),current_sha256=sha(R/rel),byte_equal=sha(P/rel)==sha(R/rel))
assert all(x['byte_equal'] for x in numeric.values());write(R/'configs/runtime_kernel_hashes.json',numeric)
write(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
write(R/'configs/storage_policy.json',dict(read(P/'configs/storage_policy.json'),schema='r101-storage-budget-v1'))
write(R/'configs/predecessor.json',{'root':read(B/'configs/runtime.json')['remote_root'],'gpu_uuid':runtime['gpu_uuid'],'registered_runs':read(B/'configs/queue.json')['jobs'],'binding':'Root actual R99 current service generation, all3paired gates tied to it, successful final history and exact PID/CUDA release required before launch. No predecessor PID is invented before it starts.'})
print('Prepared R101 inherited administrative/numeric skeleton and actual R98 evidence')
