from pathlib import Path
import shutil,json,hashlib,ast,copy
B=Path('/Users/researcher/DevProjects');R=B/'h3-timing-oxygen-online-r86-20261018';OLD=B/'h3-timing-visible-feedback-r59-execution-20261017';P=B/'h3-timing-ivebench-expanded-r73-20261018';A=B/'h3-timing-local-edit-repair-r80-20261018';O=B/'h3-timing-oxygen-observer-r81-20261018';M=B/'h3-ivebench-expanded-metrics-r73-20261018'
REMOTE='/data5/researcher/h3_runs/timing_oxygen_online_r86_20261018';PARENT='/data5/researcher/h3_runs/timing_ivebench_expanded_r73_20261018';RUN='r86_short_0252_seed2026101701_visible_only'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,v):p=R/p;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
provenance={}
def cp(parent,rel,dst=None):
 dst=dst or rel;s=parent/rel;t=R/dst;t.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(s,t);provenance[dst]={'source':str(s),'source_sha256':sha(s)}
for f in ('scripts','tests','configs','inputs','analysis/postrun','design','prepared_parent','custom_nodes','processes','logs','output','input','temp','user'):(R/f).mkdir(exist_ok=True,parents=True)
for ext in ('H3AutomaticWindowRouter','H3TemporalRouter','H3X0Readout'):
 for p in (OLD/'extensions'/ext).rglob('*.py'):
  if '__pycache__' not in p.parts:cp(OLD,str(p.relative_to(OLD)))
for ext in ('H3EventAudit','H3PairAudit'):
 for p in (P/'extensions'/ext).rglob('*.py'):
  if '__pycache__' not in p.parts:cp(P,str(p.relative_to(P)))
for f in ('observer_import.py','run_observer.py','pose_live_child.py','pose_probe.py','scan_current_pose.py','arm_features.py','timing_metrics.py','pairwise_gain.py','physical_tolerance.py','pose_domain.py','decode_live_child.py','gpu_release_gate.py'):
 cp(OLD,'scripts/'+f)
for f in ('service.py','service_entry.py','process_identity.py','resource_gate.py','supervise_service.py','compatibility_bootstrap.py','int8_row_chunking.py','backend_dispatch_audit.py','probe_guards.py','job.py','lease_watchdog.py'):
 cp(A if (A/'scripts'/f).exists() else P,'scripts/'+f)
for f in ('parent_core_hashes.json','expected_checkpoint_hashes.json'):cp(P,'configs/'+f)
for f in ('short_0252_original.mp4','short_0252_video.mp4','short_0252_provenance.json','short_0252_prompt.txt'):cp(P,'inputs/'+f)
cp(P,'configs/prompts/short_0252.txt')
cp(P,'configs/graphs/r73_short_0252_seed2026101701_native.json','configs/PARENT_GRAPH.json')
cp(M,'incoming/short_0252/PAIR_RUNTIME_GATE.json','configs/PARENT_PAIR_GATE.json')
cp(O,'inputs/manifest.json','configs/PARENT_CAPTURES.json')
cp(O,'poses/attempt1/source.pose.json','configs/source.pose.json')
cp(O,'inputs/source.pose.json','design/source_raw.pose.json')
cp(O,'audit/consumer_attempt1/R59_IMPLEMENTATION_PARITY.json','design/R81_PARITY.json')
cp(O,'configs/PROTOCOL.json','design/R81_PROTOCOL.json')
cp(O,'scripts/contract.py','design/R81_contract.py')
cp(P,'extensions/H3TemporalRouter/core.py','tests/fixtures/r73_router/core.py')
cp(P,'extensions/H3TemporalRouter/layout.py','tests/fixtures/r73_router/layout.py')
(R/'tests/fixtures/r73_router/__init__.py').write_text('')
for f in ('test_visible_feedback.py','test_transaction.py','test_process_binding.py'):cp(OLD,'tests/'+f)
# Exact source-only adult selector functions, no new detector or threshold.
s=(O/'scripts/contract.py').read_text();tree=ast.parse(s);functions=[ast.get_source_segment(s,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('validate_pose_shape','adult_only')]
(R/'scripts/adult_selector.py').write_text('"""R81 source-specified adult selection; time detection remains online."""\nimport copy\n\ndef require(ok,message):\n if not ok:raise ValueError(message)\n\n'+'\n\n'.join(functions)+'\n')
runtime=read(P/'configs/runtime.json');runtime.update(remote_root=REMOTE,port=8550,decoder_gpu_uuid='GPU-REDACTED',decoder_expected_gpu_index=1,profile_scope='R86 two-GPU online trial, same R73 host9 normal/reserve8; actual online main/decoder peaks pending.',status='CPU_PREPARATION_NOT_GPU_ADMITTED')
write('configs/runtime.json',runtime)
case=next(x for x in read(P/'configs/scientific_contract.json')['cases'] if x['run_id']=='r73_short_0252_seed2026101701_native')
case.update(run_id=RUN,arm='visible_only',parent_run='r73_short_0252_seed2026101701_native',parent_root=PARENT,parent_status='ACTUAL_GATE_PASSED_BINDING_PENDING',source_pose_path='configs/source.pose.json',source_pose_sha256=sha(R/'configs/source.pose.json'),parent_conditioning='prepared_parent/conditioning.json',parent_noise='prepared_parent/noise.json',parent_captures='configs/PARENT_CAPTURES.json',parent_file_inventory='prepared_parent/FILE_INVENTORY.json',parent_graph='configs/PARENT_GRAPH.json',parent_graph_sha256=sha(R/'configs/PARENT_GRAPH.json'))
proto=read(OLD/'configs/protocol.json');proto.update(schema='r86-oxygen-online-protocol-v1',scope='One development task: actual online visible_only; no new algorithm claim',cases=[case],geometry=case['geometry'],preparation_status='CPU_PREPARATION_ACTUAL_PARENT_MATERIALIZATION_PENDING',arms=['visible_only'],policy_choice='visible_only',GPU_launch_authorized=False)
proto['resources'].update(main_uuid=runtime['gpu_uuid'],decoder_uuid=runtime['decoder_gpu_uuid'],CPU_lock='/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock',job_timeout_seconds=14400,service_timeout_seconds=18000,capacity_status='ROOT_TRIAL_PENDING_main40GiB_decoder16GiB')
proto['person_selection']={'kind':'source-specified spatial selector','selected_bbox_center_x_fraction':[.4,.75],'selection':'retain original largest/IoU-selected person only if inside bounds; otherwise None','automation_scope':'time-window and start/stop online; spatial identity bounds specified from source/task','parent_R81_protocol_sha256':sha(O/'configs/PROTOCOL.json')}
proto['prefix']={'availability':'all20 actual R73 Native captures','comparison':'current Native exact through first actual ON inclusive; permanently N/A afterward','parent_gate_sha256':sha(R/'configs/PARENT_PAIR_GATE.json')}
proto['weak']={'enabled':False,'registered_arm':'visible_only'}
proto['evaluation']={'reference':'all98 valid frames; fixed source six times; task attainment then visible motion and officialMF','trajectory_policy':'no final-video fitting or hardcoded offline decisions'}
write('configs/protocol.json',proto)
write('configs/scientific_contract.json',dict(schema='r86-online-single-job-v1',cases=[case],case_order=[RUN],arms=['visible_only'],online_observer=True,NFE='20+actual_ON',Euler_updates=20,continuous={'job_timeout_seconds':14400,'max_service_seconds':18000,'idle_hold_seconds':1800},parent_gate_sha256=sha(R/'configs/PARENT_PAIR_GATE.json')))
write('configs/queue.json',{'jobs':[RUN],'finalize':True})
g=read(R/'configs/PARENT_GRAPH.json')
for node,key,suffix in [('5','audit_dir','audit'),('6','audit_dir','audit'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=REMOTE+'/'+suffix
for node in ('6','51','52'):g[node]['inputs']['run_id']=RUN
g['14']['inputs']['filename_prefix']=RUN
g['50']={'class_type':'H3AutomaticWindowRouter','inputs':{'model':['41',0],'positive':['51',0],'run_id':RUN,'audit_dir':REMOTE+'/audit/counterfactual'}}
write('configs/graphs/'+RUN+'.json',g)
write('configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir() if p.is_file()})
fixed={'scope':'own_user_video_jobs','max_own_gpu_cards':2,'main_gpu_uuid':runtime['gpu_uuid'],'decoder_gpu_uuid':runtime['decoder_gpu_uuid'],'existing_comfy_port':None}
write('configs/admission_template.json',{'fixed_fields':fixed})
write('configs/admission.json',dict(fixed,permitted_compute_processes=[],root_live_review_required=True,ready_for_launch=False))
write('configs/PARENT_CLOSURE.json',{'schema':'r86-actual-parent-closure-v1','ready':False,'status':'PENDING_CPU_MATERIALIZATION','cases':{}})
vae=runtime['models']+'/vae/minimax_h3_video_vae_fp16.safetensors';vaesha='7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522'
write('configs/decoder_memory_profile.json',{'schema':'r86-decoder-capacity-trial-v1','status':'UNMEASURED_HOST9_107_TRIAL','geometry':case['geometry'],'vae_sha256':vaesha,'required_free_bytes':16*1024**3,'historical_host41_peak_reserved_bytes':6027214848,'historical_scope':'R81 full107 .41 only; not a host9 capacity certificate'})
external=read(O/'configs/PROTOCOL.json')['host9'];write('configs/observer_external_bindings.json',{'comfy':runtime['core'],'runtime_deps':runtime['dependencies'],'vae':vae,'vae_sha256':vaesha,'aux_root':external['aux_root'],'external_files':dict(external['external_sha256'],**{vae:vaesha})})
write('audit/COPY_PROVENANCE.json',provenance)
# Administrative location/contract adaptations only; preserve source inventory.
for p in list((R/'scripts').glob('*.py'))+list((R/'extensions/H3EventAudit').glob('*.py'))+list((R/'extensions/H3PairAudit').glob('*.py')):
 text=p.read_text().replace('from r80_contract import','from r86_contract import').replace('from r73_contract import','from r86_contract import');p.write_text(text)
t=R/'extensions/H3AutomaticWindowRouter/transport.py';text=t.read_text();text=text.replace("PROTOCOL_SHA='5bc5e998e274d06623f3d31b195721218f89f6a1e779ebfa6d4dfd0fb68a69df'",'PROTOCOL_SHA='+repr(sha(R/'configs/protocol.json'))).replace("DECODER_UUID='GPU-REDACTED'","DECODER_UUID='GPU-REDACTED'").replace("MAIN_UUID='GPU-REDACTED'","MAIN_UUID='GPU-REDACTED'").replace('/data3/researcher/h3_runs/timing_visible_feedback_r59_execution_20261017',REMOTE).replace('R59 WAITING_R57_ACTUAL_ARCHIVES','R86 actual parent materialization pending').replace('five-case parent closure incomplete','single-case parent closure incomplete')
a=text.index('def decoder_memory_profile(');b=text.index('\ndef validate_resource_capacity',a)
text=text[:a]+'''def decoder_memory_profile(*,bootstrap=False):
 path=ROOT/'configs/decoder_memory_profile.json';p=read_json(path)
 require(p.get('schema')=='r86-decoder-capacity-trial-v1' and p.get('status')=='UNMEASURED_HOST9_107_TRIAL','decoder trial scope differs')
 require(p['geometry']=={'width':1312,'height':736,'frames':107,'fps':24} and p['required_free_bytes']==16*1024**3,'decoder trial geometry/budget differs')
 approval=read_json(ROOT/'audit/ROOT_ONLINE_APPROVAL.json')
 require(approval.get('root_approved') is True and approval['decoder_profile_sha256']==sha(path),'root decoder trial approval pending')
 require(approval['runtime_sha256']==sha(ROOT/'configs/runtime.json'),'runtime trial binding differs')
 return dict(p,profile_sha256=sha(path),profile_scope='explicit unmeasured host9 full107 trial, 16GiB admission; no measured claim')
''' +text[b:];t.write_text(text)
# Keep raw pose, scan exact R81 filtered selected-person view.
p=R/'scripts/pose_live_child.py';text=p.read_text();old="geometry=t.geometry_for(r['run_id']);validate_pose(pose,geometry)";new="""geometry=t.geometry_for(r['run_id']);validate_pose(pose,geometry)
   from adult_selector import adult_only
   filtered,rejected=adult_only(raw,geometry.video_geometry)
   raw_path=pose;pose=output/'native.adult.pose.json';t.write_new(pose,filtered)
   t.write_new(output/'adult_selection.json',{'schema':'r86-source-specified-person-view-v1','raw_pose_sha256':t.sha(raw_path),'filtered_pose_sha256':t.sha(pose),'bounds':[.4,.75],'rejected_frames':rejected,'automation_scope':'source-specified spatial identity; online temporal detection'})
   validate_pose(pose,geometry)""";assert old in text;text=text.replace(old,new);p.write_text(text)
p=R/'scripts/run_observer.py';text=p.read_text().replace("d/'pose/native.pose.json'","d/'pose/native.adult.pose.json'");p.write_text(text)
# service capacity administrative approval.
p=R/'scripts/service.py';text=p.read_text();a=text.index('def main_memory_profile(');b=text.index('\ndef gpu_readiness',a)
text=text[:a]+'''def main_memory_profile():
    import resource_gate as t
    a=t.read_json(RUN/'audit/ROOT_ONLINE_APPROVAL.json')
    t.require(a.get('root_approved') is True and a['runtime_sha256']==t.sha(RUN/'configs/runtime.json'),'root online trial pending')
    t.require(a['main_required_free_bytes']==40*1024**3,'main trial budget differs')
    return {'status':'ROOT_APPROVED_ONLINE_CAPACITY_TRIAL','required_free_bytes':a['main_required_free_bytes'],'profile_sha256':t.sha(RUN/'audit/ROOT_ONLINE_APPROVAL.json')}
''' +text[b:]
# Parent service stop must not claim auxiliary decoder absence without checking.
text=text.replace("result['child_compute_absent']=True  # This profile launches no auxiliary CUDA child.","result['child_compute_absent']=None  # root online wrapper separately verifies bound decoder descendants.")
p.write_text(text)
print(R)
