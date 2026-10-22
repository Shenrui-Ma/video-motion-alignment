"""Read-only exact official MF attribution for the existing oxygen0252 caches."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import csv,hashlib,importlib.util,json,sys
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
ROOT=Path(__file__).resolve().parents[1]
PARENT=Path('/Users/researcher/DevProjects/h3-ivebench-expanded-metrics-r73-20261018')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
spec=importlib.util.spec_from_file_location('existing_official_calibration',PARENT/'audit/official_mf_time_calibration.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
official=module.official_evaluator()
def parts(x,y,v,w):
 pos=np.linalg.norm(x-y,axis=1)
 vel=np.linalg.norm(np.diff(x,axis=0)-np.diff(y,axis=0),axis=1);vel=np.r_[vel[0],vel]
 norm=float(np.mean([np.linalg.norm(np.ptp(x,axis=0)),np.linalg.norm(np.ptp(y,axis=0))]));norm=1. if norm<1e-6 else norm
 weights=np.minimum(v,w);den=weights.sum()
 p=float(np.sum((1/(1+pos/norm))*weights)/den) if den else 0.
 d=float(np.sum((1/(1+vel/norm))*weights)/den) if den else 0.
 return {'position_similarity':p,'displacement_similarity':d,'position_weighted':.7*p,'displacement_weighted':.3*d,'score':.7*p+.3*d,'normalization_pixels':norm,'mean_position_pixels':float(pos.mean()),'mean_displacement_pixels':float(vel.mean()),'visibility_weight_sum':float(den),'visibility_weight_min':float(weights.min()),'visibility_weight_max':float(weights.max())}
def accepted_ids(v):return [i for i in range(v.shape[1]) if float(v[:,i].mean())>.3 and int((v[:,i]>.5).sum())>=5]
def time_map(v):
 ids=np.flatnonzero(v>.5)
 return np.interp(np.linspace(0,len(ids)-1,len(v)),np.arange(len(ids)),ids) if len(ids)>=2 else np.full(len(v),np.nan)
def analyze(role,caches):
 st,sv=caches['source'];tt,tv=caches[role]
 xs,vs,xt,vt=official.synchronize_videos(st,sv,tt,tv);sids,tids=accepted_ids(vs),accepted_ids(vt)
 matrix=np.array([[official.compute_frame_by_frame_similarity(xs[:,i],xt[:,j],vs[:,i],vt[:,j]) for j in tids] for i in sids])
 rows,cols=linear_sum_assignment(-matrix);matches=[]
 for row,col in zip(rows,cols):
  i,j=sids[row],tids[col];detail=parts(xs[:,i],xt[:,j],vs[:,i],vt[:,j]);score=float(matrix[row,col]);assert abs(score-detail['score'])<1e-12
  detail.update(source_id=i,target_id=j,accepted=score>.3,source_xy0=st[0,i].tolist(),target_xy0=tt[0,j].tolist(),source_visible_frames=int((sv[:,i]>.5).sum()),target_visible_frames=int((tv[:,j]>.5).sum()),source_span_pixels=float(np.linalg.norm(np.ptp(st[:,i],axis=0))),source_raw_visibility_fully_visible=bool((sv[:,i]>.5).all()),effective_source_vs_target_mean_abs_time_difference_frames=float(np.mean(np.abs(time_map(sv[:,i])-time_map(tv[:,j])))))
  matches.append(detail)
 chosen=[m for m in matches if m['accepted']]
 actual=float(official._compute_similarity_from_tracks(*(module.ArrayTensor(v[None]) for v in [st,sv,tt,tv])))
 stored=read(PARENT/'results/short_0252'/f'{role}_source1_target1.json')['motion_fidelity']
 assert abs(actual-stored)<1e-12 and abs(actual-np.mean([m['score'] for m in chosen]))<1e-12
 result={'role':role,'official_score':actual,'stored_score':stored,'position_contribution':float(np.mean([m['position_weighted'] for m in chosen])),'displacement_contribution':float(np.mean([m['displacement_weighted'] for m in chosen])),'source_eligible_ids':sids,'target_eligible_ids':tids,'hungarian_pairs':len(matches),'accepted_pairs':len(chosen),'rejected_pairs':len(matches)-len(chosen),'source_synced_visibility_unique':np.unique(vs).tolist(),'target_synced_visibility_unique':np.unique(vt).tolist(),'matches':matches}
 assert abs(result['position_contribution']+result['displacement_contribution']-actual)<1e-12
 save(ROOT/'results'/f'{role}_attribution.json',result)
 np.savez(ROOT/'results'/f'{role}_similarity_matrix.npz',similarity=matrix,source_ids=sids,target_ids=tids)
 return result,(xs,vs,xt,vt),matrix
def main():
 caches={};inputs={}
 for role in ['source','native','forced']:
  p=PARENT/'tracks'/role/'short_0252/attempt1/tracks.npz';report=read(p.with_name('REPORT.json'));assert sha(p)==report['tracks_sha256'] and report['passed'] is True
  with np.load(p,allow_pickle=False) as z: caches[role]=z['tracks'][0].copy(),z['visibility'][0].copy()
  assert caches[role][0].shape==(98,100,2) and caches[role][1].shape==(98,100)
  inputs[role]={'path':str(p),'sha256':sha(p),'report_path':str(p.with_name('REPORT.json')),'report_sha256':sha(p.with_name('REPORT.json')),'fully_visible':int((caches[role][1]>.5).all(0).sum()),'partially_visible':int(((caches[role][1]>.5).any(0)&~(caches[role][1]>.5).all(0)).sum()),'zero_visible':int((~(caches[role][1]>.5).any(0)).sum())}
 a,syna,ma=analyze('native',caches);b,synb,mb=analyze('forced',caches)
 am={m['source_id']:m for m in a['matches'] if m['accepted']};bm={m['source_id']:m for m in b['matches'] if m['accepted']}
 points=[]
 for i in sorted(set(am)|set(bm)):
  n,f=am.get(i),bm.get(i);row={'source_id':i,'source_x0':float(caches['source'][0][0,i,0]),'source_y0':float(caches['source'][0][0,i,1]),'source_visible_frames':int((caches['source'][1][:,i]>.5).sum()),'native_target_id':n['target_id'] if n else None,'guided_target_id':f['target_id'] if f else None,'native_accepted':n is not None,'guided_accepted':f is not None}
  for field in ['score','position_weighted','displacement_weighted']:
   nv=n[field]/len(am) if n else 0.;fv=f[field]/len(bm) if f else 0.
   row[field+'_native_contribution']=nv;row[field+'_guided_contribution']=fv;row[field+'_delta']=fv-nv
  points.append(row)
 delta=b['official_score']-a['official_score'];assert abs(sum(p['score_delta'] for p in points)-delta)<1e-12
 matching={'definition':'Diagnostic only: keep Native accepted source-target identities; evaluate these same pairs on guided synchronized trajectories. No retracking, altered official score, or refit.', 'applicable':set(am)==set(bm) and all(m['target_id'] in b['target_eligible_ids'] for m in am.values())}
 if matching['applicable']:
  x,v,y,w=synb;fixed=[]
  for m in am.values():fixed.append(parts(x[:,m['source_id']],y[:,m['target_id']],v[:,m['source_id']],w[:,m['target_id']]))
  fixedscore=float(np.mean([m['score'] for m in fixed]));matching.update(guided_on_native_accepted_pairs=fixedscore,trajectory_visibility_normalization_change_at_native_pairs=fixedscore-a['official_score'],assignment_selection_change_at_guided_data=b['official_score']-fixedscore,native_selected_pairs_that_would_now_fail_threshold=sum(m['score']<=.3 for m in fixed),changed_target_matches=sum(am[i]['target_id']!=bm[i]['target_id'] for i in am))
  assert abs(matching['trajectory_visibility_normalization_change_at_native_pairs']+matching['assignment_selection_change_at_guided_data']-delta)<1e-12
 normalization={'applicable':matching.get('changed_target_matches')==0 and set(am)==set(bm),'definition':'Exact two-factor symmetric arithmetic allocation on the actual unchanged accepted matching: post-interpolation distance arrays versus mean track-span normalizer. Cross combinations are bookkeeping, not generated outputs or a causal experiment.'}
 if normalization['applicable']:
  norm_rows=[];xa,va,ya,wa=syna;xb,vb,yb,wb=synb
  for i,n in am.items():
   f=bm[i];j=n['target_id'];assert j==f['target_id'] and np.all(va[:,i]==1) and np.all(wa[:,j]==1) and np.all(wb[:,j]==1)
   assert np.array_equal(xa[:,i],xb[:,i])
   sn,sf=n['normalization_pixels'],f['normalization_pixels'];row={'source_id':i,'native_normalization_pixels':sn,'guided_normalization_pixels':sf}
   for component,weight in [('position',.7),('displacement',.3)]:
    if component=='position':dn=np.linalg.norm(xa[:,i]-ya[:,j],axis=1);df=np.linalg.norm(xb[:,i]-yb[:,j],axis=1)
    else:
     dn=np.linalg.norm(np.diff(xa[:,i],axis=0)-np.diff(ya[:,j],axis=0),axis=1);dn=np.r_[dn[0],dn]
     df=np.linalg.norm(np.diff(xb[:,i],axis=0)-np.diff(yb[:,j],axis=0),axis=1);df=np.r_[df[0],df]
    nn=float(np.mean(1/(1+dn/sn)));fn=float(np.mean(1/(1+df/sn)));nf=float(np.mean(1/(1+dn/sf)));ff=float(np.mean(1/(1+df/sf)))
    distance=weight*.5*((fn-nn)+(ff-nf))/len(am);scale=weight*.5*((nf-nn)+(ff-fn))/len(am)
    row.update({component+'_distance_array_contribution':distance,component+'_normalizer_contribution':scale,component+'_native_mean_distance_pixels':float(dn.mean()),component+'_guided_mean_distance_pixels':float(df.mean())})
    assert abs(distance+scale-(f[component+'_weighted']-n[component+'_weighted'])/len(am))<1e-12
   norm_rows.append(row)
  normalization['rows']=norm_rows
  normalization['aggregate']={k:float(sum(row[k] for row in norm_rows)) for k in ['position_distance_array_contribution','position_normalizer_contribution','displacement_distance_array_contribution','displacement_normalizer_contribution']}
  normalization['mean_normalization_pixels']={role:float(np.mean([row[role+'_normalization_pixels'] for row in norm_rows])) for role in ['native','guided']}
  save(ROOT/'results/NORMALIZATION_DECOMPOSITION.json',normalization)
 groups={}
 for name,predicate in [('source_always_visible',lambda x:x['source_visible_frames']==98),('source_intermittently_visible',lambda x:0<x['source_visible_frames']<98)]:
  subset=[p for p in points if predicate(p)];groups[name]={'count':len(subset),'sum_delta':sum(p['score_delta'] for p in subset),'position_delta':sum(p['position_weighted_delta'] for p in subset),'displacement_delta':sum(p['displacement_weighted_delta'] for p in subset)}
 # Fixed spatial strata derived only from source frame0 coordinates, not semantic masks.
 spatial=[]
 for yi in range(3):
  for xi in range(3):
   subset=[p for p in points if min(2,int(p['source_x0']/1280*3))==xi and min(2,int(p['source_y0']/720*3))==yi]
   spatial.append({'grid_x':xi,'grid_y':yi,'count':len(subset),'sum_delta':sum(p['score_delta'] for p in subset)})
 summary={'official_source':str(module.SOURCE),'official_source_sha256':sha(module.SOURCE),'official_method_extraction':'Reuse previous exact AST four-method loader; no synthetic calibration rerun','inputs':inputs,'native':{k:v for k,v in a.items() if k!='matches'},'guided':{k:v for k,v in b.items() if k!='matches'},'delta':delta,'position_delta':b['position_contribution']-a['position_contribution'],'displacement_delta':b['displacement_contribution']-a['displacement_contribution'],'matching_counterfactual':matching,'normalization_decomposition':{k:v for k,v in normalization.items() if k!='rows'},'source_visibility_strata':groups,'source_xy0_spatial_strata':spatial,'positive_point_contribution_sum':sum(max(0,p['score_delta']) for p in points),'negative_point_contribution_sum':sum(min(0,p['score_delta']) for p in points),'positive_points':sum(p['score_delta']>0 for p in points),'negative_points':sum(p['score_delta']<0 for p in points),'scope':'Exact accounting of this metric on these cached tracks. It does not establish which anatomical/object points are correct, why the model generated them, or which temporal operation caused the changes.'}
 save(ROOT/'results/SUMMARY.json',summary);save(ROOT/'results/SOURCE_POINT_DELTAS.json',points)
 with (ROOT/'results/SOURCE_POINT_DELTAS.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(points[0]));w.writeheader();w.writerows(points)
 print(json.dumps({k:summary[k] for k in ['delta','position_delta','displacement_delta','matching_counterfactual','source_visibility_strata','positive_point_contribution_sum','negative_point_contribution_sum']},indent=2))
if __name__=='__main__':main()
