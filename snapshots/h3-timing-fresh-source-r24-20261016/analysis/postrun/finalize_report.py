"""Derived descriptive report; original metrics, acceptance gates, and media stay unchanged."""
import json,hashlib,csv,html
from pathlib import Path
P=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
d=read(P/'COMPACT_RESULTS.json');state=read(P/'STATE.json')
if len(d['runs'])!=8 or len(d['pairs'])!=4 or state['phase']!='all_eight_CPU_complete' or not read(P/'BATCH_CHECKS.json')['passed']:raise ValueError('Batch not complete')
windows={'fresh_a':[[44,61],[17,34],[82,99]],'fresh_b':[[64,81],[23,40],[103,120]]}
def lag(run,conf,win,feature):
 rows=[x for x in d['timing'] if x['run_id']==run and x['confidence']==conf and x['window']==win and x['feature']==feature]
 if len(rows)!=1:raise ValueError('metric selection')
 r=rows[0];return {'lag':r['reliable_lag_frames'],'status':r['status'],'flags':r['flags']}
def common(key,conf,win,feature):
 rows=[x for x in d['common_support'] if x['pair']==key and x['confidence']==conf and x['window']==win and x['feature']==feature]
 if len(rows)!=1:raise ValueError('common selection')
 return rows[0]
def fmt(x):return 'UNKNOWN' if x['lag'] is None else f"{x['lag']:+d}"
primary=[];costs=[];sections=[]
for cid in ['fresh_a','fresh_b']:
 for seed in [2026101610,2026101611]:
  key=f'{cid}_seed{seed}';row={'pair':key,'primary_window':windows[cid][0],'metrics':{},'common_support':{}}
  for conf in [.3,.5]:
   row['metrics'][str(conf)]={}
   for arm in ['native','full_6to14']:
    run=f'r24_{cid}_seed{seed}_{arm}';row['metrics'][str(conf)][arm]={f:lag(run,conf,windows[cid][0],f) for f in ['arm_direction','wrist_relative','left_arm_direction','right_arm_direction']}
   row['common_support'][str(conf)]={f:common(key,conf,windows[cid][0],f) for f in ['arm_direction','wrist_relative']}
  primary.append(row)
  sections.append(f'<section><h2>{html.escape(key)}</h2><p>正常时序对照。参考视频 / 编辑后视频 / 编辑＋时序引导后视频。</p><video controls loop preload="metadata" src="{key}/full_length.mp4"></video><p><a href="{key}/index.html">查看固定截图、主窗正常速度与半速对照</a></p></section>')
for run,r in sorted(d['runs'].items()):
 e=r['execution'];c=r['complete'];costs.append({'run_id':run,**{k:e[k] for k in ['NFE','callbacks','Euler_updates','job_wall_seconds','capture_wrapper_seconds','copy_snapshot_seconds','integrity_seconds']},'CPU_consume_seconds':c['elapsed_seconds']})
summary={'scope':'Two new source videos × two preselected seeds × Native/Full; normal controls, no delay failure selected from these generated results.','primary':primary,'costs':costs,'all_run_gates_passed':all(r['execution']['passed'] and r['local_playback_verified'] for r in d['runs'].values()),'all_pair_gates_passed':all(r['passed'] for r in d['pairs'].values()),'cross_seed_noise_checks':read(P/'BATCH_CHECKS.json'),'pose_curve_count':len(d['timing']),'lag_candidates_per_curve':49,'compact_results_sha256':sha(P/'COMPACT_RESULTS.json'),'limitations':d['limitations']}
(P/'FINAL_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
lines=['R24 FINAL — two fresh sources, two seeds, normal controls','', 'All eight actual runs and four same-seed pairs passed. Actual input/condition/noise, all five x0 tensor inventory/metadata/finite/signature checks,20NFE/20callbacks/1000blocks with Native0/Full450routes, prefix005 video/audio equality, and141frame1312×736/24fps/5.875s physical playback gates pass. Cross-seed actual noise differs. Both pairs for both seeds have received independent read-only review.','', 'Primary lag in frames: direction / wrist; positive means the edited motion is later. UNKNOWN remains unreliably observed.']
for r in primary:
 for conf in ['0.3','0.5']:
  a=r['metrics'][conf]['native'];b=r['metrics'][conf]['full_6to14'];lines.append(f"{r['pair']} conf={conf}: Native {fmt(a['arm_direction'])}/{fmt(a['wrist_relative'])}; Full {fmt(b['arm_direction'])}/{fmt(b['wrist_relative'])}")
lines+=['','These four Native outputs are normal near-synchronous controls. User visual inspection agrees. At.3 their primary direction/wrist stay within−2..−1frames; Full stays near−1. This round does not demonstrate repair of a delayed action. At.5 wrists are UNKNOWN in all four primary pairs, and B seed1611 primary direction is also UNKNOWN. These are support limits, not substitute estimates.','','Primary same-time shape errors on common support (descriptive):']
for r in primary:
 for f in ['arm_direction','wrist_relative']:
  c=r['common_support']['0.3'][f];n=c['runs']['native']['same_frame_error_on_common_support'];v=c['runs']['full']['same_frame_error_on_common_support'];lines.append(f"{r['pair']} {f}: commoncoverage={c['common_valid_fraction']:.6f}, Native={n:.6f}, Full={v:.6f}, status={c['status']}")
lines+=['','The primary common-support errors are smaller under Full in these cases. This remains a local auxiliary observation. Outer-window effects are mixed: B seed1611 window23–40 direction is worse at both thresholds; first-seed B early wrist and late direction also worsen. All qualified/unqualified values and complete49lag curves are retained in COMPACT_RESULTS.json. No global quality improvement, population robustness, or architectural novelty is inferred.','','Visual review: all five predetermined frames per pair are presented at identical scale in full field. Source gray/green lighting can differ from both edited outputs; scene layout remains recognizable in the inspected frames. Fast hands contain blur; B77 has face occlusion and a hand leaving the frame. Fixed-frame inspection is separate from timing and does not rate continuous flicker or exact real-person identity. The visual-verdict presentation score is only a layout/caption check.','','Native sparse observer: four trajectories × captured indices005/010/015/019 × three source-only windows yielded48 correlated observations with lag−1or0 and no>=4flag. Existing005 curves were reused by SHA. Only two source videos are represented; this is not all20steps, no online intervention decision was executed, and there is no intermediate independent pose truth. The full-grid gap5 descriptor includes background/global motion and spans17physicalframes. See ../native_sparse_step_observer/SUMMARY.txt.','','Execution costs (seconds; includes actual runtime conditions/caching, descriptive only):']
for c in costs:lines.append(f"{c['run_id']}: job={c['job_wall_seconds']:.3f}, sampler/capturewrapper={c['capture_wrapper_seconds']:.3f}, snapshotcopy={c['copy_snapshot_seconds']:.3f}, integrity={c['integrity_seconds']:.3f}, CPUconsume={c['CPU_consume_seconds']:.3f}, NFE={c['NFE']}")
lines+=['','Media entry: media/index.html; each pair has full5.875second video, fixed primary-context24fps and12fps clips, and five fixed screenshots. All columns retain the original physical frame numbers. Media use relative sibling files.','','CPU consumer completed and exited. No GPU service cleanup was requested or claimed; resident service lifecycle belongs to root. Large verified tensor archives remain on the remote filesystem with SHA inventories retained locally.']
(P/'FINAL_REVIEW.txt').write_text('\n'.join(lines)+'\n')
with (P/'COSTS.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(costs[0]));w.writeheader();w.writerows(costs)
(P/'media/index.html').write_text('<!doctype html><meta charset="utf-8"><title>R24 两个新素材·正常对照</title><style>body{background:#111;color:#eee;font:17px sans-serif;max-width:1600px;margin:30px auto;padding:0 16px}video{width:100%;height:auto}section{margin:40px 0}a{color:#8bc7ff}p{line-height:1.65}</style><h1>两个新素材，四组正常时序对照</h1><p>每个素材使用两个预定种子。原生编辑的主窗动作已接近同步，四组全部保留作为正常对照。各列按24fps原始帧号同步；下面分别展示完整5.875秒，详细页附固定截图与主窗附近慢放。</p><p>Full沿用固定时序引导，在从0计数的去噪步骤6–14启用。主窗误差与可观测覆盖率、外窗变化和画面质量分别记录。</p>'+''.join(sections))
print(json.dumps({'passed':summary['all_run_gates_passed'] and summary['all_pair_gates_passed'],'report':str(P/'FINAL_REVIEW.txt'),'gallery':str(P/'media/index.html')}))
