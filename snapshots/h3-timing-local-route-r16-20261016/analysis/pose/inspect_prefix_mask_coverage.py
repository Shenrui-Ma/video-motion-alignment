"""Post-outcome geometry proxy only; never a measurement of intermediate query features."""
import fcntl,hashlib,json,math
from pathlib import Path
ROOT=Path('/Users/researcher/DevProjects/h3-timing-local-route-r16-20261016')
R3=Path('/Users/researcher/DevProjects/h3-timing-spatial-r3-20261016/analysis/pose/pilot')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 with Path('/Users/researcher/DevProjects/h3-timing-architecture-r2-20261016/analysis/pose/cpu_evaluation_global.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  maskp=ROOT/'configs/source_query_mask.json';m=json.loads(maskp.read_text())
  assert sha(maskp)=='16c5e884ea835cae33f75c2bc66061bae3aa5f4fc99042120aac21405400e81c'
  old=Path('/Users/researcher/DevProjects/h3-timing-autoresearch-20261016')
  decoded=old/'outputs/x0_decoded/s05_full_seed1_native_x0/x0_step005.json';d=json.loads(decoded.read_text())
  manifest=ROOT/'analysis/pose/pilot/r16_s05_roi_6to14_provenance/capture_manifest.json';current=json.loads(manifest.read_text())['captures'][0]
  assert d['status']=='complete' and current['step_zero_based']==5
  keys=('video','audio','geometry','sigma_video','sigma_audio','normalization_stage','audio_scale','video_latent_scale_factor','seed')
  assert all(d['snapshot_metadata'][k]==current[k] for k in keys)
  video=old/'outputs/x0_decoded/s05_full_seed1_native_x0/x0_step005.mp4'
  pose=old/'analysis/pose/x0/s05_full_seed1_native_x0/x0_step005.pose.json'
  assert d['output_sha256']==sha(video)==json.loads(pose.read_text())['video']['sha256']
  binding={'prior_decode_record':str(decoded),'decode_record_sha256':sha(decoded),'current_capture_manifest_sha256':sha(manifest),'same_tensor_signatures_and_normalization':list(keys),'snapshot_video':current['video'],'snapshot_audio':current['audio'],'decoded_video_sha256':sha(video),'VAE_SHA':d['vae_sha256'],'new_model_or_vae_runs':0,'semantics':'exact reused clean x0 estimate before first intervention, not actual noisy input state'}
  paths={'source':ROOT/'configs/source_pose.json','preintervention_x0_index5':pose}
  def alpha(frame,xy):
   indices=[i for i,tr in enumerate(m['source_traces']) if tr['span'][0]<=frame<=tr['span'][1]]
   assert len(indices)==1
   c=math.floor((xy[0]+.5)/32);r=math.floor((xy[1]+.5)/32)
   return m['roi'][indices[0]][r][c] if 0<=r<23 and 0<=c<41 else 0.
  records=[];summaries={}
  for name,p in paths.items():
   d=json.loads(p.read_text());assert d['video']['width']==1312 and d['video']['height']==736
   for conf in (.3,.5):
    for side,(a,b) in [('left',(7,9)),('right',(8,10))]:
     rows=[]
     for frame in range(50,66):
      f=d['frames'][frame];sel=f['selected_person']
      reason='missing_person' if sel is None else 'ambiguous_person' if f.get('selection_ambiguous') else None
      person=f['persons'][sel] if sel is not None else None
      if person and min(person['coco17_score'][a],person['coco17_score'][b])<conf:reason='joint_confidence'
      row={'run':name,'confidence':conf,'side':side,'frame':frame,'unknown_reason':reason}
      if not reason:
       x,y=person['coco17_xy'][a],person['coco17_xy'][b]
       values=[alpha(frame,[x[k]+i/20*(y[k]-x[k]) for k in (0,1)]) for i in range(21)]
       row.update(mean_forearm_alpha=sum(values)/len(values),fraction_forearm_alpha_positive=sum(v>0 for v in values)/len(values),wrist_alpha=values[-1],elbow_alpha=values[0])
      rows.append(row)
     valid=[r for r in rows if r['unknown_reason'] is None];key=f'{name}/{conf}/{side}'
     summaries[key]={'valid_frames':len(valid),'total_frames':16,'missing_frames':[r['frame'] for r in rows if r['unknown_reason']],**{k:sum(r[k] for r in valid)/len(valid) if valid else None for k in ('mean_forearm_alpha','fraction_forearm_alpha_positive','wrist_alpha','elbow_alpha')}}
     records+=rows
  out={'status':'complete','post_outcome_diagnostic':True,'primary_metrics_changed':False,'source_mask_changed':False,'method':'For each reused preintervention x0-pose forearm at physical frames50..65, 21 equal-length points are mapped to the exact32px query patch containing xy+0.5; average actual frozen ROI coefficients. Missing/ambiguous/low-confidence poses excluded and denominators reported. No phase alignment.','limitations':['Decoded index5 x0 is a preintervention clean endpoint estimate, not the actual noisy x6 input or hidden query feature support at indices6..14.','A spatial patch center and its contextual hidden features are not a body-part label.','Generated appearance/body proportions and pose errors can affect this proxy.','This post-outcome diagnostic cannot establish why ROI failed or justify changing the frozen mask.'],'source_mask_sha256':sha(maskp),'exact_reuse_binding':binding,'pose_inventory':{k:{'path':str(v),'sha256':sha(v)} for k,v in paths.items()},'summaries':summaries,'records':records}
  dest=ROOT/'analysis/pose/prefix005_geometry_mask_coverage.json';dest.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(summaries,indent=2))
if __name__=='__main__':main()
