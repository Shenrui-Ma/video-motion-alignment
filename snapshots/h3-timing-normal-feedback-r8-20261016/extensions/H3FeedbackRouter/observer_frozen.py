"""Frozen CPU-only VAE phase diagnostics. Never imports Comfy or invokes a model."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import hashlib,json,time
import numpy as np
HERE=Path(__file__).resolve().parent
PROTOCOL_SHA='e84af137304d6b950e3bba078a96d1631c665a7fdcce84ef6c93d7e9551f4a16'
METHODS=('raw_adjacent','whole_time_centering','phase_mean_centering','constant0_template','same_phase_gap5')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def geometry(n=42):
 widths=np.array([(1,4,4,4,4)[i%5] for i in range(n)])
 starts=np.cumsum(np.r_[0,widths[:-1]])
 return starts+(widths-1)/2

def phase_mean(z):
 return np.stack([z[k::5].mean(0) for k in range(5)])

def signal(z,method,template=None):
 """z [T,feature], float64. Return physical timestamps and derivatives."""
 if z.dtype!=np.float64 or z.ndim!=2:raise ValueError('expected float64 [T,D]')
 centers=geometry(len(z));step=5 if method=='same_phase_gap5' else 1
 if method=='whole_time_centering':y=z-z.mean(0,keepdims=True)
 elif method=='phase_mean_centering':y=z-phase_mean(z)[np.arange(len(z))%5]
 elif method=='constant0_template':
  if template is None or template.shape!=(5,z.shape[1]):raise ValueError('invalid constant template')
  y=z-template[np.arange(len(z))%5]
 elif method in ('raw_adjacent','same_phase_gap5'):y=z
 else:raise ValueError(method)
 dt=centers[step:]-centers[:-step]
 return (centers[step:]+centers[:-step])/2,(y[step:]-y[:-step])/dt[:,None]

def interp(times,values,queries):
 up=np.searchsorted(times,queries,side='right').clip(1,len(times)-1);lo=up-1
 w=((queries-times[lo])/(times[up]-times[lo])).clip(0,1)
 return values[lo]*(1-w[:,None])+values[up]*w[:,None]

def scan(a,b,window,limits):
 t=np.arange(window[0],window[1]+1,dtype=float)
 av=interp(*a,t);an=np.linalg.norm(av,axis=1);ar=an/np.sqrt(av.shape[1]);rows=[]
 source_clamp=(t<a[0][0])|(t>a[0][-1])
 for lag in range(-24,25):
  q=t+lag;bv=interp(*b,q);bn=np.linalg.norm(bv,axis=1);br=bn/np.sqrt(bv.shape[1]);valid=(ar>limits['min_per_frame_rms'])&(br>limits['min_per_frame_rms'])
  score=float(np.mean(1-np.sum(av[valid]*bv[valid],axis=1)/(an[valid]*bn[valid]))) if valid.any() else None
  rows.append({'lag_frames':lag,'signed_cosine_error':score,'valid_frames':int(valid.sum()),'coverage':float(valid.mean()),'clamped_frames':int((source_clamp|(q<b[0][0])|(q>b[0][-1])).sum()),'source_signal_rms':float(np.sqrt(np.mean(av*av))),'target_signal_rms':float(np.sqrt(np.mean(bv*bv)))})
 ranked=sorted((r for r in rows if r['signed_cosine_error'] is not None),key=lambda r:(r['signed_cosine_error'],r['lag_frames']))
 best=ranked[0] if ranked else None
 rival=next((r for r in ranked if abs(r['lag_frames']-best['lag_frames'])>=limits['separated_competitor_frames']),None) if best else None
 margin=None if rival is None else rival['signed_cosine_error']-best['signed_cosine_error']
 reasons=[]
 if best is None:reasons.append('low_signal_no_valid_frames')
 else:
  if best['coverage']<limits['required_valid_coverage']:reasons.append('incomplete_nonzero_signal_coverage')
  if margin is None or margin<=limits['max_ambiguous_margin']:reasons.append('ambiguous_separated_lag')
  if abs(best['lag_frames'])==24:reasons.append('search_boundary')
  if best['clamped_frames']>0:reasons.append('winner_endpoint_clamp')
 return {'window_inclusive':list(window),'best':best,'separated_runner_up':rival,'margin':margin,'accepted':not reasons,'rejection_reasons':reasons,'curve':rows}

def main():
 started=time.time()
 if sha(HERE/'PROTOCOL.json')!=PROTOCOL_SHA:raise RuntimeError('protocol changed')
 p=json.loads((HERE/'PROTOCOL.json').read_text());import torch
 torch.set_num_threads(1)
 if torch.cuda.is_initialized():raise RuntimeError('CUDA must remain uninitialized')
 latents={};checks={}
 for name,item in p['inputs'].items():
  path=Path(item['path'])
  if sha(path)!=item['file_sha256']:raise RuntimeError('input file SHA mismatch '+name)
  z=torch.load(path,map_location='cpu',weights_only=True,mmap=True)
  meta={'shape':list(z.shape),'dtype':str(z.dtype),'sha256':hashlib.sha256(z.contiguous().view(torch.uint8).numpy()).hexdigest()}
  if meta!=item['tensor']:raise RuntimeError('input tensor SHA/shape/dtype mismatch '+name)
  if not bool(torch.isfinite(z).all()):raise RuntimeError('nonfinite input')
  latents[name]=z;checks[name]=meta
 results={'schema':'h3-vae-phase-calibration-result-v1','protocol_sha256':PROTOCOL_SHA,'script_sha256':sha(__file__),'inputs_verified':checks,'regions':{},'CPU_only':True,'torch':torch.__version__,'numpy':np.__version__}
 for region,roi in p['regions'].items():
  y0,y1,x0,x1=roi;arrays={k:v[0,:,:,y0:y1,x0:x1].permute(1,0,2,3).reshape(42,-1).numpy().astype(np.float64) for k,v in latents.items()};template=phase_mean(arrays['constant0']);entries={}
  for method in METHODS:
   signals={k:signal(v,method,template) for k,v in arrays.items()};arms={}
   for arm,expected in [('original',0),('delay4',4),('delay8',8),('constant0',None)]:
    a=signals['constant0'] if arm=='constant0' else signals['original'];b=signals[arm]
    rows=[scan(a,b,w,p['reject_rules']) for w in p['windows_inclusive']]
    for row in rows:
     row['expected_lag_frames']=expected
     row['absolute_error_frames']=None if expected is None or row['best'] is None else abs(row['best']['lag_frames']-expected)
     row['within_tolerance']=None if expected is None else row['best'] is not None and row['absolute_error_frames']<=2
     row['necessary_case_pass']=not row['accepted'] if expected is None else row['accepted'] and row['within_tolerance']
    arms[arm]={'signal_rms':float(np.sqrt(np.mean(b[1]*b[1]))),'rows':rows}
   entries[method]={'arms':arms,'all_16_cases_pass':all(r['necessary_case_pass'] for a in arms.values() for r in a['rows']),'delay_cases_passed':sum(r['necessary_case_pass'] for k,a in arms.items() if k!='constant0' for r in a['rows']),'constant_cases_rejected':sum(not r['accepted'] for r in arms['constant0']['rows'])}
   print(region,method,'lags', {k:[r['best']['lag_frames'] if r['best'] else None for r in a['rows']] for k,a in arms.items()},'PASS',entries[method]['all_16_cases_pass'],flush=True)
  raw=signal(arrays['original'],'raw_adjacent')[1];center=signal(arrays['original'],'whole_time_centering')[1]
  results['regions'][region]={'roi_yxyx':roi,'methods':entries,'whole_time_centering_raw_max_abs':float(np.abs(raw-center).max())}
 results['primary_any_method_passed']=any(v['all_16_cases_pass'] for v in results['regions']['primary_full_frame']['methods'].values())
 results['elapsed_seconds']=time.time()-started;results['CUDA_initialized']=torch.cuda.is_initialized()
 # File/content identities checked a second time; analysis never mutates the mmap inputs.
 for name,item in p['inputs'].items():
  if sha(item['path'])!=item['file_sha256']:raise RuntimeError('input changed during analysis '+name)
 with (HERE/'RESULTS.json').open('x') as f:json.dump(results,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
 print('primary_any_method_passed',results['primary_any_method_passed'],'seconds',results['elapsed_seconds'])
if __name__=='__main__':main()
