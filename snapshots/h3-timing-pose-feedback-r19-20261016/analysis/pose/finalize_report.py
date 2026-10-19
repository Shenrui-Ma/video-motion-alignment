"""Summarize completed and independently inspected R19 evidence, never infer labels."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
P=Path(__file__).resolve().parent;RUN='r19_s05_pose_observer'
def read(n):return json.loads((P/n).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(n,d):(P/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
comp=read('five_arm_compact.json');integ=read('replication/'+RUN+'_integrity.json');official=read('replication/'+RUN+'_official_completed_gate.json')
q=read('FINAL_VISUAL_REVIEW.json');assert q['actually_reviewed'] is True
prov=P/'pilot'/(RUN+'_provenance');archive=json.loads((prov/'archive_manifest.json').read_text());history=json.loads((prov/'history.json').read_text())
raw=P/'raw'/archive['relative_video'];pose=read('pilot/'+raw.stem+'.pose.json')
assert integ['passed'] and official['status']=='pass' and sha(raw)==archive['video_sha256']==pose['video']['sha256']
obs=comp['observability']['r19'];v=obs['50:65']['direction_lags_by_threshold']+obs['50:65']['position_lags_by_threshold']
times={k:d['timestamp'] for k,d in history['status']['messages'] if k in ['execution_start','execution_success']}
replay=read('replication/same_mask_R18_replay.json')
summary={'round':'R19','status':'complete','generated_utc':datetime.now(timezone.utc).isoformat(),'run_id':RUN,
 'strict_primary_direction_and_wrist_both_thresholds_abs2':all(x is not None and abs(x)<=2 for x in v),'observability':comp['observability'],
 'five_arm_common_support':comp['five_arm_common_support'],'same_support_note':'Every table uses the intersection and shared minimum-confidence weights of this exact arm set. Different arm sets are not directly comparable numeric error tables.',
 'actual_integrity_pass':True,'official_integrity':official,'independent_prefix_recheck':integ['independent_prefix_recheck'],
 'actual_full_indices_zero_based':integ['active_indices'],'NFE':integ['actual_NFE'],'Euler_updates':20,'callbacks':20,
 'routed_blocks':integ['routed_blocks'],'measurement_decisions':integ['measurement_decisions'],
 'same_R18_mask_replay':replay,'quality':q,
 'whole_history_wall_seconds':(times['execution_success']-times['execution_start'])/1000,'observer_wall_seconds':integ['observer_wall_seconds'],
 'final_pose_CPU_seconds':pose['statistics']['elapsed_s'],'integrity_CPU_seconds':integ['cpu_seconds'],'common_support_CPU_seconds':comp['cpu_seconds'],
 'cost_note':'Record only, no speed diagnosis or superiority claim. Observer total overlaps history walltime.',
 'raw_path':str(raw),'raw_sha256':archive['video_sha256'],'geometry':archive['expected_geometry'],
 'detection_statistics':{k:pose['statistics'][k] for k in ['processed_frames','missing_person_frames','multiple_person_frames','ambiguous_selection_frames']},
 'all_unknowns_retained':True,'cleanup':read('replication/complete_evidence/processes/cleanup.json'),
 'scope':['Known selected source05/Sam/seed2026101311 development case.','Changed measurement and explicit stop classifier jointly, not a pure sensor-only factor.','Same pose estimator family for control/evaluation; fixed-frame and segment review do not remove evaluation dependence.','An equal mask and exact R18 replay validates interface reproduction on this case, not adaptive superiority.','No architecture novelty, generalization, probability guarantee or efficiency advantage follows from this run.','Video-reference lag is distinct from semantic action deletion.']}
put('FINAL_SUMMARY.json',summary)
items=[]
for p in sorted(P.rglob('*')):
 if not p.is_file() or '__pycache__' in p.parts or p.name.endswith(('.lock','.tmp')) or p.name in ['FINAL_REVIEW_MANIFEST.json','consumer.log']:continue
 items.append({'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)})
put('FINAL_REVIEW_MANIFEST.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'count':len(items),'files':items})
print(json.dumps({'strict_primary':summary['strict_primary_direction_and_wrist_both_thresholds_abs2'],'NFE':summary['NFE'],'mask':summary['actual_full_indices_zero_based'],'file_count':len(items)}))
