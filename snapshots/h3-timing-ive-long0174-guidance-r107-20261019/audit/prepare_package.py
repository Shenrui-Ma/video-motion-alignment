from pathlib import Path
import json,shutil,hashlib,copy
R=Path(__file__).resolve().parents[1]
B=R.parent/'h3-timing-ive-p1-guidance-r99-20261019'
ONE=R.parent/'h3-timing-flexiact-character-guidance-r101-20261019'
P=R.parent/'h3-timing-ive-native-screen-r96-20261018'
A=R.parent/'h3-timing-flexiact-p1-repair-r103-20261019/audit/R96_ACTUAL_RECOVERY.json'
S='long_0174';OLD='r96_'+S+'_seed2026101701_native';RUN='r107_'+S+'_seed2026101701_forced'
REMOTE='/data4/researcher/h3_runs/timing_ive_long0174_guidance_r107_20261019'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
assert not (R/'configs').exists()
numeric=read(P/'configs/runtime_kernel_hashes.json')
for folder in ('scripts','extensions','source_snapshot','tests'):
 shutil.copytree(B/folder,R/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copytree(B/'analysis/postrun',R/'analysis/postrun',ignore=shutil.ignore_patterns('__pycache__','*.pyc','short_*'))
for folder in ('configs/graphs','configs/prompts','design','inputs','input','output','temp','user','custom_nodes','logs','processes','audit/router','audit/x0','audit/tensor_blobs'):(R/folder).mkdir(parents=True,exist_ok=True)
for folder in ('scripts','extensions','source_snapshot','tests','analysis/postrun'):
 for p in (R/folder).rglob('*.py'):
  if str(p.relative_to(R)) not in numeric:p.write_text(p.read_text().replace('r99_contract','r107_contract').replace('r99_','r107_').replace('r99-','r107-').replace('R99','R107'))
(R/'scripts/r99_contract.py').rename(R/'scripts/r107_contract.py')
for rel in ('scripts/execution_gate.py','audit/root_run_control.py'):
 (R/rel).write_text((ONE/rel).read_text().replace('r101_contract','r107_contract').replace('r101_','r107_').replace('r101-','r107-').replace('R101','R107'))
for rel in ('scripts/service.py','scripts/cgroup_memory.py'):
 (R/rel).write_text((P/rel).read_text().replace('r96_contract','r107_contract').replace('r96_','r107_').replace('r96-','r107-').replace('R96','R107'))
a=read(A);files=a['files'];pr=Path(a['root']);gate=files['analysis/postrun/'+S+'/NATIVE_RUNTIME_GATE.json']['value'];assert gate['passed'] and gate['runs']['native']['NFE']==20 and gate['runs']['native']['routed_blocks']==0
snap={'PARENT_ACTUAL_GATE.json':'analysis/postrun/'+S+'/NATIVE_RUNTIME_GATE.json','PARENT_GRAPH.json':'configs/graphs/'+OLD+'.json','PARENT_RUNTIME.json':'configs/runtime.json','PARENT_CONDITIONING.json':'audit/'+OLD+'_conditioning.json','PARENT_SHARED_CONDITIONING.json':'audit/r96_'+S+'_shared_conditioning.json','PARENT_NOISE.json':'audit/'+OLD+'_noise.json','PARENT_X0_MANIFEST.json':'audit/x0/'+OLD+'/manifest.json','PARENT_HISTORY.json':'logs/'+OLD+'_history.json','PARENT_JOB.json':'logs/'+OLD+'_job.json','PARENT_SERVICE.json':'processes/service.json','PARENT_CLEANUP.json':'processes/cleanup.json'}
for name,rel in snap.items():write(R/'design'/S/name,files[rel]['value'])
case=copy.deepcopy(next(c for c in files['configs/scientific_contract.json']['value']['cases'] if c['source_id']==S and c['arm']=='native'))
case.update(run_id=RUN,arm='forced',parent_run=OLD,parent_graph='design/'+S+'/PARENT_GRAPH.json',parent_graph_sha256=files['configs/graphs/'+OLD+'.json']['sha256'],reference_video_count=1,reference_image_count=0,prompt_version='actual-parent-P1-verbatim')
shutil.copy2(P/'configs/graphs'/f'{OLD}.json',R/case['parent_graph']);assert sha(R/case['parent_graph'])==case['parent_graph_sha256']
for key in ('video','provenance'):shutil.copy2(P/'inputs'/case[key],R/'inputs'/case[key])
(R/'configs/prompts'/f'{S}.txt').write_text(case['prompt']);write(R/'design/CASE_DEFINITIONS.json',[case])
noise=copy.deepcopy(files['audit/'+OLD+'_noise.json']['value'])
# Producer gate binds the actual cache file; obtain that SHA in the actual CPU intake before sealing.
noise_path=Path(noise['cache_file'])
noise['current_file']={'sha256':read(R/'audit/PARENT_NOISE_FILE.json')['sha256']}
record_hashes={rel:files[rel]['sha256'] for rel in snap.values() if rel!='analysis/postrun/'+S+'/NATIVE_RUNTIME_GATE.json'}
binding={'source_id':S,'producer_local':str(P),'producer_remote':str(pr),'run_id':OLD,'graph':{'sha256':case['parent_graph_sha256']},'gate':{'sha256':files['analysis/postrun/'+S+'/NATIVE_RUNTIME_GATE.json']['sha256']},'native_video':gate['runs']['native']['video'],'runtime':files['configs/runtime.json']['value'],'condition_manifest':{'sha256':files['audit/'+OLD+'_conditioning.json']['sha256']},'noise':noise,'new_noise_relative':'audit/r107_'+S+'_seed2026101701_noise.pt','original_gate_relative':'analysis/postrun/'+S+'/NATIVE_RUNTIME_GATE.json','first_six_predictions':gate['runs']['native']['snapshots'][:6],'condition_tensors':[{'file':x['file'],'gate_file_sha256':x['sha256']} for x in gate['condition_tensor_files']],'local_snapshot_hashes':{name:sha(R/'design'/S/name) for name in snap},'parent_record_hashes':record_hashes,'task_acceptance':'All145 source/Native frames reviewed; black clothing edit succeeds and actions show visible delay. Matching guidance remains untested.'}
write(R/'configs/parent_bindings.json',{S:binding})
runtime=copy.deepcopy(files['configs/runtime.json']['value']);runtime.update(remote_root=REMOTE,port=8570,profile='host41_gpu2_r107_normal_reserve8',profile_scope='R96 actual long0174 Native matched fixed guidance; six condition tensors, raw AV noise and predictions0..5 exact.40GiB GPU and64GiB cgroup cold-load admission.');write(R/'configs/runtime.json',runtime)
sci=copy.deepcopy(read(B/'configs/scientific_contract.json'));sci.update(schema='r107-historical-native-fixed-guidance-v1',source_ids=[S],cases=[case],case_order=[RUN],geometry=case['geometry'],scope_note='Known fixed temporal routing on one successful black-clothing edit with observed timing drift; no architectural novelty claim.');sci['continuous']['max_service_seconds']=21600;write(R/'configs/scientific_contract.json',sci);write(R/'configs/queue.json',{'jobs':[RUN],'finalize':True})
write(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir() if p.is_file()})
for name in ('expected_checkpoint_hashes.json','parent_core_hashes.json','cgroup_policy.json'):shutil.copy2(P/'configs'/name,R/'configs'/name)
for rel,row in numeric.items():
 shutil.copy2(P/rel,R/rel);row.update(parent_file=str(P/rel),parent_sha256=sha(P/rel),current_sha256=sha(R/rel),byte_equal=sha(P/rel)==sha(R/rel))
assert all(x['byte_equal'] for x in numeric.values());write(R/'configs/runtime_kernel_hashes.json',numeric)
write(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
write(R/'configs/storage_policy.json',{'startup_required_free_bytes':10*1024**3,'estimated_output_bytes':4*1024**3,'note':'One158frame output, actual conditioning and x0 captures; estimate.'})
write(R/'configs/predecessor.json',{'root':str(pr),'owner':files['processes/service.json']['value'],'producer_seal_sha256':files['deploy_manifest.json']['sha256'],'attempt':'root_native_screen_attempt1','last_run':OLD,'exit_sha256':files['audit/root_native_screen_attempt1/ROOT_EXIT_RECEIPT.json']['sha256'],'pending_receipt_sha256':files['audit/root_native_screen_attempt1/RELEASED_PENDING_REVIEW.json']['sha256'],'binding':'Exact released R96 generation; its fifth Native is transferred to this independent matched-guidance follow-up.'})
for name in ('REVIEW.json','FRAME_LEDGER.json'):shutil.copy2(R.parent/'h3-ive-native-screen-metrics-r96-20261018/audit/recovery_full_review_long0174'/name,R/'design'/name)
print('Prepared R107 inherited skeleton; explicit contract/geometry adjustments still pending.')
