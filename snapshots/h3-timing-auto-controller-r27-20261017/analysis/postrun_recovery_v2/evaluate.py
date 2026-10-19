"""Final-only CPU evaluation, frozen pose/metrics; overlapping rows remain descriptors."""
import os,sys,subprocess,time,hashlib,shutil
from pathlib import Path
from contract import *
FEATURES=('arm_direction','wrist_relative','body_xy','left_arm_direction','right_arm_direction')
OLD=Path('/data5/researcher/h3_runs/timing_autoresearch_20261016')
UNKNOWN='Insufficient reliable torso anchors for scale normalization'

def check_provenance(source,generated,parents,source_video_sha):
 require(generated['script_sha256']=='04c6dd432ddf102300a4cd065f4de8b9c2bc0661ce1abb06d994330b32ae693f','generated pose script')
 require(all(generated==p for p in parents),'generated pose provenance differs from frozen parent')
 if source==generated:return {'exact':True}
 exception=read(HERE/'SOURCE_POSE_PROVENANCE_EXCEPTION.json')
 require(source['script_sha256']=='b0eb01e8a0d24049cff8880dc3f356a177ada760cc919a31cfbd11ee7f82fa89' and source_video_sha==exception['source_sha256'] and exception['passed'] is True,'unregistered source pose exception')
 require({k:v for k,v in source.items() if k!='script_sha256'}=={k:v for k,v in generated.items() if k!='script_sha256'},'pose source/model/selection provenance changed')
 return {'exact_except_source_opening_mode':True,'existing_141RGB_bridge':exception}

def fixed_metrics(source,poses,windows,thresholds,metrics):
 out={}
 for name,path in poses.items():
  out[name]={}
  for c in thresholds:
   try:s,t=metrics.load_pose(source,c),metrics.load_pose(path,c)
   except ValueError as exc:
    if str(exc)!=UNKNOWN:raise
    out[name][str(c)]={'status':'unknown_visibility','reason':str(exc),'diagnostics':[]};continue
   rows=[metrics.local_diagnostic(s,t,w,24,f) for w in windows for f in FEATURES]
   out[name][str(c)]={'status':'measured','diagnostics':metrics.clean(rows)}
 return out

def region_sets(ledger,case):
 regions={f'fixed_{a}_{b}':list(range(a,b+1)) for a,b in case['windows']+case['descriptive_windows']}
 chosen=set();bins=set()
 for row in ledger['rows']:
  if row['chosen']!='full':continue
  for a,b in row['decision']['physical_intervals']:chosen.update(range(a,b+1))
  bins.update(row['decision']['latent_bins'])
 cursor=0;support=set()
 for i in range(42):
  size=(1,4,4,4,4)[i%5]
  if i in bins:support.update(range(cursor,min(cursor+size,141)))
  cursor+=size
 regions.update(actual_physical_union=sorted(chosen),actual_physical_complement=sorted(set(range(141))-chosen),actual_bin_support_union=sorted(support),actual_bin_support_complement=sorted(set(range(141))-support))
 return regions

def common_regions(source,poses,regions,threshold,metrics):
 """Same intersection/min-confidence formula as frozen compare_runs, arbitrary frozen frame subsets."""
 import numpy as np
 try:s=metrics.load_pose(source,threshold);runs={k:metrics.load_pose(p,threshold) for k,p in poses.items()}
 except ValueError as exc:
  if str(exc)!=UNKNOWN:raise
  return {'status':'unknown_visibility','reason':str(exc),'rows':[]}
 require(all(np.array_equal(x['frames'],np.arange(141)) for x in [s,*runs.values()]),'common support requires exact141 source frame grid')
 result=[];cn={'arm_direction':'arm_conf','wrist_relative':'wrist_conf','body_xy':'body_conf','left_arm_direction':'left_arm_conf','right_arm_direction':'right_arm_conf'}
 for region,frames in regions.items():
  for feature in FEATURES:
   if not frames:result.append({'region':region,'feature':feature,'status':'empty_region','source_frames':[],'runs':{}});continue
   idx=np.asarray(frames);a=s[feature][idx];valid=np.isfinite(a).all(axis=-1);weights=s[cn[feature]][idx].clip(0,1)
   for run in runs.values():valid &= np.isfinite(run[feature][idx]).all(axis=-1);weights=np.minimum(weights,run[cn[feature]][idx].clip(0,1))
   weights=np.where(valid,weights,0);denom=weights.sum();reports={}
   for name,run in runs.items():
    dist=np.linalg.norm(a-run[feature][idx],axis=-1);weighted=np.nan_to_num(dist)*weights
    reports[name]={'same_frame_error_on_common_support':weighted.sum()/denom if denom else None,'per_source_frame_error':np.divide(weighted.sum(-1),weights.sum(-1),out=np.full(len(idx),np.nan),where=weights.sum(-1)>0)}
   result.append({'region':region,'feature':feature,'status':'usable_exploratory' if valid.mean()>=.8 else 'insufficient_common_support','source_frames':frames,'common_valid_fraction':valid.mean(),'common_valid_joint_frames':int(valid.sum()),'common_weight_sum':denom,'common_valid_mask':valid.tolist(),'common_weights':weights.tolist(),'runs':reports})
 return metrics.clean({'status':'measured','confidence':threshold,'policy':'intersection of all methods and source; shared minimum confidence weights, same frozen formula as compare_runs','rows':result})

def media_and_pixels(videos,folder,frames,clip):
 import cv2,numpy as np
 cv2.setNumThreads(1);folder.mkdir();caps={};digests={k:[] for k in videos};writer=None;clip_path=folder/'fixed_clip_comparison.mp4'
 ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe');require(ffmpeg is not None and ffprobe is not None,'existing ffmpeg/ffprobe required')
 playback={}
 for name,path in videos.items():
  cmd=[ffprobe,'-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','stream=width,height,r_frame_rate,avg_frame_rate,duration,time_base:frame=best_effort_timestamp_time','-of','json',str(path)]
  probe=json.loads(subprocess.check_output(cmd,timeout=30));playback[name]=dict(check_playback_probe(probe),video_sha256=sha(path),raw_probe=probe)
 save(folder/'PLAYBACK_GATE.json',{'passed':True,'all_share_physical_24fps_grid':True,'videos':playback})
 try:
  for name,path in videos.items():
   cap=cv2.VideoCapture(str(path),cv2.CAP_FFMPEG,[cv2.CAP_PROP_N_THREADS,1]);caps[name]=cap
   require(cap.isOpened() and [int(cap.get(x)) for x in (cv2.CAP_PROP_FRAME_WIDTH,cv2.CAP_PROP_FRAME_HEIGHT,cv2.CAP_PROP_FRAME_COUNT)]==[1312,736,141] and cap.get(cv2.CAP_PROP_FPS)==24,'final video geometry/timebase')
  width=656*len(caps);height=368+32
  cmd=[ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-f','rawvideo','-pixel_format','bgr24','-video_size',f'{width}x{height}','-framerate','24','-i','pipe:0','-an','-c:v','libx264','-threads','1','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(clip_path)]
  with (folder/'ffmpeg.log').open('x') as log:
   writer=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=log,stderr=log)
   for i in range(141):
    panes=[]
    for name,cap in caps.items():
     ok,bgr=cap.read();require(ok,'video early EOF');rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB);digests[name].append(hashlib.sha256(rgb.tobytes()).hexdigest())
     pane=np.zeros((height,656,3),np.uint8);pane[:368]=cv2.resize(bgr,(656,368),interpolation=cv2.INTER_AREA);cv2.putText(pane,name,(12,390),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),1,cv2.LINE_AA);panes.append(pane)
    combined=np.hstack(panes)
    if i in frames:require(cv2.imwrite(str(folder/f'frame{i:03d}_comparison.png'),combined),'PNG export failed')
    if clip[0]<=i<=clip[1]:writer.stdin.write(combined.tobytes())
   require(all(not cap.read()[0] for cap in caps.values()),'video extra frame')
   writer.stdin.close();require(writer.wait(timeout=60)==0,'comparison clip encoding failed')
 finally:
  for cap in caps.values():cap.release()
  if writer is not None and writer.poll() is None:writer.terminate();writer.wait(timeout=10)
 result={'frames':141,'fps':24,'geometry':[1312,736],'RGB_frame_sha256':digests,'fixed_frames':frames,'clip_inclusive':clip,'media_scale':'each tile656x368, no timeline alignment/warping; black caption32px','manual_quality_review':'pending'};save(folder/'PIXELS_AND_MEDIA.json',result);return result

def evaluate(root,arc,case,protocol):
 started=time.monotonic();run=case['run_id'];dest=arc/'final';require(not dest.exists(),'partial final evaluation exists; explicit recovery required');dest.mkdir()
 for path,digest in protocol['frozen_external'].items():require(sha(path)==digest,'frozen external changed '+path)
 sys.path.insert(0,str(root/'scripts'));import timing_metrics as metrics
 from scan_current_pose import observe,valid_pose
 source=arc/'configs/source.pose.json';require(sha(source)==protocol['source_pose_sha256'],'source pose changed');valid_pose(source)
 h=read(arc/'logs'/f'{run}_history.json');video=output_file(arc,h,run);source_video=arc/'input'/read(arc/'configs'/f'{run}.json')['22']['inputs']['file'];require(sha(source_video)==read(source)['video']['sha256'],'actual source video/pose binding')
 poses={};videos={'SOURCE':source_video};parents=[]
 for name in case['comparators']:
  p=protocol['parents'][name];path=HERE/p['pose'];require(sha(path)==p['pose_sha256'] and sha(p['video'])==p['video_sha256'] and read(path)['video']['sha256']==p['video_sha256'],'parent pose/video binding');valid_pose(path);poses[name]=path;videos[name]=Path(p['video']);parents.append(read(path)['provenance'])
 cmd=[sys.executable,str(OLD/'scripts/pose_probe.py'),'--video',str(video),'--output-dir',str(dest/'pose'),'--threads','4','--stride','1']
 for frame in protocol['fixed_visual_frames']:cmd+=['--overlay-frame',str(frame)]
 with (dest/'pose.log').open('x') as log:proc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4'),timeout=240)
 require(proc.returncode==0,'pose execution failed; technical error, not UNKNOWN');pose=dest/'pose'/(video.stem+'.pose.json');raw=valid_pose(pose);require(raw['video']['sha256']==sha(video),'generated pose input mismatch');provenance=check_provenance(read(source)['provenance'],raw['provenance'],parents,sha(source_video));poses['auto']=pose;videos['AUTO']=video
 fixed=fixed_metrics(source,poses,case['windows'],protocol['thresholds'],metrics);save(dest/'FIXED_WINDOWS.json',{'window_scope':case['window_scope'],'windows':case['windows'],'results':fixed})
 scans={}
 for name,path in poses.items():
  scan=observe(source,path,19);save(dest/(name+'_WHOLE_SCAN.json'),scan);scans[name]=observer_summary(scan)
 save(dest/'WHOLE_SCAN_SUMMARY.json',{'endpoint':'final sampler output, independent of online selected windows; legacy physical_index19 is only schema adapter','results':scans})
 ledger=read(arc/'DECISION_LEDGER.json');regions=region_sets(ledger,case);save(dest/'REGIONS.json',regions);subsets=[list(poses)]
 if len(poses)>2:subsets.append([case['comparators'][0],'auto'])
 common={}
 for names in subsets:
  label='__'.join(names);common[label]={}
  for c in protocol['thresholds']:
   record=common_regions(source,{n:poses[n] for n in names},regions,c,metrics);save(dest/f'COMMON_{label}_{c}.json',record);common[label][str(c)]={'status':record['status'],'rows':len(record['rows'])}
 pixels=media_and_pixels(videos,dest/'media',protocol['fixed_visual_frames'],protocol['fixed_clip_inclusive'])
 off=not ledger['active_indices'];rgb_equal=pixels['RGB_frame_sha256']['AUTO']==pixels['RGB_frame_sha256'][case['comparators'][0]]
 if off:require(rgb_equal,'all-OFF141RGB differs from Native despite required equality')
 audit=read(arc/'audit/counterfactual'/f'{run}.json')['counterfactual'];job=read(arc/'logs'/f'{run}_job.json');capture=read(arc/'audit/x0'/run/'manifest.json')
 efficiency={'job_wall_seconds':job['observed_unix']-job['submitted_unix'],'actual_NFE':ledger['NFE'],'actual_Euler_updates':20,'current_Native_observations':20,'Full_branches':len(ledger['active_indices']),'observer_wall_seconds':sum(x['wall_seconds'] for x in audit['measurements']),'branch_model_seconds_synchronized':sum(x['model_seconds_synchronized'] for x in audit['branches']),'branch_condition_copy_hash_seconds':sum(x['condition_copy_hash_seconds'] for x in audit['branches']),'chosen20_capture_seconds':sum(x['capture_seconds'] for x in capture['captures']),'interpretation':'recorded scopes can overlap; not an efficiency optimization study or a sum-total decomposition'}
 save(dest/'EFFICIENCY.json',efficiency)
 summary={'video':str(video),'video_sha256':sha(video),'pose':str(pose),'pose_sha256':sha(pose),'source_pose_sha256':sha(source),'pose_provenance':provenance,'fixed_windows_scope':case['window_scope'],'whole_scan':scans,'common_support':common,'NFE':ledger['NFE'],'active_indices':ledger['active_indices'],'ON_episodes':ledger['ON_episodes_inclusive'],'restart_count':ledger['restart_count'],'normal_any_intervention':case['seed']==2026101313 and not off,'all_OFF_141RGB_equal':rgb_equal if off else None,'all_OFF_final_AV':'independently checked by verify_single' if off else 'N/A after first intervention','CPU_seconds':time.monotonic()-started,'efficiency':efficiency,'manual_quality_review':'pending fixed frames/fullvideo inspection; pose alone not identity/shape success','scope':'development cases, no generalization or architecture novelty claim'}
 save(dest/'FINAL_SUMMARY.json',summary);return summary
