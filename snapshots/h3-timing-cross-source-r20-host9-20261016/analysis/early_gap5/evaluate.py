"""Run only after final R20 verifier. Reuse frozen pure gap5 funcs, no model."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'
import ast,fcntl,hashlib,json,time
from pathlib import Path
import numpy as np
import torch
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def check(x,s):
 if not x:raise ValueError(s)
def ts(t):return {'shape':list(t.shape),'dtype':str(t.dtype),'sha256':hashlib.sha256(t.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()}
def arr(t):
 check(t.device.type=='cpu' and tuple(t.shape)==(1,24,42,46,82) and t.dtype==torch.float32 and torch.isfinite(t).all().item(),'video shape/dtype/finite')
 return t[0].permute(1,0,2,3).reshape(42,-1).numpy().astype(np.float64)
def main():
 started=time.time();lock=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);torch.set_num_threads(1)
 check(not torch.cuda.is_initialized(),'CUDA initialized');check(not (HERE/'RESULTS.json').exists(),'do not overwrite existing results')
 p=read(HERE/'PROTOCOL.json');check(sha(HERE/'observer_frozen.py')==p['frozen_function_source_sha256']=='c84cca34903c9476adc36fa2af0c9e3507b736031efac5bf361187a2c63de075','function hash');check(sha(HERE/'observer_protocol.json')==p['frozen_reject_protocol_sha256']=='e84af137304d6b950e3bba078a96d1631c665a7fdcce84ef6c93d7e9551f4a16','reject hash')
 check(read(ROOT/'audit/completed_pair_gate.json')['passed'],'final paired execution gate')
 check(read(ROOT/'analysis/pose/cpu_complete.json')['status']=='CPU_complete','final pose analysis first')
 run='r20_s07_native';folder=ROOT/'audit/x0'/run;mf=read(folder/'manifest.json');record=next(x for x in mf['captures'] if x['step_zero_based']==5);fp=folder/record['file'];check(fp.name=='x0_step005.pt','wrong endpoint')
 value=torch.load(fp,map_location='cpu',weights_only=True,mmap=True)
 expected={k:v for k,v in record.items() if k not in ('file','capture_seconds')}
 check(value['metadata']==expected and record['snapshot_kind']=='x0_estimate' and record['model_call_one_based']==6,'actual endpoint metadata')
 check({k:record['video'][k] for k in ('shape','dtype','sha256')}==ts(value['video']),'endpoint signature')
 check(mf['normalization_stage']=='after_process_latent_out' and mf['video_latent_scale_factor']==1,'latent normalization')
 cond=read(ROOT/'audit'/f'{run}_conditioning.json');shared=ROOT/'audit'/cond['pair_snapshot']['source_manifest'];check(sha(shared)==cond['pair_snapshot']['source_manifest_sha256'],'actual condition binding')
 vc=cond['native_vae_calls'][1]['latent'];check(vc['shape']==[1,24,42,46,82],'actual reference shape')
 rp=ROOT/'audit'/vc['tensor_file'];check(rp.resolve().is_relative_to((ROOT/'audit').resolve()) and not rp.is_symlink(),'reference path')
 ref=torch.load(rp,map_location='cpu',weights_only=True,mmap=True);check(ts(ref)=={k:vc[k] for k in ('shape','dtype','sha256')},'actual ref signature')
 check(ts(ref)==cond['pair_snapshot']['actual']['references'][1]['clean_latent'],'actual processed reference')
 names=set(p['functions']);body=[n for n in ast.parse((HERE/'observer_frozen.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names];check({n.name for n in body}==names,'frozen funcs')
 ns={'np':np};exec(compile(ast.Module(body=body,type_ignores=[]),'<frozen gap5>','exec'),ns)
 limits=read(HERE/'observer_protocol.json')['reject_rules'];a=ns['signal'](arr(ref),'same_phase_gap5');b=ns['signal'](arr(value['video']),'same_phase_gap5')
 rows=[ns['scan'](a,b,w,limits) for w in [p['window_inclusive_primary'],*p['secondary_windows_inclusive']]]
 check(all(len(x['curve'])==49 for x in rows),'full49curve')
 result={'protocol_sha256':sha(HERE/'PROTOCOL.json'),'script_sha256':sha(Path(__file__)),'run_id':run,'actual_snapshot_file':str(fp),'actual_snapshot_file_sha256':sha(fp),'actual_snapshot_metadata':expected,'reference_file':str(rp),'reference_file_sha256':sha(rp),'reference_tensor':ts(ref),'condition_sha256':sha(ROOT/'audit'/f'{run}_conditioning.json'),'rows':rows,'limits':limits,'elapsed_seconds':time.time()-started,'CUDA_initialized':torch.cuda.is_initialized(),'limitations':['Gap5 spans17physicalframes; coarse observation only.','Accepted does not establish true pose phase or2frame stop accuracy.','Actual index005 current endpoint used, not final video or old example.']}
 with (HERE/'RESULTS.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps({'saved':str(HERE/'RESULTS.json'),'rows':[{'window':r['window_inclusive'],'accepted':r['accepted'],'best':r['best'],'rejection_reasons':r['rejection_reasons']} for r in rows]}))
if __name__=='__main__':main()
