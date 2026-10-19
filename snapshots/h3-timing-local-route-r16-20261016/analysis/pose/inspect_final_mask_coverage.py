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
  paths={'source':ROOT/'configs/source_pose.json','native':R3/'r3_s05_native_00001_.pose.json','full':R3/'r3_s05_full_6to14_00001_.pose.json','roi':ROOT/'analysis/pose/pilot/r16_s05_roi_6to14_00001_.pose.json'}
  u=ROOT/'analysis/pose/pilot/r16_s05_uniform_6to14_00001_.pose.json'
  if u.exists():paths['uniform']=u
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
  out={'status':'complete','post_outcome_diagnostic':True,'primary_metrics_changed':False,'source_mask_changed':False,'method':'For each final-pose forearm at physical frames50..65, 21 equal-length points are mapped to the exact32px query patch containing xy+0.5; average actual frozen ROI coefficients. Missing/ambiguous/low-confidence poses excluded and denominators reported. No phase alignment.','limitations':['Final decoded pose is not the denoising state or query feature support at indices6..14.','A spatial patch center and its contextual hidden features are not a body-part label.','Generated appearance/body proportions and pose errors can affect this proxy.','This post-outcome diagnostic cannot establish why ROI failed or justify changing the frozen mask.'],'source_mask_sha256':sha(maskp),'pose_inventory':{k:{'path':str(v),'sha256':sha(v)} for k,v in paths.items()},'summaries':summaries,'records':records}
  dest=ROOT/'analysis/pose/final_geometry_mask_coverage.json';dest.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(summaries,indent=2))
if __name__=='__main__':main()
