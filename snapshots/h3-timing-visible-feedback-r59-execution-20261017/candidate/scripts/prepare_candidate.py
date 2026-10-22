"""Build small, CPU-only fixed-five/four-arm candidates; actual R57 parents remain pending."""
import copy, hashlib, json, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent
R55=BASE/'h3-timing-ivebench-auto-r55-20261017'
R56=BASE/'h3-observer-local-bones-r56-20261017'
R57=BASE/'h3-timing-ivebench-prompt-adaptation-r57-20261017'
REMOTE='/data3/researcher/h3_runs/timing_visible_feedback_r59_20261017'
ARMS=('native','visible_only','visible_fallback','weak_only')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def main():
 parent=read(R57/'configs/scientific_contract.json');old=read(R55/'configs/protocol.json')
 cases=[];bindings={};parent_records={}
 for case in parent['cases']:
  source=case['source_id'];p1=R57/case['prompt_file']
  assert p1.read_text()==case['prompt'] and sha(p1)==case['prompt_sha256']
  planned=R57/'configs/graphs'/f"{case['run_id']}.json"
  pose=R56/'source_snapshot/configs/parents'/source/'source.pose.json'
  target=ROOT/'configs/source_poses'/source/'source.pose.json';target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(pose,target)
  parent_records[source]={'status':'PENDING','ready':False,'parent_run':case['run_id'],'planned_graph_sha256':sha(planned),'actual_noise':None,'actual_conditioning':None,'actual_captures':None,'actual_RUN_GATE':None,'actual_FILE_INVENTORY':None}
  template=read(R55/'configs/graphs'/f"r55_{source}_seed2026101701_auto.json")
  def mapstrings(v,run):
   if isinstance(v,str):return v.replace('timing_ivebench_auto_r55_20261017','timing_visible_feedback_r59_20261017').replace(f'r55_{source}_seed2026101701_auto',run).replace(f'r55_{source}_shared',run+'_shared')
   if isinstance(v,dict):return {k:mapstrings(x,run) for k,x in v.items()}
   if isinstance(v,list):return [mapstrings(x,run) for x in v]
   return v
  for arm in ARMS:
   run=f'r59_{source}_seed2026101701_{arm}'
   c={k:copy.deepcopy(case[k]) for k in ['source_id','seed','prompt','video','provenance','reference_video_count','reference_image_count','valid_frame_count','original_task','video_sha256','provenance_sha256','geometry','evaluation_crop_xywh','original_source','prompt_file','prompt_sha256']}
   c.update(run_id=run,arm=arm,parent_run=case['run_id'],parent_status='PENDING',parent_root='/data3/researcher/h3_runs/timing_ivebench_prompt_adaptation_r57_20261017/analysis/postrun/captured/batch',parent_planned_graph='configs/planned_parents/'+planned.name,parent_planned_graph_sha256=sha(planned),source_pose_path=str(target.relative_to(ROOT)),source_pose_sha256=sha(target),parent_conditioning=None,parent_noise=None,parent_captures=None,parent_file_inventory=None)
   cases.append(c);g=mapstrings(template,run);g['5']['inputs']['prompt']=case['prompt']
   write(ROOT/'configs/graphs'/f'{run}.json',g)
   bindings[run]={'parent_P1_prompt_equal':g['5']['inputs']['prompt']==case['prompt'],'video_input_equal':g['22']['inputs']==read(planned)['22']['inputs'],'seed_equal':g['6']['inputs']['noise_seed']==case['seed'],'actual_noise_condition_equality':'PENDING','native_reuse_preferred':arm=='native'}
 protocol=copy.deepcopy(old)
 protocol.update(schema='r59-visible-feedback-four-arms-cpu-v1',scope='Fixed five IVEBench P1 tasks, four preregistered candidate arms; all outcomes retained.',cases=cases,preparation_status='CPU_CANDIDATE_R57_ACTUAL_PARENTS_PENDING',GPU_launch_authorized=False)
 protocol['observer'].update(feature_provider='scripts/arm_features.py',feature_provider_sha256=sha(ROOT/'scripts/arm_features.py'),descriptor_version='r56-arm-bone-unit-v1',required_joints='each descriptor uses its shoulder/elbow/wrist; no hip anchors',complete_rows='geometry.windows() x bilateral/left/right descriptors',scientific_unknown='Visible-only Native; fallback arm only complete all baseline UNKNOWN within fixed weak schedule')
 protocol['weak']={'alpha':.25,'indices':list(range(6,15)),'bins':list(range(27)),'blocks':list(range(50)),'spatial_support':'all canvas query positions','padding':'included in full-bin intervention; excluded from observation/score valid prefix','formula':'O + alpha * m_ref * (O_same_time_ref - O_ref)','candidate_history':'never receives fallback events','strength_schedule_tuning':'none'}
 protocol['arms']={'native':{'observer':False,'intervention':'none','reuse':'actual R57 P1 Native after archive binding'},'visible_only':{'observer':True,'intervention':'original signed persistent local time routing, alpha1; UNKNOWN Native'},'visible_fallback':{'observer':True,'intervention':'Visible-only; mutually exclusive alpha.25 whole-canvas fallback only complete allUNKNOWN and index6..14'},'weak_only':{'observer':False,'intervention':'fixed alpha.25 whole-canvas index6..14'}}
 protocol['prefix'].update(all_OFF='Compare actual R57 P1 final AV after parent binding',availability='PENDING actual five R57 histories and21AV endpoints')
 protocol['inherited_rule'].update(parent='R55 signed control + R56 arm-only feature provider',detector_policy_actuator_unchanged=False,unchanged='metrics/dual-confidence/gain/persistence/attention arithmetic/Euler; only feature entry and arm decision schedule change')
 protocol['policy_choice']['source_result_used']='R55 frozen signed policy inherited before new P1 outputs; no new tuning'
 protocol['resources']['capacity_status']='PENDING actual R59 branch and P1 conditioning check; R55 measurements are historical evidence only'
 write(ROOT/'configs/protocol.json',protocol)
 write(ROOT/'configs/scientific_contract.json',{'schema':'r59-fixed-five-four-arm-contract-v1','status':'CPU_CANDIDATE','cases':cases,'planned_sources':5,'arms':list(ARMS),'paired_parent_status':'PENDING','same_seed':2026101701,'sampler':'Euler20 CFG1','geometry':{'width':1312,'height':736,'frames':90,'fps':24},'fallback':protocol['weak'],'source_inputs':'external byte-bound R57/R54 inputs; no media copied','novelty_claim':False})
 write(ROOT/'configs/PARENT_CLOSURE.json',{'schema':'r59-parent-closure-v1','status':'PENDING_R57_ACTUAL_ARCHIVES','ready':False,'cases':parent_records})
 write(ROOT/'configs/admission.json',{'approved':False,'ready':False,'reason':'CPU preparation only; R57 actual parents and new runtime gates pending'})
 write(ROOT/'audit/GRAPH_BINDINGS.json',bindings)
 shutil.copyfile(R57/'configs/input_bindings.json',ROOT/'configs/input_bindings.json')
 shutil.copyfile(R57/'PREPARATION_MANIFEST.json',ROOT/'source_snapshot/R57_PREPARATION_MANIFEST.json')
 p=ROOT/'extensions/H3AutomaticWindowRouter/transport.py';s=p.read_text().replace("PROTOCOL_SHA='b09311241ad27916430a1065537b06ea2ff0b6960c756aa4459f43e139285389'",f"PROTOCOL_SHA='{sha(ROOT/'configs/protocol.json')}'").replace('timing_ivebench_auto_r55_20261017','timing_visible_feedback_r59_20261017').replace('R55 WAITING_R54_ACTUAL_ARCHIVES','R59 WAITING_R57_ACTUAL_ARCHIVES');p.write_text(s)
 print('20 candidate graphs; actual R57 parent closure PENDING; no GPU entry authorized')
if __name__=='__main__':main()
