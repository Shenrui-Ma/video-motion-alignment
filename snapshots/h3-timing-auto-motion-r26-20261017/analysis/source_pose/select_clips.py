"""Frozen source-only geometric turn-density selection; no generated input."""
import json,hashlib,math
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;R=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def extract(raw):
 n=len(raw['frames']);xy=np.full((n,17,2),np.nan);cf=np.zeros((n,17));amb=np.zeros(n,dtype=bool)
 for i,r in enumerate(raw['frames']):
  if r['frame']!=i:raise ValueError('non-contiguous full source')
  amb[i]=r['selection_ambiguous'];sel=r['selected_person']
  if sel is not None:xy[i]=r['persons'][sel]['coco17_xy'];cf[i]=r['persons'][sel]['coco17_score']
 return xy,cf,amb

def masks(xy,cf,amb,th):
 v=np.isfinite(xy).all(-1)&(cf>=th)&(xy[:,:,0]>=0)&(xy[:,:,0]<1312)&(xy[:,:,1]>=0)&(xy[:,:,1]<736)&~amb[:,None]
 a=v[:,[5,6,11,12]].all(1)
 chains=[v[:,j].all(1)&a for j in ([5,7,9],[6,8,10],[11,13,15],[12,14,16])]
 return v,a,chains

def signals(xy,cf,amb,protocol):
 v,a,chains=masks(xy,cf,amb,protocol['confidence_primary']);bones=[];valid=[]
 for i,j in protocol['bone_pairs']:bones.append(xy[:,j]-xy[:,i]);valid.append(v[:,i]&v[:,j]&a)
 bones.append((xy[:,5]+xy[:,6]-xy[:,11]-xy[:,12])/2);valid.append(a)
 x=np.stack(bones,1);ok=np.stack(valid,1);norm=np.linalg.norm(x,axis=-1);ok &= np.isfinite(norm)&(norm>=protocol['bone_min_length_pixels'])
 unit=np.full_like(x,np.nan);unit[ok]=x[ok]/norm[ok,None]
 smooth=np.full_like(unit,np.nan)
 for t in range(1,len(unit)-1):
  keep=ok[t-1:t+2].all(0);mean=np.nan_to_num(unit[t-1:t+2]).mean(0);length=np.linalg.norm(mean,axis=-1);keep &= length>1e-12;smooth[t,keep]=mean[keep]/length[keep,None]
 radius=protocol['turn']['radius_frames'];weights=np.array(protocol['turn']['bone_weights']);minimum=np.deg2rad(protocol['turn']['minimum_signed_angle_each_side_degrees']);events=[]
 def angle(u,w):return np.arctan2(u[:,0]*w[:,1]-u[:,1]*w[:,0],(u*w).sum(-1))
 for t in range(radius+1,len(unit)-radius-1):
  l=angle(smooth[t-radius],smooth[t]);rr=angle(smooth[t],smooth[t+radius]);keep=np.isfinite(l)&np.isfinite(rr)&(l*rr<0)&(np.abs(l)>=minimum)&(np.abs(rr)>=minimum)
  strength=float((weights*np.where(keep,np.minimum(np.minimum(np.abs(l),np.abs(rr)),np.pi/2),0)).sum())
  if strength>0:events.append({'frame':t,'strength':strength,'reversing_bone_indices':np.flatnonzero(keep).tolist(),'left_degrees':np.rad2deg(l).tolist(),'right_degrees':np.rad2deg(rr).tolist()})
 return events

def nms(events,start,end,separation,margin):
 eligible=[v for v in events if start+margin<=v['frame']<=end-margin];selected=[]
 for v in sorted(eligible,key=lambda x:(-x['strength'],x['frame'])):
  if all(abs(v['frame']-x['frame'])>=separation for x in selected):selected.append(v)
 return sorted(selected,key=lambda x:x['frame'])

def analyze(raw,protocol):
 xy,cf,amb=extract(raw);n=len(xy);length=protocol['clip_length_frames'];events=signals(xy,cf,amb,protocol);thresholds={th:masks(xy,cf,amb,th) for th in [.3,.5]};rows=[]
 for start in range(0,n-length+1,protocol['candidate_start_stride']):
  end=start+length-1;coverage={}
  for th,(_,a,c) in thresholds.items():coverage[str(th)]={'anchor':float(a[start:end+1].mean()),'left_arm':float(c[0][start:end+1].mean()),'right_arm':float(c[1][start:end+1].mean()),'left_leg':float(c[2][start:end+1].mean()),'right_leg':float(c[3][start:end+1].mean())}
  c=coverage['0.3'];ambiguity=float(amb[start:end+1].mean());reasons=[]
  if c['anchor']<.8:reasons.append('anchor_coverage_below_0.8')
  for side in ['left','right']:
   if c[side+'_arm']<.8:reasons.append(side+'_arm_coverage_below_0.8')
  if ambiguity>.05:reasons.append('ambiguity_above_0.05')
  arms=not reasons;legs=c['left_leg']>=.6 and c['right_leg']>=.6;tier=2 if arms and legs else 1 if arms else 0
  if not legs:reasons.append('leg_support_below_fullbody_tier')
  chosen=nms(events,start,end,protocol['turn']['event_nonmax_separation_frames'],protocol['turn']['candidate_edge_margin_frames']);mean=float(np.mean(list(c.values())));strength=sum(x['strength'] for x in chosen)
  rank=[tier,len(chosen),mean,strength,-start] if tier else [tier,mean,len(chosen),strength,-start]
  rows.append({'start_frame':start,'end_frame':end,'visibility_tier':tier,'status':'eligible_fullbody' if tier==2 else 'eligible_arms_only' if tier==1 else 'UNKNOWN_support','coverage':coverage,'ambiguous_fraction':ambiguity,'rejection_or_limit_reasons':reasons,'reversal_event_count':len(chosen),'reversal_strength_sum':strength,'reversal_event_frames':[v['frame'] for v in chosen],'rank':rank})
 if not rows:raise ValueError('source shorter than141')
 best=max(rows,key=lambda x:tuple(x['rank']))
 return {'all_candidate_windows':rows,'all_reversal_candidates':events,'selected':best,'frame_count':n,'pose_statistics':raw['statistics'],'selection_only_uses_source':True,'no_generated_result_access':True,'limitations':['Event count is a geometric reversal proxy, not semantic action labels.','Raw confidence and track continuity do not prove correct anatomy.','No threshold/segment tuning after this full source pose.']}

def finite_json(x):
 if isinstance(x,float) and not math.isfinite(x):return None
 if isinstance(x,list):return [finite_json(y) for y in x]
 if isinstance(x,dict):return {k:finite_json(v) for k,v in x.items()}
 return x

def main():
 protocol=read(R/'configs/source_selection_protocol.json');freeze=read(R/'configs/source_selection_freeze.json')
 for rel,d in freeze['files'].items():
  if sha(R/rel)!=d:raise ValueError('frozen selection changed '+rel)
 for cid in protocol['sources']:
  p=P/'full_pose'/cid/f'{cid}_full24.pose.json';raw=read(p);manifest=read(R/'assets/prepared'/f'{cid}_full24_provenance.json')
  if raw['video']['sha256']!=manifest['full_prepared_sha256'] or raw['video']['fps']!=24:raise ValueError('pose source binding')
  result=analyze(raw,protocol);result.update(source_id=cid,pose_sha256=sha(p),source_full_provenance_sha256=sha(R/'assets/prepared'/f'{cid}_full24_provenance.json'),protocol_sha256=sha(R/'configs/source_selection_protocol.json'),script_sha256=sha(Path(__file__)))
  dst=P/f'{cid}_SELECTION.json'
  with dst.open('x') as f:json.dump(finite_json(result),f,indent=2,allow_nan=False);f.write('\n')
  print(json.dumps({'source':cid,'selected':result['selected']}),flush=True)
if __name__=='__main__':main()
