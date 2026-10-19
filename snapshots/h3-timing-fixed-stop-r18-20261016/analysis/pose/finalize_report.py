"""Summarize already-frozen R18 results; no new model/pose computation."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
P=Path(__file__).resolve().parent;run='r18_s05_full_6to11'
def read(n):return json.loads((P/n).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(n,d):(P/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
comp=read('four_arm_compact.json');integ=read('replication/'+run+'_integrity.json');gate=read('replication/'+run+'_official_completed_gate.json')
prov=P/'pilot'/(run+'_provenance');h=json.loads((prov/'history.json').read_text());archive=json.loads((prov/'archive_manifest.json').read_text());pose=read('pilot/'+run+'_00001_.pose.json')
assert integ['passed'] and gate['passed'] and len(gate['exact_comparisons'])==8 and all(all(x['video_audio_equal'].values()) for x in gate['exact_comparisons'])
raw=P/'raw'/archive['relative_video'];assert sha(raw)==archive['video_sha256']==pose['video']['sha256']
q={'run_id':run,'fixed_frames_actually_viewed':[55,86,105],'gross_layout_and_edit_presence':'White curtain, cabinet, table, white bench and adult male gray-top/black-trouser edit remain visible. No gross black-background/silhouette collapse in these inspected frames.',
 'observed_limitations':['Visible hands/fast-motion regions are blurred or trail; fine hand/finger quality is not certified.','Exact Sam likeness unverified.','Fixed frames do not establish whole-clip absence of flicker/ghosting or equal quality to Full.'],
 'full_quality_pass':False,'artifacts':[{'path':str(P/'pilot'/(run+f'_00001_.frame{f:03d}.pose.jpg')),'sha256':sha(P/'pilot'/(run+f'_00001_.frame{f:03d}.pose.jpg'))} for f in [55,86,105]]}
put('FINAL_VISUAL_REVIEW.json',q)
times={k:v['timestamp'] for k,v in h['status']['messages'] if k in ['execution_start','execution_success']}
obs=comp['observability']['r18'];primary=obs['50:65'];val=primary['direction_lags_by_threshold']+primary['position_lags_by_threshold']
summary={'round':'R18','status':'complete','generated_utc':datetime.now(timezone.utc).isoformat(),'run_id':run,
 'scientific_outcome':'Fixed Full routing at zero-based indices6..11 retains final primary timing within±2 on this already selected development case. It has higher primary same-frame pose error than Full6..14 and does not validate an online stopping policy.',
 'strict_primary_direction_and_wrist_both_thresholds_abs2':all(x is not None and abs(x)<=2 for x in val),
 'observability':comp['observability'],'four_arm_common_support':comp['four_arm_common_support'],
 'same_support_note':'Every table recomputes intersection and shared minimum-confidence weights for that exact arm set; values should not be compared numerically across different arm sets.',
 'integrity_pass':True,'official_checks':gate['checks'],'exact_comparisons':gate['exact_comparisons'],
 'capture_indices_zero_based':[5,6,7,8,9,10,11,12,15,19],'capture_file_count_including_final':11,
 'NFE':20,'sampler_updates':20,'callbacks':20,'routed_blocks':300,'active_indices_zero_based':list(range(6,12)),
 'whole_history_wall_seconds':(times['execution_success']-times['execution_start'])/1000,'capture_timing':gate['timing'],
 'pose_CPU_seconds':pose['statistics']['elapsed_s'],'integrity_CPU_seconds':integ['cpu_seconds'],'common_support_CPU_seconds':comp['cpu_seconds'],
 'cost_note':'Recorded only; no walltime superiority claim, no speed diagnosis.',
 'raw_path':str(raw),'raw_sha256':archive['video_sha256'],'geometry':archive['expected_geometry'],
 'detection_statistics':{k:pose['statistics'][k] for k in ['processed_frames','missing_person_frames','multiple_person_frames','ambiguous_selection_frames']},
 'quality':q,'all_unknowns_retained':True,'cleanup':read('replication/resource_cleanup/cleanup.json'),
 'live_resource_snapshot':read('replication/resource_cleanup/live_after_completion.json'),
 'scope':['Known development source05/Sam/seed2026101311; schedule selected after R10/R15 diagnostics.','Not an independent sample, threshold validation, generalization or architecture novelty claim.','R10 index12 is an unchosen native endpoint at the shared prefix; later R18 evolution is new measured evidence.','Raw/capture identities do not imply final video equals Full6..14.','Reference-to-generated timing shift is not semantic action deletion.']}
put('FINAL_SUMMARY.json',summary)
items=[]
for p in sorted(P.rglob('*')):
 if not p.is_file() or '__pycache__' in p.parts or p.name.endswith(('.lock','.tmp')) or p.name=='FINAL_REVIEW_MANIFEST.json':continue
 items.append({'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)})
put('FINAL_REVIEW_MANIFEST.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'count':len(items),'files':items})
print(json.dumps({'strict_primary':summary['strict_primary_direction_and_wrist_both_thresholds_abs2'],'wall_s':summary['whole_history_wall_seconds'],'pose_s':summary['pose_CPU_seconds'],'integrity_s':summary['integrity_CPU_seconds'],'file_count':len(items)}))
