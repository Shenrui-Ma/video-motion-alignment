from pathlib import Path
import json,hashlib,shutil
R=Path(__file__).resolve().parents[1]
O=R.parent/'h3-timing-auto-bedside-r35-20261017'
P=R.parent/'h3-timing-new-actions-native-r38-20261017'
A=P/'analysis/postrun/captured/batch'
B=R.parent/'h3-timing-auto-fresh-r32-20261017'
REMOTE='/data5/researcher/h3_runs/timing_auto_source51310_r40_20261017'
PR='/data5/researcher/h3_runs/timing_new_actions_native_r38_20261017'
RUN='r40_source51310_seed2026101701_auto';OLD='r35_s07_seed2026101311_auto';PN='r38_source_51310_seed2026101701_native'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(rel,v): (R/rel).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
assert sha(R/'configs/source.pose.json')=='57726240324645eb811539a67a1205b7c92fca8a9c2797587dd289273f0f635e'
evidence={
'parent_graph.json':A/f'configs/graphs/{PN}.json',
'parent_conditioning.json':A/f'audit/{PN}_conditioning.json',
'parent_noise.json':A/f'audit/{PN}_noise.json',
'parent_captures.json':A/f'audit/x0/{PN}/manifest.json',
'parent_file_inventory.json':A/'FILE_INVENTORY.json',
'parent_run_gate.json':A/'RUN_GATE.json',
'parent_runtime_gate.json':A/'RUNTIME_GATE.json',
'parent_runtime_provenance.json':A/'configs/runtime_provenance.json',
'parent_history.json':A/f'logs/{PN}_history.json',
'parent_router.json':A/f'audit/router/{PN}.json',
'source_provenance.json':A/'inputs/source_51310_provenance.json',
'inherited_actual87361_kernel.json':R.parent/'h3-timing-fixed-early-global-r34-20261017/configs/inherited_actual87361_kernel.json',
'r28_parent_manifest.json':B/'configs/r28_deploy_manifest.json'}
for name,src in evidence.items():shutil.copy2(src,R/'configs'/name)
write('audit/raw_evidence_copy.json',{name:{'source':str(src),'sha256':sha(src),'copied_sha256':sha(R/'configs'/name)} for name,src in evidence.items()})
for name in ('source_51310_video.mp4','source_51310_portrait.jpg'):shutil.copy2(A/'inputs'/name,R/'inputs'/name)
write('configs/input_hashes.json',{p.name:sha(p) for p in sorted((R/'inputs').iterdir())})
p=read(O/'configs/protocol.json');p['schema']='r40-source51310-auto-transfer-v1';p['scope']='One development-screened source51310 from the previously used night-court corpus, Sam identity, seed2026101701. Different source ID, not an independent unseen scene. Full141 automatic scanning with the frozen R27/R32/R35 rules. No hand-selected action windows or outcome-specific parameter changes.'
p['cases']=[dict(run_id=RUN,seed=2026101701,source_id='51310',parent_graph='configs/parent_graph.json',parent_root=PR,parent_run=PN,parent_conditioning='configs/parent_conditioning.json',parent_noise='configs/parent_noise.json',parent_captures='configs/parent_captures.json',parent_file_inventory='configs/parent_file_inventory.json')]
p['observer']['source_pose_sha256']=sha(R/'configs/source.pose.json')
p['prefix']={'old_indices':list(range(20)),'missing_indices':[],
'eligibility':'Current Native n remains comparable through firstON n inclusive. Chosen n is comparable strictly before firstON. Full n and all future historical Native endpoints permanently N/A after firstON, including later OFF.',
'all_OFF':'All20 current Native/chosen and finalAV are compared with actual R38 Native; final decoded141RGB is a separate measured outcome, never inferred from latent equality.',
'available_mismatch':'Abort and retain evidence on eligible current Native mismatch. No deferred first intervention or extra replay.',
'same_state':'Every current Native/Full pair shares exact packedinput/sigma/condition; RNG and parent resident state unchanged.',
'historical_limit':'R38 full processed/postaugmentation tree and packed sampler inputs were not saved; actual clean embedding entity, references, code/seed/noise and available AV endpoint bridges do not fabricate those missing historical objects.'}
p['evaluation']={'main':'all186 full-source scan rows with UNKNOWN retained; same Native/Auto common support','visual_frames':[0,24,48,72,96,120,140],'manual_window_used_online':False,'purpose':'multiple-case improvement relative to Native, approaching manual/fixed controls; no requirement to outperform manual or global'}
p.pop('design_protocol_sha256',None);p.pop('design_freeze_sha256',None)
write('PROTOCOL.json',p);write('FREEZE.json',{'schema':'r40-scientific-freeze-v1','files':{'PROTOCOL.json':sha(R/'PROTOCOL.json')},'no_GPU_authorized':True})
p['design_protocol_sha256']=sha(R/'PROTOCOL.json');p['design_freeze_sha256']=sha(R/'FREEZE.json');write('configs/protocol.json',p)
write('configs/queue.json',{'jobs':[RUN],'finalize':False})
write('configs/admission.json',{'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[],'root_live_review_required':True})
spec=read(O/'configs/r27_inheritance.json');spec['schema']='r40-r27-numerical-evidence-reuse-v1';spec['inherited_scope']='17 exact numerical files, common geometry/weights/decode/pose implementation only. Actual87361 layout kernel separately bound. Not new-source observation accuracy, current trajectory, or resource approval.';spec['independent_required']=['R38 actual current embedding entity and clean conditions/noise','eligible actual Native endpoints through firstON inclusive','root live GPU3 resource admission'];spec['adapter_changes']=['source51310 identifiers/root/port','dense 20-point historical endpoint availability','R38 parent gate and actual embedding entity'];write('configs/r27_inheritance.json',spec)
k=read(B/'configs/r28_inheritance.json');k['schema']='r40-same-layout-kernel-reuse-v1';k.pop('same_source_condition_noise_artifacts');k.pop('replaces_unrun_R28');k['administrative_changes']=['new case and scientific evidence','same87361 packed geometry only; source pixels/conditioning values differ','GPU3/8502 resource administrative binding'];write('configs/kernel_inheritance.json',k)
write('configs/inherited_policy.json',read(O/'configs/inherited_policy.json'))
# Explicit source-code edits only; immutable evidence above is never text-rewritten.
changes={}
def edit(rel,pairs):
 f=R/rel;text=f.read_text();before=sha(f)
 for old,new in pairs:
  assert old in text,(rel,old);text=text.replace(old,new)
 f.write_text(text);changes[rel]={'before_sha256':before,'after_sha256':sha(f),'exact_fragments':[a for a,b in pairs]}
oldroot='/data5/researcher/h3_runs/timing_auto_bedside_r35_20261017'
for rel in ['scripts/preflight.py','scripts/run_queue.py','scripts/job.py','scripts/verify_completed.py','tests/test_automatic.py','tests/test_admin_relocation.py','extensions/H3EventAudit/__init__.py']:
 edit(rel,[('from r35_contract import','from r40_contract import')])
for rel in ['scripts/service.py','extensions/H3EventAudit/__init__.py','extensions/H3AutomaticWindowRouter/transport.py','scripts/r35_contract.py']:
 edit(rel,[(oldroot,REMOTE)])
edit('scripts/service.py',[('PORT = 8497','PORT = 8502')]);edit('scripts/job.py',[("'h3-timing-auto-bedside-r35-20261017'","'h3-timing-auto-source51310-r40-20261017'")])
edit('scripts/r35_contract.py',[("One frozen source07 development transfer","One frozen source51310 development transfer"),('frozen R35 root','frozen R40 root'),("'r35_s07_shared'","'r40_source51310_shared'")]);(R/'scripts/r35_contract.py').rename(R/'scripts/r40_contract.py')
edit('scripts/run_queue.py',[('source07 job','source51310 job')])
edit('extensions/H3AutomaticWindowRouter/__init__.py',[(OLD,RUN)])
edit('extensions/H3AutomaticWindowRouter/transport.py',[("PROTOCOL_SHA='94f21c35abb197e2ef650c852e25a523fff78b64f375362308ab24c48e8c2602'","PROTOCOL_SHA='"+sha(R/'configs/protocol.json')+"'")])
edit('extensions/H3AutomaticWindowRouter/pair_gate.py',[("'case_role':'source07 previously inspected development transfer'","'case_role':'source51310 development-screened same-corpus transfer'"),("'prefix_evidence':'prefix_unavailable_due_to_early_intervention' if self.first_on is not None and self.first_on<5 else 'compare only archived eligible indices005/010/015/019; no fabricated earlier bridge'","'prefix_evidence':'all20 historical captures available; current Native through firstON inclusive; future permanently N/A'")])
edit('scripts/build_manifest.py',[("'r35-immutable-deploy-v1'","'r40-immutable-deploy-v1'"),("('extensions','scripts','tests','configs','inputs')","('extensions','scripts','tests','configs')")])
# Export the actual graph through the same production transformer.
import sys
sys.path.insert(0,str(R/'scripts'))
from r40_contract import expected_graph
parent=read(R/'configs/parent_graph.json');graph=expected_graph(parent,p['cases'][0]);write('configs/'+RUN+'.json',graph)
write('configs/graph_diff.json',{key:{'parent':parent.get(key),'current':graph.get(key)} for key in parent.keys()|graph.keys() if parent.get(key)!=graph.get(key)})
write('audit/explicit_code_edits.json',changes)
(R/'README.txt').write_text('R40 source51310/Sam seed2026101701 automatic controller case transfer. Root controls GPU launch. Same frozen R27/R32/R35 method, no manual action window. Physical_index in legacy audit means denoising index, not a video-frame time.\n')
(R/'COMPARABILITY.txt').write_text('Source51310 was selected after Native screening and comes from the previously used night-court corpus. R38 actual clean8 tensors/embedding entity/AV noise and all21 endpoint archives bind comparison. Historical processed/postaugmentation tree and packedinputs unavailable. Current Native through firstON is exactly compared; full and future are divergent. Final RGB equality is independent from AV latent equality. No new-method claim, no requirement to beat manual/fixed controls.\n')
print('prepared',RUN,'protocol',sha(R/'configs/protocol.json'),'raw_evidence',len(evidence))
