import json,hashlib,math
from pathlib import Path
R=Path(__file__).resolve().parent
P=json.loads((R/'requested_windows.json').read_text())
output={'source_only':True,'windows_sha256':hashlib.sha256((R/'requested_windows.json').read_bytes()).hexdigest(),'sources':{},'interpretation':'Pose confidence is raw, uncalibrated. Source support does not guarantee accurate identity/tracking or generated-pose observability. No timing lag measured.'}
lines=['R24 source-only visibility before generation','Frozen same CPU DWPose, same feature definitions; no output-driven selection.','Main/secondary windows fixed by root from source images before results.','']
for name in ('fresh_a','fresh_b'):
 p=R/name/'RESULTS.json'
 if not p.exists():continue
 d=json.loads(p.read_text());raw=json.loads((R/name/(name+'.pose.json')).read_text());frames=raw['frames'];s={'source_sha256':d['video']['sha256'],'result_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'statistics':d['statistics'],'thresholds':{},'selected_track':[]}
 for f in frames:
  i=f['selected_person'];s['selected_track'].append({'frame':f['frame'],'person_count':len(f['persons']),'selected_person':i,'ambiguous':f['selection_ambiguous'],'selected_bbox':None if i is None else f['persons'][i]['box_xyxy'],'all_bbox':[v['box_xyxy'] for v in f['persons']]})
 lines += [name+': '+s['source_sha256'], 'statistics '+json.dumps(s['statistics'])]
 for th in (.3,.5):
  td=d['thresholds'][str(th)]
  if td['status']!='computed':s['thresholds'][str(th)]=td;lines.append(str(th)+' UNKNOWN');continue
  q={'whole_anchor_coverage':td['anchors']['coverage'],'whole_anchor_joint_coverages':td['anchors']['joint_coverages'],'observable_intervals':{fn:ft['with_anchor_intervals'] for fn,ft in td['features'].items()},'crossings':td['crossings'],'windows':[]}
  lines.append(f'confidence{th}: whole shoulder+hip anchors {td["anchors"]["count"]}/141={td["anchors"]["coverage"]:.6f}; per-joint '+json.dumps(td['anchors']['joint_coverages']))
  for label,w in [('primary',P[name]['primary'])]+[(f'secondary{i+1}',w) for i,w in enumerate(P[name]['secondary'])]:
   start,end=w;n=end-start+1;anchor=[];joint={str(j):[] for j in (5,6,11,12)};amb=0
   for f in frames[start:end+1]:
    i=f['selected_person'];a=[]
    for j in (5,6,11,12):
     ok=False if i is None else f['persons'][i]['coco17_score'][j]>=th and all(math.isfinite(v) for v in f['persons'][i]['coco17_xy'][j]);a.append(ok);joint[str(j)].append(ok)
    anchor.append(all(a));amb+=int(f['selection_ambiguous'])
   z={'label':label,'window_inclusive':w,'anchor_coverage':sum(anchor)/n,'anchor_joint_coverages':{j:sum(vals)/n for j,vals in joint.items()},'ambiguous_frames':amb,'features':{}}
   for fn,ft in td['features'].items():
    vals=ft['per_frame_valid_slots'][start:end+1];slots=ft['slots_per_frame'];cov=sum(vals)/(n*slots);vf=sum(v>0 for v in vals)
    z['features'][fn]={'coverage':cov,'valid_frames':vf,'fully_observable_frames':sum(v==slots for v in vals),'source_support_pass':cov>=.8 and vf>=8}
   z['all_four_source_support_pass']=all(x['source_support_pass'] for x in z['features'].values());q['windows'].append(z)
   lines.append(f'  {label}{w}: anchors{z["anchor_coverage"]:.6f}; '+', '.join(f'{k}={v["coverage"]:.6f}({"pass" if v["source_support_pass"] else "UNKNOWN"})' for k,v in z['features'].items()))
  s['thresholds'][str(th)]=q
 output['sources'][name]=s;lines.append('')
(R/'VISIBILITY_SUMMARY.json').write_text(json.dumps(output,indent=2)+'\n');(R/'SUMMARY.txt').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
