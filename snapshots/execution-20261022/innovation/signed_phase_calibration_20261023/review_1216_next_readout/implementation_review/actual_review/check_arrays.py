"""Independent CPU-only H/P coefficient oracle; decodes no generated members."""
from pathlib import Path
import hashlib,json,time,sys
import numpy as np

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()

def check(policy,inputs,root,expected_summary_sha):
 start=time.monotonic();root=Path(root);summary_path=root/'summary.json'
 assert sha(summary_path)==expected_summary_sha
 summary=json.loads(summary_path.read_text());status=json.loads((root/'STATUS.json').read_text())
 assert status['status']=='complete' and status['results_written'] is True and status['summary_sha256']==expected_summary_sha
 assert summary['policy_sha256']==hashlib.sha256(json.dumps(policy,sort_keys=True).encode()).hexdigest()
 assert sha(inputs['upstream_status'])==policy['upstream']['status_sha256']
 us=json.loads(Path(inputs['upstream_status']).read_text());assert us['status']=='complete' and us['results_written'] is True
 assert us['summary_sha256']==policy['upstream']['summary_sha256']
 assert summary['input_sha256']['status']==policy['upstream']['status_sha256']
 allowed={'qrn_kn','qrw_kw','valid_bins','physical_frame_spans_inclusive','spatial_ids'}
 assert set(summary['decoded_npz_keys'])==allowed
 assert summary['planned_video_count']==1 and summary['planned_correlated_bins']==124
 assert summary['controller_released'] is False and summary['gpu_used'] is False and summary['model_calls']==0
 tol=64*np.finfo(np.float64).eps;oracle_tol=512*np.finfo(np.float64).eps
 assert summary['tie_tolerance']==tol
 rows=summary['diagnostics'];assert len(rows)==4
 expected_pairs={(step,a,b) for step in (9,19) for a,b in [('qrn_kn','qrw_kw'),('qrw_kw','qrn_kn')]}
 assert {(r['step_zero_based'],r['dictionary_branch'],r['query_branch']) for r in rows}==expected_pairs
 results=[];decoded=[]
 for step in (9,19):
  source=Path(inputs['steps'][str(step)]);expected=policy['upstream']['npz_sha256'][str(step)]
  assert sha(source)==expected==summary['input_sha256'][str(step)]
  with np.load(source,allow_pickle=False) as z:
   data={k:z[k] for k in sorted(allowed)};decoded+=list(sorted(allowed))
  valid=data['valid_bins'];assert valid.dtype==np.bool_ and np.array_equal(valid,np.asarray(policy['valid_bins']))
  ids=np.flatnonzero(valid);assert len(ids)==31
  for key in ['physical_frame_spans_inclusive','spatial_ids']:assert np.array_equal(data[key],np.asarray(policy[key]))
  times=data['physical_frame_spans_inclusive'][ids].astype(float).mean(-1)
  for key in ['qrn_kn','qrw_kw']:
   p=data[key];assert p.shape==(56,32,8,32) and p.dtype==np.float64
   assert np.isfinite(p).all() and np.min(p)>=0 and not np.any(p[:,~valid]) and not np.any(p[...,~valid])
   np.testing.assert_allclose(p[:,valid].sum(-1),1,atol=1e-12,rtol=0)
  for row in [r for r in rows if r['step_zero_based']==step]:
   a=data[row['dictionary_branch']];b=data[row['query_branch']]
   # Independent coefficient identity, accumulated separately over all H/P.
   # This does not import or call the production fingerprint/distance code.
   oracle=np.zeros((31,31),dtype=np.float64)
   for h in range(56):
    for p in range(8):
     da=np.sqrt(a[h,ids,p][:,ids]);qb=np.sqrt(b[h,ids,p][:,ids])
     oracle+=np.sum(qb*qb,axis=1)[:,None]+np.sum(da*da,axis=1)[None,:]-2*(qb@da.T)
   oracle/=56*8
   resultpath=root/row['array_file'];assert sha(resultpath)==row['array_sha256']
   with np.load(resultpath,allow_pickle=False) as z:out={k:z[k] for k in z.files}
   np.testing.assert_allclose(out['squared_distances'],oracle,atol=oracle_tol,rtol=0)
   for key in ['valid_bins','physical_frame_spans_inclusive','spatial_ids']:np.testing.assert_array_equal(out['input_'+key],data[key])
   np.testing.assert_array_equal(out['valid_indices'],ids);np.testing.assert_array_equal(out['nominal_frame_centers'],times)
   nearest=oracle<=oracle.min(-1,keepdims=True)+tol
   margin=np.array([min(oracle[i,j] for j in range(31) if i!=j)-oracle[i,i] for i in range(31)])
   unique=(nearest.sum(-1)==1)&nearest.diagonal()&(margin>tol)
   np.testing.assert_array_equal(out['nearest_mask'],nearest);np.testing.assert_array_equal(out['nearest_count'],nearest.sum(-1));np.testing.assert_array_equal(out['unique_correct'],unique)
   np.testing.assert_allclose(out['diagonal_squared_distance'],oracle.diagonal(),atol=oracle_tol,rtol=0);np.testing.assert_allclose(out['off_diagonal_margin'],margin,atol=oracle_tol,rtol=0)
   assert row['tested_correlated_bins']==31 and row['unique_correct_count']==int(unique.sum()) and row['all_unique_correct']==bool(unique.all())
   assert abs(row['minimum_margin']-float(margin.min()))<=oracle_tol
   assert len(row['per_bin'])==31
   for i,item in enumerate(row['per_bin']):
    assert item['query_bin']==int(ids[i]) and item['nominal_frame_center']==float(times[i])
    assert item['nearest_dictionary_bins']==ids[nearest[i]].tolist()
    assert item['nearest_signed_bin_errors']==(ids[nearest[i]]-ids[i]).tolist()
    assert item['nearest_signed_nominal_frame_errors']==(times[nearest[i]]-times[i]).tolist()
    assert item['unique_correct']==bool(unique[i])
    assert abs(item['off_diagonal_margin']-margin[i])<=oracle_tol
    assert abs(item['diagonal_squared_distance']-oracle[i,i])<=oracle_tol
   for unit,errors in [('bin',ids[None,:]-ids[:,None]),('nominal_frame',times[None,:]-times[:,None])]:
    lo=np.where(nearest,abs(errors),np.inf).min(-1);hi=np.where(nearest,abs(errors),-np.inf).max(-1)
    np.testing.assert_array_equal(out['nearest_min_absolute_'+unit+'_error'],lo);np.testing.assert_array_equal(out['nearest_max_absolute_'+unit+'_error'],hi)
    if unit=='nominal_frame':assert row['mean_best_absolute_nominal_frame_error']==float(lo.mean()) and row['mean_worst_absolute_nominal_frame_error']==float(hi.mean())
   results.append({'step':step,'dictionary':row['dictionary_branch'],'query':row['query_branch'],'result_sha256':row['array_sha256'],'max_matrix_abs_error':float(np.max(np.abs(out['squared_distances']-oracle))),'oracle_minimum_margin':float(margin.min()),'production_minimum_margin':row['minimum_margin'],'unique_correct':int(unique.sum()),'tested_bins':31,'mean_best_absolute_nominal_frame_error':row['mean_best_absolute_nominal_frame_error'],'mean_worst_absolute_nominal_frame_error':row['mean_worst_absolute_nominal_frame_error']})
  assert sha(source)==expected
 allpass=all(r['unique_correct']==31 for r in results)
 assert summary['all_unique_correct']==allpass and summary['unique_correct_correlated_bins']==sum(r['unique_correct'] for r in results)==124
 assert summary['tested_correlated_bins']==124 and summary['decision']==('CONTINUE_TO_INDEPENDENT_CONTENT_CALIBRATION_ONLY' if allpass else 'STOP_FULL_SUPPORT_ZERO_SHIFT_OBSERVER')
 assert sha(summary_path)==expected_summary_sha
 return {'status':'PASS_INDEPENDENT_REFERENCE_ONLY_ARRAY_RECOMPUTATION','summary_sha256':expected_summary_sha,'results':results,'source_keys_decoded':sorted(set(decoded)),'generated_members_decoded':False,'heads':56,'probes':8,'steps':[9,19],'directions':4,'bins_per_direction':31,'total_correlated_bins':124,'independent_video_count':1,'oracle':'Per-head/probe Hellinger coefficient identity with row norms, independently accumulated; no production core import','oracle_comparison_absolute_tolerance':float(oracle_tol),'production_tie_tolerance_unchanged':float(tol),'gpu_calls':0,'source_production_reexecution':False,'cpu_seconds':time.monotonic()-start}
