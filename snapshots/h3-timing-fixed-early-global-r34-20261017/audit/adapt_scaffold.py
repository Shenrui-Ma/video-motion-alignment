from pathlib import Path
import json,hashlib,sys,shutil
r=Path(__file__).resolve().parents[1]; p=r/'scripts'
def j(path):return json.loads(path.read_text())
def dump(path,v):path.write_text(json.dumps(v,indent=2)+'\n')
def edit(path,a,b):
 s=path.read_text()
 if a not in s:
  assert b in s,(path,a);return
 path.write_text(s.replace(a,b))
rt=j(r/'configs/runtime.json');rt['port']=8498;dump(r/'configs/runtime.json',rt)
edit(p/'preflight.py',"rt['port']!=8496","rt['port']!=8498")
edit(p/'preflight.py',"p['seed']!=SEED or p['scientific_change']['to_query_bins']!=list(range(42)) or p['scientific_change']['at_denoising_index_zero_based']!=4","p['case']['seed']!=SEED or p['operator']['bins']!=list(range(42)) or p['schedule']['active_indices']!=[4]")
edit(p/'r34_contract.py','Frozen displaced-window','Frozen global early pulse')
edit(p/'prelaunch_gates.py','same87592','same87361')
edit(p/'prelaunch_gates.py','87592','87361')
v=p/'verify_completed.py'
edit(v,"t.require(c['initial_noise']==t.read_json(root/'configs/parent_counterfactual_summary.json')['initial_noise'],'sampler packed noise differs')","packed=torch.cat([x.reshape(1,1,-1) for x in saved['tensors']],dim=-1)\n    t.require(c['initial_noise']==signature(packed),'sampler packed noise differs from actual saved AV streams')")
edit(v,"t.read_json(root/'configs/parent_counterfactual_summary.json')['full_grid']","t.read_json(root/'configs/parent_captures.json')['sigmas_video']")
edit(v,"t.require(canonical_condition(c['conditioning']['tree'])==canonical_condition(t.read_json(root/'configs/parent_actual_condition_tree.json')['tree']),'actual processed condition differs')","canonical_condition(c['conditioning']['tree']) # current UUID correspondence only; old full tree was not archived")
edit(v,"expected_prefix=t.read_json(root/'design/evidence/ACTUAL_PREFIX_0_TO_4.json')['records']\n        old_cond_sha=t.read_json(root/'configs/parent_actual_condition_tree.json')['sha256']","expected_prefix=t.read_json(root/'PROTOCOL.json')['actual_native_prefix_evidence']")
edit(v,"actual_prefix(branches[n,b],expected_prefix[n],branches[n,b]['file'],old_cond_sha)","actual_prefix(branches[n,b],expected_prefix[n],branches[n,b]['file'])")
edit(v,"==expected_prefix[4]['input_signature']",'')
edit(v,"packedinput4 signature only because old rawinput was not saved","historical packedinput4 and processed full condition tree unavailable; only current same-state input and tree are verified")
edit(r/'tests/real_comfy_cpu_smoke.py','actual_seed1311_noise_cold_hit_pass','actual_seed1701_noise_cold_hit_pass')
edit(r/'tests/test_evidence.py','test_actual_R27_final_and_step_metadata','test_actual_R26_final_and_step_metadata')
edit(r/'tests/test_evidence.py',"Path('/Users/researcher/DevProjects/h3-timing-auto-controller-r27-20261017/audit/gpu_dynamic_union_gate.json')","ROOT/'configs/inherited_actual87361_kernel.json'")
shutil.copyfile(r/'audit/inherited_actual87361_kernel.json',r/'configs/inherited_actual87361_kernel.json')
old=Path('/Users/researcher/DevProjects/h3-timing-window-location-r33-20261017')
shutil.copyfile(old/'configs/kernel_provenance.json',r/'configs/kernel_provenance.json')
parent=Path('/Users/researcher/DevProjects/h3-timing-auto-fresh-r28-20261017')
sha=lambda x:hashlib.sha256(x.read_bytes()).hexdigest()
dump(r/'configs/kernel_inheritance.json',{'parent_root':'/data5/researcher/h3_runs/timing_auto_fresh_r28_20261017','parent_manifest_sha256':sha(parent/'audit/deploy_manifest_v1.json'),'parent_protocol_sha256':sha(parent/'configs/protocol.json'),'kernel_gate_sha256':sha(r/'configs/inherited_actual87361_kernel.json'),'scope':'Actual R28 same87361/full42bin kernel evidence with identical numerical source. No current H3 forward, memory, actual condition or prefix result is inherited.'})
b=p/'build_manifest.py';edit(b,'source05 parent','source40372 parent');edit(b,"for folder in ('scripts','extensions','tests','configs','inputs','design','parent_evidence'):","for rel in ('PROTOCOL.json','README.txt','COMPARABILITY.txt','FREEZE.json'):\n  path=root/rel;files[rel]={'bytes':path.stat().st_size,'sha256':sha(path)}\n for folder in ('scripts','extensions','tests','configs','inputs'):")
edit(b,'timing_forward_reverse_r30_20261017/inputs','timing_global_full_r29_20261017/inputs')
(r/'configs/IMPLEMENTATION.txt').write_text('''R34 fixed early global pulse\n\nOne source40372/Sam/seed1701 development control. Full at zero-based denoising index4, all42 temporal bins/allspatial/all50blocks, alpha1/radius0. Native every step and one extra Full:21NFE,20Euler,20callbacks,1050blocks,50routes. No online observer or adaptive window. Numerical Router/core/layout/mask and dynamic support retain parent bytes.\n\nR26 actual clean8 condition entities, actual AV noise, graph/core/seed and five normalized AV snapshots0..4 bind this source. Historical R26 packedinput4 and full processed/postaugmentation tree were not archived; no such old equality is asserted. Current tree/input4 and Native/Full same-state equality are recorded. Full4 and future states are never claimed to match old Native.\n\nR28 inherited actual87361 kernel gate covers numerical geometry only. Root resource approval and each actual runtime gate remain required. 4 root design files are immutable. Snapshot/condition hash cost is recorded separately from model inference. Current Native/final21 captures plus21branch PTs saved; static selection never fabricates observations.\n''')
(r/'configs/DEPLOYMENT.txt').write_text('''R34 fixed early global single pulse; root is sole GPU launcher.\n1. Extract sealed tar to /data5/researcher/h3_runs/timing_fixed_early_global_r34_20261017 and verify deploy_manifest. Copy two immutable input files with the same names from timing_global_full_r29_20261017/inputs; verify configs/input_hashes.json.\n2. Run existing Comfy Python scripts/preflight.py. Root fills audit/resource_admission.json and configs/admission.json using actual resource/owner evidence; GPU2/8498. scripts/preflight.py --live requires exact inherited R28 actual87361 kernel and current resource bindings.\n3. Use scripts/launch_remote.py --service-only with root preCUDA runpy gate if a peer automatic service is active. Register exact PID/UID/start/cmd with the peer before releasing CUDA. Once service is ready call scripts/start_controller.py; start controller once under its lock.\n4. One job,7200s bound,12h service bound and1800s idle hold. Submission bounded600s strict peer gate; no unknown PID allowed. Root can use queue.finalize boolean after archive with an explicit release record.\n5. Read-only scripts/verify_completed.py --allow-resident requires actual R26 normalized x0_step000..004 at PROTOCOL.actual_native_prefix_evidence paths; no new native replay. Postrun evidence does not substitute for these actual run gates.\n''')
# Bind all parent metadata + immutable root design before deriving graph.
evidence={str(x.relative_to(r)):sha(x) for x in (r/'configs').glob('parent*.json')}
for name in ('PROTOCOL.json','README.txt','COMPARABILITY.txt','FREEZE.json','configs/source.pose.json','configs/source_provenance.json','configs/input_hashes.json','configs/model_hashes_host9.json'):
 evidence[name]=sha(r/name)
dump(r/'configs/evidence_hashes.json',evidence)
sys.path.insert(0,str(p));import r34_contract as c
g=c.expected_graph(r);gp=r/'configs/graphs'/f'{c.RUN_ID}.json';gp.parent.mkdir(exist_ok=True);dump(gp,g)
dump(r/'configs/job_registry.json',{'jobs':{c.RUN_ID:{'seed':c.SEED,'arm':'static_global','case':{'source_id':'40372'},'graph_sha256':sha(gp)}}})
print('R34 scaffold adapted; tests pending')
