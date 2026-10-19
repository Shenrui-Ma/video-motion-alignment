"""Apply the already-frozen full-frame gap5 observer to existing R4 x0; CPU only."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'): os.environ[key]='1'
from pathlib import Path
import hashlib, importlib.util, json, time
import numpy as np
import torch
HERE=Path(__file__).resolve().parent
R2=HERE.parents[2]/'h3-timing-architecture-r2-20261016'
R4=HERE.parents[2]/'h3-timing-target-path-r4-20261016'
FROZEN=R2/'analysis/vae_phase_calibration'
SOURCE_SHA='c84cca34903c9476adc36fa2af0c9e3507b736031efac5bf361187a2c63de075'
PROTOCOL_SHA='e84af137304d6b950e3bba078a96d1631c665a7fdcce84ef6c93d7e9551f4a16'
REMOTE_SHA={
'manifest.json':'c2650fafd671f72cf066fda633a8fbb06b4a58a4a6998b5f7fe2861c5f607ff7',
'sampler_final.pt':'dd181ea6e8385e4f5d7f71a700709d12bb5c78a91bd33e69cecf8a765684d73a',
'x0_step005.pt':'3c7e8f15ac00403909292fd34bcdb25f59a15c7377beac01eec2906d82765d8b',
'x0_step006.pt':'7503aff763d25ad661c0c3cb706b001834291f5e31ba3d3f7cb816ed35e878a0',
'x0_step007.pt':'206a2ca93f1adaedecdd6ed225c21f297a3a962852b4b81ca5df6de4cc067a0a',
'x0_step008.pt':'5ce94d8f29eacb526f5b49158cece76cada773b10af9c58718a5620d8aa30ca6',
'x0_step009.pt':'78688736a5346de0c6f000ebd9b58f1e1717e16faca5a4cfd95bd8f4ee6de1f2',
'x0_step010.pt':'bf69b975ee866b8e3e6ea3ee3113c968ee36bf39d91c2e842024e33dda4cc0cc',
'x0_step015.pt':'1f7fdb47e406f38566a5f032ab5645826e9ecbfe464bbbb2a567a135ef4f8b88',
'x0_step019.pt':'469b8e535a20f87d273de81fcf2e14a5b2f4af5007535ea04ae7f32ac674c730'}

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def signature(z): return {'shape':list(z.shape),'dtype':str(z.dtype),'sha256':hashlib.sha256(z.contiguous().view(torch.uint8).numpy()).hexdigest()}
def require(check, why):
 if not check: raise RuntimeError(why)
def dump(name,obj):
 with (HERE/name).open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def array(z):
 require(tuple(z.shape)==(1,24,42,46,82) and z.dtype==torch.float32 and z.device.type=='cpu','unexpected video shape/dtype/device')
 require(bool(torch.isfinite(z).all()),'nonfinite video')
 return z[0].permute(1,0,2,3).reshape(42,-1).numpy().astype(np.float64)

def main():
 started=time.perf_counter();torch.set_num_threads(1)
 require(not torch.cuda.is_initialized(),'CUDA was initialized')
 require(sha(FROZEN/'evaluate.py')==SOURCE_SHA,'Frozen evaluator changed')
 require(sha(FROZEN/'PROTOCOL.json')==PROTOCOL_SHA,'Frozen protocol changed')
 p=json.loads((FROZEN/'PROTOCOL.json').read_text())
 m=json.loads((HERE/'inputs/manifest.json').read_text())
 for name,digest in REMOTE_SHA.items(): require(sha(HERE/'inputs'/name)==digest,'download SHA mismatch '+name)
 require(m['status']=='complete' and m['callback_count']==20,'R4 incomplete capture')
 require(m['run_id']=='r4_s05_native_path_probe','wrong R4 run')
 captures=m['captures']+[m['final_sampler_result']]
 require([x['file'] for x in captures]==[f'x0_step{i:03d}.pt' for i in [5,6,7,8,9,10,15,19]]+['sampler_final.pt'],'unexpected snapshot set')
 condition_path=R4/'analysis/pose/pilot/r4_s05_native_path_probe_provenance/conditioning.json'
 cond=json.loads(condition_path.read_text())
 reference_info=p['inputs']['original'];reference_path=Path(reference_info['path'])
 require(sha(reference_path)==reference_info['file_sha256'],'reference file changed')
 reference=torch.load(reference_path,map_location='cpu',weights_only=True,mmap=True)
 reference_sig=signature(reference)
 require(reference_sig==reference_info['tensor'],'reference raw tensor mismatch')
 ref_calls=[v['latent'] for v in cond['native_vae_calls'] if v['latent']['shape']==[1,24,42,46,82]]
 require(len(ref_calls)==1,'ambiguous R4 video VAE reference')
 require({k:ref_calls[0][k] for k in reference_sig}==reference_sig,'R4 actual reference differs from VAE controls original')
 replay_path=R4/'analysis/pose/replication/native_replay_complete_gate.json'
 replay=json.loads(replay_path.read_text());require(replay['passed'] is True,'R2/R4 replay not passed')
 for name,digest in replay['evidence_sha256'].items(): require(sha(replay_path.parent/name)==digest,'Replay gate evidence changed '+name)
 pin={'schema':'r4-native-gap5-precheck-v1','source_path':str(FROZEN/'evaluate.py'),'source_sha256':SOURCE_SHA,'protocol_path':str(FROZEN/'PROTOCOL.json'),'protocol_sha256':PROTOCOL_SHA,'method':'same_phase_gap5','region':'full_frame','roi_yxyx':p['regions']['primary_full_frame'],'windows_inclusive':p['windows_inclusive'],'reject_rules':p['reject_rules'],'reference':reference_info,'r4_conditioning_path':str(condition_path),'r4_conditioning_sha256':sha(condition_path),'r4_actual_reference':ref_calls[0],'r4_capture_remote':'/data3/researcher/h3_runs/timing_target_path_r4_20261016/audit/x0/r4_s05_native_path_probe','download_file_sha256':REMOTE_SHA,'replay_gate_path':str(replay_path),'replay_gate_sha256':sha(replay_path),'decisions':'No parameter/window/ROI change; all existing snapshots; no early pose ground truth; final pose reused only because exact same-host replay passed'}
 
 if (HERE/'PROTOCOL.json').exists(): require(json.loads((HERE/'PROTOCOL.json').read_text())==pin,'retry protocol changed')
 else: dump('PROTOCOL.json',pin)
 spec=importlib.util.spec_from_file_location('frozen_gap5',FROZEN/'evaluate.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 a=mod.signal(array(reference),'same_phase_gap5');rows=[];tensor_checks=[]
 for item in captures:
  payload=torch.load(HERE/'inputs'/item['file'],map_location='cpu',weights_only=True,mmap=True)
  require(set(('video','audio')).issubset(payload),'missing streams')
  check={'file':item['file']}
  for key in ('video','audio'):
   sig=signature(payload[key]);expected={k:item[key][k] for k in sig};require(sig==expected,'snapshot signature mismatch '+item['file']+':'+key);check[key]=sig
  tensor_checks.append(check)
  b=mod.signal(array(payload['video']),'same_phase_gap5')
  windows=[mod.scan(a,b,w,p['reject_rules']) for w in p['windows_inclusive']]
  row={'file':item['file'],'snapshot_kind':item['snapshot_kind'],'denoising_index_zero_based':item['step_zero_based'],'model_call_one_based':item['model_call_one_based'],'sigma_video':item['sigma_video'],'windows':windows,'independent_early_pose':'unknown; not evaluated'}
  rows.append(row)
  print(item['file'],[w['best']['lag_frames'] if w['best'] else None for w in windows],[w['accepted'] for w in windows],flush=True)
 pose={}
 for threshold in (0.3,0.5):
  f=R2/f'analysis/pose/pilot/r2_s05_native_00001_.threshold{threshold}.timing.json';obj=json.loads(f.read_text())
  items=[v for v in obj['diagnostics'] if v['feature']=='arm_direction']
  require([v['window'] for v in items]==p['windows_inclusive'],'pose windows mismatch')
  pose[str(threshold)]={'path':str(f),'sha256':sha(f),'windows':[{'window':v['window'],'status':v['status'],'flags':v.get('flags',[]),'reliable_lag_frames':v.get('reliable_lag_frames'),'same_frame_coverage':v['same_frame']['coverage']} for v in items]}
 final=rows[-1]
 for idx,w in enumerate(final['windows']):
  w['independent_final_pose']={t:x['windows'][idx] for t,x in pose.items()}
  labels=[x['windows'][idx]['reliable_lag_frames'] for x in pose.values()]
  w['both_pose_thresholds_known']=all(x is not None for x in labels)
  w['within_two_frames_both_thresholds']=all(abs(w['best']['lag_frames']-x)<=2 for x in labels) if all(x is not None for x in labels) and w['accepted'] else None
 output={'schema':'r4-native-gap5-precheck-result-v1','protocol_sha256':sha(HERE/'PROTOCOL.json'),'script_sha256':sha(__file__),'inputs_verified':tensor_checks,'reference_sha_equal_actual_r4':True,'rows':rows,'final_pose_provenance':pose,'all_36_observer_windows_accepted':all(w['accepted'] for r in rows for w in r['windows']),'primary_window_all_positive_delay':all(r['windows'][0]['accepted'] and r['windows'][0]['best']['lag_frames']>=4 for r in rows),'scope':'same delayed example/runtime feasibility, not new independent validation or universal observer proof','cpu_only':True,'CUDA_initialized':torch.cuda.is_initialized(),'elapsed_seconds':time.perf_counter()-started,'torch':torch.__version__,'numpy':np.__version__}
 require(not output['CUDA_initialized'],'CUDA became initialized')
 for name,digest in REMOTE_SHA.items():require(sha(HERE/'inputs'/name)==digest,'input changed '+name)
 require(sha(reference_path)==reference_info['file_sha256'],'reference changed')
 dump('RESULTS.json',output)
 print('elapsed_seconds',output['elapsed_seconds'],flush=True)
if __name__=='__main__':main()
