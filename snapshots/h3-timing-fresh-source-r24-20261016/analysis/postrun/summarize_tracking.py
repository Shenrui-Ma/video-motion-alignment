"""Descriptive selector audit only; no selection override or new timing gate."""
import hashlib,json,math
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
rows={}
for arc in sorted((HERE/'captured').glob('*')):
 if not (arc/'CPU_COMPLETE.json').exists():continue
 done=json.loads((arc/'CPU_COMPLETE.json').read_text());p=arc/'pose'/Path(done['pose']).name;d=json.loads(p.read_text());centers=[];indices=[]
 for f in d['frames']:
  selected=f['selected_person']
  if selected is None:continue
  b=f['persons'][selected]['box_xyxy'];centers.append((f['frame'],(b[0]+b[2])/2,(b[1]+b[3])/2));indices.append(selected)
 jumps=[{'from':a[0],'to':b[0],'pixels':math.hypot(a[1]-b[1],a[2]-b[2])} for a,b in zip(centers,centers[1:])]
 rows[arc.name]={'pose_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'statistics':d['statistics'],'selected_index_counts':dict(Counter(indices)),'center_x_range':[min(x[1] for x in centers),max(x[1] for x in centers)] if centers else None,'center_y_range':[min(x[2] for x in centers),max(x[2] for x in centers)] if centers else None,'largest_five_center_displacements':sorted(jumps,key=lambda x:-x['pixels'])[:5],'note':'Detector index changes do not by themselves indicate identity switches. Bounds and sampled overlays require visual review; no selector/metric change.'}
(HERE/'TRACKING_SUMMARY.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
