from pathlib import Path
import copy,json,hashlib,shutil
R=Path(__file__).resolve().parents[1]
P=Path('/Users/researcher/DevProjects/h3-timing-ive-subject-capacity-r89-20261018')
B=Path('/Users/researcher/DevProjects/h3-timing-flexiact-p1-control-r90-20261018')
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
remote='/data5/researcher/h3_runs/timing_ive_glasses_schedule_r97_20261018'
run='r97_short_0358_seed2026101701_extended';oldrun='r89_short_0358_seed2026101701_forced'
case=copy.deepcopy(next(c for c in read(P/'configs/scientific_contract.json')['cases'] if c['run_id']==oldrun))
case.update(run_id=run,arm='extended',parent_graph='design/R89_ACTUAL/forced_graph.json',parent_graph_sha256=sha(R/'design/R89_ACTUAL/forced_graph.json'),parent_semantics='Same actual R89 fixed conditions/noise; only routing step_end15 to20. Prefix x0 predictions0..14 exact, index15 first permitted divergence.')
write(R/'design/CASE_DEFINITION.json',case)
write(R/'configs/scientific_contract.json',{'schema':'r97-fixed-schedule-extension-v1','new_method_claim':False,'geometry':case['geometry'],'NFE_per_job':20,'callback_count':20,'online_observer':False,'CFG':1,'sampler':'Euler20','no_Turbo':True,'blocks_per_job':1000,'captures':list(range(20)),'seeds':[2026101701],'arms':['extended'],'cases':[case],'case_order':[run],'source_ids':['short_0358'],'prompt_version':'P1-local-v1','router':{'mode':'mass_preserve','alpha':1.,'blocks':[0,50],'steps':[6,20],'physical_frames':[0,104],'routed_calls':700},'continuous':{'retain_service_between_jobs':False,'cache_none':False,'idle_hold_seconds':30,'max_service_seconds':18000,'job_timeout_seconds':14400,'root_final_close_releases':True,'failure_releases_exact_owned':True},'scope_note':'One existing fixed-schedule control. Same-bin all valid physical bins, alpha1/all50. Adding final5 denoising predictions changes both late position and cumulative intervention dose. No automatic timing or new-method claim.','prefix_semantics':'Callback x0 at step i is the i+1th model prediction before its Euler update; normalized video identity and audio /4. Compare both streams bitwise at i=0..14 against actual R89 fixed.','evaluation':{'valid_frames':105,'crop_xywh':[16,8,1280,720],'events_source':[ [14,18],[37,40],[80,84] ],'events_native':[[28,33],[50,53],[94,97]],'events_fixed_6_14':[[22,26],[47,50],[94,97]],'manual_boundaries_used_for_guidance':False,'inspect':'especially final bottle-leaves-mouth timing, also eyeglasses/identity/scene/bottle geometry','event_review_sha256':sha(R/'design/EVENT_REVIEW.json')}})
runtime=read(R/'configs/runtime.json');runtime.update(remote_root=remote,gpu_uuid='GPU-REDACTED',port=8561,expected_gpu_index=0,profile='host9_gpu0_r97_normal_reserve8',profile_scope='One same-host R89 schedule control: same-bin6..19, 700routes20NFE. Strict same actual conditions/rawAVnoise/predictions0..14;40GiB launch allowance, max2ownGPUs, wait exact R89 final release.')
write(R/'configs/runtime.json',runtime)
write(R/'configs/queue.json',{'jobs':[run],'finalize':True})
write(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
owner=read(R/'design/R89_ACTUAL/processes/service.json')
write(R/'configs/predecessor.json',{'root':read(P/'configs/runtime.json')['remote_root'],'service_pid':36315,'service_start_ticks':'2635074861','gpu_uuid':runtime['gpu_uuid'],'last_run':'r89_short_0178_seed2026101701_forced','required':'Require final0178historysuccess and exact36315/start2635074861 PID/CUDA release. Never stop predecessor.'})
actual=R/'design/R89_ACTUAL'
records={str(p.relative_to(actual)):sha(p) for p in actual.rglob('*') if p.is_file() and p.name!='PAIR_RUNTIME_GATE.json'}
gate=read(actual/'PAIR_RUNTIME_GATE.json');assert sha(actual/'PAIR_RUNTIME_GATE.json')=='963d11b3e95861cf55801ad037140794fbaa58159f0b5522eebdfcdccccc924c'
write(R/'configs/parent_bindings.json',{'schema':'r97-actual-fixed-parent-v1','parent_root':read(P/'configs/runtime.json')['remote_root'],'parent_run':oldrun,'parent_native_run':'r89_short_0358_seed2026101701_native','parent_shared':'r89_short_0358_shared','parent_graph_sha256':sha(actual/'forced_graph.json'),'parent_gate_sha256':sha(actual/'PAIR_RUNTIME_GATE.json'),'parent_gate_relative':'analysis/postrun/short_0358/PAIR_RUNTIME_GATE.json','parent_records':records,'parent_snapshots_prefix':[x for x in gate['runs']['forced']['snapshots'] if Path(x['file']).name in [f'x0_step{i:03d}.pt' for i in range(15)]],'parent_router_sha256':gate['runs']['forced']['router_file_sha256'],'parent_video':gate['runs']['forced']['video'],'noise_cache_relative':'audit/r89_short_0358_seed2026101701_noise.pt','noise_cache_sha256':'789250cdd8405a4c69a756d9c8c239868387b6fa200403285d2b79eeb6cdfe5f','new_noise_relative':'audit/r97_short_0358_seed2026101701_noise.pt','definition_sha256':sha(R/'design/CASE_DEFINITION.json'),'event_review_sha256':sha(R/'design/EVENT_REVIEW.json')})
(R/'configs/prompts').mkdir(exist_ok=True);(R/'configs/prompts/short_0358.txt').write_text(case['prompt'])
g=copy.deepcopy(read(actual/'forced_graph.json'))
for node,key,suf in [('5','audit_dir','audit'),('6','audit_dir','audit'),('50','audit_dir','audit/router'),('51','source_audit_dir','audit'),('52','output_dir','audit/x0')]:g[node]['inputs'][key]=remote+'/'+suf
g['5']['inputs']['run_id']='r97_short_0358_shared';g['51']['inputs']['source_run_id']='r97_short_0358_shared'
for node in ('6','50','51','52'):g[node]['inputs']['run_id']=run
g['6']['inputs']['pair_id']='r97_short_0358_seed2026101701';g['14']['inputs']['filename_prefix']=run;g['50']['inputs']['step_end']=20
write(R/'configs/graphs'/(run+'.json'),g)
write(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()})
write(R/'configs/storage_policy.json',{'startup_required_free_bytes':8*1024**3,'estimated_output_bytes':2*1024**3,'note':'One107frame job; sourceRGB/blob cache and21AV snapshots remain remote. Estimate only.'})
kernels={}
for p in read(B/'configs/runtime_kernel_hashes.json'):
 assert sha(R/p)==sha(P/p)
 kernels[p]={'parent_file':str(P/p),'parent_sha256':sha(P/p),'current_sha256':sha(R/p),'byte_equal':True}
write(R/'configs/runtime_kernel_hashes.json',kernels)
# Only administrative adapters receive renamed run IDs and singleton terminology.
for name in ('job.py','service.py','execution_gate.py','check_storage.py','run_queue.py'):
 p=R/'scripts'/name;s=p.read_text().replace('r90_','r97_').replace('r90-','r97-').replace('R90','R97').replace('h3-timing-flexiact-p1-control-r90-20261018','h3-timing-ive-glasses-schedule-r97-20261018')
 s=s.replace('ROOT_NATIVE_APPROVAL','ROOT_RUN_APPROVAL').replace('approve-native','approve-run').replace('root_run_native.py','root_run_control.py').replace('Native prompt control','fixed schedule control').replace('root Native','root single-run').replace('single Native','single output')
 p.write_text(s)
p=R/'extensions/H3PairAudit/__init__.py';p.write_text(p.read_text().replace("'r89_'","'r97_'"))
# Single output uses an already-complete historical fixed parent, not a fabricated local Native.
p=R/'scripts/job.py';s=p.read_text();a=s.index('def require_native_generation(');b=s.index('\n\ndef submit(',a)
s=s[:a]+'''def require_native_generation(binding, owner):
    from parent_evidence import verify_parent
    if binding['arm'] != 'extended':raise ValueError('unregistered control arm')
    verify_parent(RUN, include_snapshots=False)
'''+s[b:];p.write_text(s)
p=R/'audit/root_run_native.py';s=p.read_text().replace('r90_contract','r97_contract').replace('r85_root','parent_root').replace('r90_one_leg__movie_man_9_seed2026101701_noise.pt','r97_short_0358_seed2026101701_noise.pt').replace('R85','R89').replace('r90','r97').replace('P1 Native','extended fixed control').replace('single Native','single control').replace('approve-native','approve-run').replace('verify_native.py','verify_control.py').replace('NATIVE_RUNTIME_GATE','CONTROL_RUNTIME_GATE').replace('verify_native.log','verify_control.log')
s=s.replace("service.write_json(audit/'ORIGINAL_AV_NOISE.json',prepare_original_noise())","from parent_evidence import verify_parent\n        service.write_json(audit/'PARENT_ACTUAL_VERIFIED.json',verify_parent(ROOT,include_snapshots=True))\n        service.write_json(audit/'ORIGINAL_AV_NOISE.json',prepare_original_noise())")
(R/'audit/root_run_control.py').write_text(s);p.unlink()
print('Prepared metadata, original inputs, graph and administrative skeleton.')
