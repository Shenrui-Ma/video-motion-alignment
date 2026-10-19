"""Fixed full-frame gap5 readout on actual native R7 captures, CPU only."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'
from pathlib import Path
import hashlib,importlib.util,json,time
import numpy as np
import torch
HERE=Path(__file__).resolve().parent
PIN='c7f65d41fb12f660c60c2ab2dbe8972b4d908771b88683f4139231c51cfc861b'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,s):
 if not v:raise RuntimeError(s)
def signature(x):return {'shape':list(x.shape),'dtype':str(x.dtype),'sha256':hashlib.sha256(x.contiguous().view(torch.uint8).numpy()).hexdigest()}
def store(name,x):
 with (HERE/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def array(x,shape):
 require(tuple(x.shape)==tuple(shape) and x.dtype==torch.float32 and x.device.type=='cpu','unexpected video shape/dtype/device')
 require(bool(torch.isfinite(x).all()),'nonfinitevideo')
 return x[0].permute(1,0,2,3).reshape(42,-1).numpy().astype(np.float64)
def classify(w):
 if not w['accepted']:return 'OFF_UNKNOWN'
 lag=w['best']['lag_frames']
 if lag>=4:return 'ON_DELAYED'
 if -2<=lag<=2:return 'OFF_ALIGNED'
 if lag==3:return 'HOLD_PREVIOUS'
 return 'OFF_ADVANCED'
def main():
 started=time.perf_counter();torch.set_num_threads(1)
 require(not torch.cuda.is_initialized(),'CUDA initialized')
 require(sha(HERE/'PROTOCOL.json')==PIN,'protocol changed');p=json.loads((HERE/'PROTOCOL.json').read_text())
 require(sha(p['frozen_source_path'])==p['frozen_source_sha256'],'observer source changed')
 require(sha(p['frozen_protocol_path'])==p['frozen_protocol_sha256'],'observer protocol changed')
 d=json.loads((HERE/'download_manifest.json').read_text());base=HERE/'inputs'
 for f in d['files']:require(sha(base/f['relative'])==f['sha256'],'download changed '+f['relative'])
 require(d['complete'] and d['run_id']==p['run_id'],'wrong/incomplete download')
 require(sha(base/'configs'/f"{p['run_id']}.json")==p['planned_config_sha256'],'actual graph differs from pinned planned graph')
 c=json.loads((base/'audit'/f"{p['run_id']}_conditioning.json").read_text())
 require(c['run_id']==p['run_id'],'actualcondition run mismatch')
 refmeta=[x['latent'] for x in c['native_vae_calls'] if x['latent']['shape']==p['shape']]
 require(len(refmeta)==1,'uniqueactualref missing')
 require('audit/'+refmeta[0]['tensor_file']==d['reference_relative'],'reference path mismatch')
 reference=torch.load(base/d['reference_relative'],weights_only=True,map_location='cpu',mmap=True)
 sig=signature(reference);require(sig=={k:refmeta[0][k] for k in sig},'actual reference rawSHA mismatch')
 xroot=base/'audit/x0'/p['run_id'];m=json.loads((xroot/'manifest.json').read_text())
 require(m['run_id']==p['run_id'] and m['status']=='complete' and m['callback_count']==20,'capture incomplete')
 require(m['capture_steps_zero_based']==p['snapshot_indices_zero_based'],'captureindices mismatch')
 require(m['normalization_stage']=='after_process_latent_out' and m['video_latent_scale_factor']==1 and m['audio_scale']==4,'normalization mismatch')
 require(m['target_latent_shapes']==[p['shape'],[1,32,2,235]],'target shapes mismatch')
 captures=m['captures']+[m['final_sampler_result']]
 require([x['file'] for x in captures]==[f'x0_step{i:03d}.pt' for i in p['snapshot_indices_zero_based']]+['sampler_final.pt'],'capture set mismatch')
 spec=importlib.util.spec_from_file_location('frozen_gap5',p['frozen_source_path']);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 a=module.signal(array(reference,p['shape']),'same_phase_gap5');rows=[];checks=[]
 for item in captures:
  payload=torch.load(xroot/item['file'],weights_only=True,map_location='cpu',mmap=True);check={'file':item['file']}
  for key in ('video','audio'):
   value=signature(payload[key]);require(value=={k:item[key][k] for k in value},'snapshotSHA mismatch '+item['file']+key);check[key]=value
  require(payload['metadata']['run_id']==p['run_id'] and payload['metadata']['step_zero_based']==item['step_zero_based'],'snapshot metadata mismatch')
  checks.append(check);b=module.signal(array(payload['video'],p['shape']),'same_phase_gap5')
  windows=[module.scan(a,b,w,p['reject_rules']) for w in p['windows_inclusive']]
  row={'file':item['file'],'snapshot_kind':item['snapshot_kind'],'denoising_index_zero_based':item['step_zero_based'],'model_call_one_based':item['model_call_one_based'],'sigma_video':item['sigma_video'],'windows':windows,'hypothetical_main_window_decision_class':classify(windows[0]),'independent_early_pose':'unknown; not yet supplied','ground_truth_policy':'Do not borrow final pose labels for earlyx0; native trajectory notclosedloop'}
  rows.append(row);print(item['file'],[w['best']['lag_frames'] if w['best'] else None for w in windows],[w['accepted'] for w in windows],row['hypothetical_main_window_decision_class'],flush=True)
 first=rows[0]['windows'][0]
 result={'schema':'r7-native-observer-result-v1','protocol_sha256':PIN,'script_sha256':sha(__file__),'download_manifest_sha256':sha(HERE/'download_manifest.json'),'reference':sig,'input_checks':checks,'rows':rows,'first_index5_would_trigger_forward6':first['accepted'] and first['best']['lag_frames']>=4,'no_parameter_changes':True,'cpu_only':True,'CUDA_initialized':torch.cuda.is_initialized(),'elapsed_seconds':time.perf_counter()-started,'torch':torch.__version__,'numpy':np.__version__,'independent_final_replay_pose':'pending critic; report update separate from frozen raw observer results','selection':'negative control chosen using prior normal R1 outcome; not independent unseen scene'}
 require(not result['CUDA_initialized'],'CUDA becameinitialized')
 for f in d['files']:require(sha(base/f['relative'])==f['sha256'],'input changed '+f['relative'])
 store('RESULTS.json',result);print('first_index5_would_trigger_forward6',result['first_index5_would_trigger_forward6'],'elapsed',result['elapsed_seconds'])
if __name__=='__main__':main()
