"""Independent reference-only re-evaluation; no frozen implementation imports."""
from pathlib import Path
import json,hashlib,sys,time
import numpy as np
R=Path(sys.argv[1]); inputs=json.loads(Path(sys.argv[2]).read_text());summary=json.loads((R/'summary.json').read_text());status=json.loads((R/'STATUS.json').read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert status['status']=='complete' and status['results_written'];assert sha(R/'summary.json')==status['summary_sha256'];assert len(summary['diagnostics'])==4
started=time.monotonic();out={'source_summary_sha256':sha(R/'summary.json'),'passed':True,'all_reference_products':4,'all_head_fold_rows':448,'real_generated_probability_members_read':False,'arrays':[]}
for di in summary['diagnostics']:
 step=di['step_zero_based'];branch=di['reference_branch'];assert step in [9,19] and branch in ['qrn_kn','qrw_kw'];source=Path(inputs['steps'][str(step)]);assert sha(source)==summary['input_sha256'][str(step)]
 with np.load(source,allow_pickle=False) as z:
  p=z[branch];valid=z['valid_bins'];spans=z['physical_frame_spans_inclusive'];spatial=z['spatial_ids']
 assert p.shape==(56,32,8,32) and valid.tolist()==[True]*31+[False];assert np.isfinite(p).all();assert np.all(p[:,~valid]==0) and np.all(p[...,~valid]==0)
 path=R/di['array_file'];assert sha(path)==di['array_sha256']
 with np.load(path,allow_pickle=False) as z:a={k:z[k] for k in z.files}
 for k,v in a.items():
  if k=='candidate_diameter':assert np.array_equal(np.isnan(v),a['candidate_count']==0)
  else:assert np.isfinite(v).all(),k
 np.testing.assert_array_equal(a['input_valid_bins'],valid);np.testing.assert_array_equal(a['input_physical_frame_spans_inclusive'],spans);np.testing.assert_array_equal(a['input_spatial_ids'],spatial)
 bins=np.flatnonzero(valid);tau=spans[bins].mean(-1);disttime=np.abs(tau[:,None]-tau[None,:]);deltas=np.unique(disttime[disttime>0]);np.testing.assert_array_equal(a['resolutions'],deltas)
 rows={(x['head'],x['fold']):x for x in di['per_head_fold']};assert set(rows)=={(h,f) for h in range(56) for f in range(2)}
 maxerr=0.
 for h in range(56):
  c=p[h][bins][:,:,bins]
  for f,train in enumerate([[0,2,4,6],[1,3,5,7]]):
   test=[x for x in range(8) if x not in train];template=sum(c[:,i] for i in train)/4
   loo=np.array([[np.linalg.norm(np.sqrt(c[t,i])-np.sqrt(sum(c[t,j] for j in train if j!=i)/3)) for i in train] for t in range(31)])
   radius=loo.max();dist=np.linalg.norm(np.sqrt(c[:,test])[:,:,None,:]-np.sqrt(template)[None,None,:,:],axis=-1);maxerr=max(maxerr,float(np.max(abs(dist-a['heldout_distances'][h,f]))))
   np.testing.assert_allclose(a['template'][h,f],template,atol=1e-15,rtol=0);np.testing.assert_allclose(a['training_loo_residual'][h,f],loo,atol=1e-15,rtol=0);np.testing.assert_allclose(a['heldout_distances'][h,f],dist,atol=1e-15,rtol=0)
   cand=dist<=radius+64*np.finfo(float).eps;np.testing.assert_array_equal(a['candidate_mask'][h,f],cand);np.testing.assert_array_equal(a['candidate_count'][h,f],cand.sum(-1));correct=cand[np.arange(31),:,np.arange(31)];np.testing.assert_array_equal(a['candidate_contains_correct_time'][h,f],correct)
   near=np.abs(dist-dist.min(-1)[...,None])<=64*np.finfo(float).eps;np.testing.assert_array_equal(a['nearest_mask'][h,f],near);err=np.abs(tau[None,None,:]-tau[:,None,None]);best=np.min(np.where(near,err,np.inf),-1);worst=np.max(np.where(near,err,-np.inf),-1)
   np.testing.assert_array_equal(a['nearest_min_abs_time_error'][h,f],best);np.testing.assert_array_equal(a['nearest_max_abs_time_error'][h,f],worst)
   pair=np.linalg.norm(np.sqrt(template)[:,None,:]-np.sqrt(template)[None,:,:],axis=-1);curve=np.array([pair[disttime>=delta].min() for delta in deltas]);np.testing.assert_allclose(a['minimum_separation_curve'][h,f],curve,atol=1e-15,rtol=0);np.testing.assert_allclose(a['training_radius_margin_curve'][h,f],curve-2*radius,atol=1e-15,rtol=0)
   # Independent least-squares solution with the frozen numerical rank cutoff.
   x=(template-template[0]);x=x-x.mean(0);u,s,vh=np.linalg.svd(x,full_matrices=False);tol=np.finfo(float).eps*max(x.shape)*np.linalg.norm(template,2);keep=s>tol;w=vh[keep].T@((u[:,keep].T@(tau-tau.mean()))/s[keep]);offset=tau.mean()-template.mean(0)@w;prediction=c[:,test]@w+offset;np.testing.assert_allclose(a['linear_heldout_prediction'][h,f],prediction,rtol=1e-8,atol=1e-7)
   row=rows[h,f]
   for key,value in [('empty_fraction',np.mean(cand.sum(-1)==0)),('singleton_fraction',np.mean(cand.sum(-1)==1)),('multiple_fraction',np.mean(cand.sum(-1)>1)),('correct_time_in_candidate_fraction',correct.mean()),('linear_heldout_rmse',np.sqrt(np.mean((prediction-tau[:,None])**2)))]:assert np.isclose(row[key],value,rtol=1e-8,atol=1e-9),(key,row[key],value)
   assert np.isclose(row['nearest_best_abs_time_error']['mean'],best.mean(),rtol=0,atol=1e-10)
 counts=a['candidate_count'];mae=a['nearest_min_abs_time_error'].mean(axis=(-1,-2));linrmse=np.sqrt(np.mean(a['linear_heldout_error']**2,axis=(-1,-2)));margin=a['training_radius_margin_curve'];diam=a['candidate_diameter'];curve_summary=[{'resolution':float(d),'positive_margin_fraction_over112_head_folds':float(np.mean(margin[...,k]>0)),'mean_margin':float(margin[...,k].mean()),'max_margin':float(margin[...,k].max())} for k,d in enumerate(deltas)]
 out['arrays'].append({'step':step,'branch':branch,'sha256':sha(path),'max_independent_distance_abs_error':maxerr,'nearest_mean_abs_error':float(mae.mean()),'nearest_head_fold_mae_min_median_max':[float(mae.min()),float(np.median(mae)),float(mae.max())],'candidate_count_mean':float(counts.mean()),'empty_fraction':float(np.mean(counts==0)),'singleton_fraction':float(np.mean(counts==1)),'multiple_fraction':float(np.mean(counts>1)),'correct_time_in_candidate_fraction':float(a['candidate_contains_correct_time'].mean()),'nonempty_candidate_diameter_mean':float(np.nanmean(diam)),'linear_heldout_rmse_min_median_max':[float(linrmse.min()),float(np.median(linrmse)),float(linrmse.max())],'linear_inverse_gain_min_median_max':[float(a['linear_inverse_gain'].min()),float(np.median(a['linear_inverse_gain'])),float(a['linear_inverse_gain'].max())],'full_resolution_curve':curve_summary})
out['seconds']=time.monotonic()-started;print(json.dumps(out,allow_nan=False))
