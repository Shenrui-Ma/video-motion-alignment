"""Package measured R16 results without changing any frozen measurement/runtime."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
P=Path(__file__).resolve().parent
read=lambda n:json.loads((P/n).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(n,d):(P/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
compact=read('four_arm_compact.json')
quality={'reviewed_arms':['roi','uniform'],'fixed_frames_actually_viewed':[55,86,105],
 'segment_archived_half_open':[42,82],'segment_sample_frames_actually_viewed':[42,47,52,57,62,67,72,77],
 'gross_layout_and_edit_presence':'In the inspected fixed frames/contact-sheet samples, both arms retain white curtains, cabinet, table, white bench, and adult male gray top/black trousers. No gross black-background or silhouette collapse observed.',
 'motion':'ROI and Uniform visible body poses are similar and remain delayed by the frozen timing measurements; no claim of pixel identity.',
 'limitations':['Hands and rapid-motion regions are blurred; fine finger quality unverified.','Exact Sam likeness unverified.','Sampled fixed frames do not establish full-clip absence of flicker or ghosting.','The complete [42,82) clips are archived; continuous playback was not used as a separate validated quality score.'],
 'full_quality_pass':False,
 'artifacts':[{'path':str(p),'sha256':sha(p)} for p in sorted((P/'visual_review').glob('*')) if p.is_file()]}
put('FINAL_VISUAL_REVIEW.json',quality)
runs={}
for arm in ['roi','uniform']:
 run=f'r16_s05_{arm}_6to14'; prov=P/'pilot'/f'{run}_provenance'
 h=json.loads((prov/'history.json').read_text()); times={k:v['timestamp'] for k,v in h['status']['messages'] if k in ['execution_start','execution_success']}
 pose=read(f'pilot/{run}_00001_.pose.json'); integ=read(f'replication/{run}_integrity.json'); archive=json.loads((prov/'archive_manifest.json').read_text())
 assert integ['passed'] and archive['status']=='archived_and_measured'
 assert sha(P/'raw'/archive['relative_video'])==archive['video_sha256']
 obs=compact['observability'][arm]; vals=obs['50:65']['direction_lags_by_threshold']+obs['50:65']['position_lags_by_threshold']
 runs[arm]={'run_id':run,'history_status':h['status']['status_str'],'integrity_pass':integ['passed'],'observability':obs,
 'strict_primary_direction_and_wrist_both_thresholds_abs2':all(v is not None and abs(v)<=2 for v in vals),
 'geometry':archive['expected_geometry'],'raw_path':str(P/'raw'/archive['relative_video']),'raw_sha256':archive['video_sha256'],
 'NFE':integ['actual_NFE'],'sampler_updates':integ['sampler_updates'],'callbacks':integ['callbacks'],
 'routed_blocks':integ['routed_blocks'],'active_indices_zero_based':integ['active_indices'],
 'whole_history_wall_seconds':(times['execution_success']-times['execution_start'])/1000,
 'pose_CPU_seconds':pose['statistics']['elapsed_s'],'integrity_CPU_seconds':integ['cpu_seconds'],
 'detection_statistics':{k:pose['statistics'][k] for k in ['processed_frames','missing_person_frames','multiple_person_frames','ambiguous_selection_frames']},
 'archive_manifest':str(prov/'archive_manifest.json'),'integrity_report':str(P/f'replication/{run}_integrity.json')}
low=read('lowerbody_aux/summary.json')
lowcompact={k:[{q:x[q] for q in ['window','feature','threshold','status','reliable_lag_frames']}|{'same_frame_error':x['same_frame']['error'],'same_frame_coverage':x['same_frame']['coverage']} for x in rows] for k,rows in low['runs'].items()}
summary={'round':'R16','status':'complete','generated_utc':datetime.now(timezone.utc).isoformat(),
 'scientific_outcome':'Both the frozen source-forearm ROI distribution and its equal-alpha-sum uniform control fail to correct the known primary delay. No demonstrated useful ROI advantage over Uniform in this case.',
 'scope':'One already selected development source05/Sam/seed2026101311 case; not independent generalization. Novelty and empirical efficacy are separate questions.',
 'runs':runs,'baseline_observability':{k:compact['observability'][k] for k in ['native','full']},
 'common_support':compact['four_arm_common_support'],
 'lowerbody_auxiliary':{'pairwise_support_not_four_arm_common_support':True,'runs':lowcompact},
 'quality_review':str(P/'FINAL_VISUAL_REVIEW.json'),'unknowns_preserved':True,
 'geometry_hypothesis':{'file':str(P/'MASK_COVERAGE_INTERPRETATION.md'),'status':'post-outcome diagnostic only','conclusion':'Source-mask coverage is poor for the visible delayed arm; clean endpoint/final pose is not actual noisy state or hidden query support, so the causal explanation remains unproven.'},
 'integrity_boundaries':['Original 63-file science payload unchanged except the documented administrative exact-R17-process allowance.','Sealed evaluator originals remain intact. New v2 evaluation-only paths accommodate actual router status sampling and manifest schema; success is independently checked.','Equal per-bin alpha sum is not equal attention-mass-weighted correction dose.'],
 'cost_note':'Record only. No efficiency/speed explanation or extra speed experiment.',
 'cleanup':read('replication/resource_cleanup/cleanup.json'),
 'resource_note':'R16 exact service17134 was verified absent and GPU2 idle before root reused GPU2 for R18. This report does not claim GPU2 remains idle now.'}
put('FINAL_SUMMARY.json',summary)
# Manifest excludes ephemeral lock/cache files and itself; preserved preliminary evidence remains included.
items=[]
for p in sorted(P.rglob('*')):
 if not p.is_file() or '__pycache__' in p.parts or p.name.endswith(('.lock','.tmp')) or p.name=='FINAL_REVIEW_MANIFEST.json':continue
 items.append({'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)})
put('FINAL_REVIEW_MANIFEST.json',{'status':'complete','created_utc':datetime.now(timezone.utc).isoformat(),'files':items,'count':len(items),'mutable_after_manifest':False})
print(json.dumps({'runs':{k:{j:v[j] for j in ['run_id','strict_primary_direction_and_wrist_both_thresholds_abs2','whole_history_wall_seconds','pose_CPU_seconds']} for k,v in runs.items()},'manifest_files':len(items)}))
