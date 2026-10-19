"""R24 sparse-step CPU binding; exact frozen gap5 primitives and thresholds."""
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
 with Path(p).open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
def check(v,s):
 if not v:raise ValueError(s)
def safe(root,rel):
 p=Path(rel);check(not p.is_absolute() and '..' not in p.parts and not(root/p).is_symlink() and (root/p).resolve().is_relative_to(root.resolve()),'unsafe path');return root/p
def ts(t):return {'shape':list(t.shape),'dtype':str(t.dtype),'sha256':hashlib.sha256(t.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()}
def arr(t):
 check(t.device.type=='cpu' and tuple(t.shape)==(1,24,42,46,82) and t.dtype==torch.float32 and torch.isfinite(t).all().item(),'video shape/dtype/finite');return t[0].permute(1,0,2,3).reshape(42,-1).numpy().astype(np.float64)
def main():
 started=time.time();lock=Path('/data5/researcher/h3_runs/timing_architecture_r2_20261016/analysis/pose/consumer.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);torch.set_num_threads(1)
 check(not torch.cuda.is_initialized(),'CUDA initialized');check(not(HERE/'RESULTS.json').exists(),'existing result must not be overwritten');p=read(HERE/'PROTOCOL.json');f=read(HERE/'FREEZE.json')
 for n,d in f['files'].items():check(sha(HERE/n)==d,'frozen file changed '+n)
 check(sha(HERE/'observer_frozen.py')==p['frozen_function_source_sha256']=='c84cca34903c9476adc36fa2af0c9e3507b736031efac5bf361187a2c63de075','function hash');check(sha(HERE/'observer_protocol.json')==p['frozen_reject_protocol_sha256']=='e84af137304d6b950e3bba078a96d1631c665a7fdcce84ef6c93d7e9551f4a16','reject hash')
 names=set(p['functions']);body=[n for n in ast.parse((HERE/'observer_frozen.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name in names];check({n.name for n in body}==names,'frozen funcs');ns={'np':np};exec(compile(ast.Module(body=body,type_ignores=[]),'<frozen gap5>','exec'),ns);limits=read(HERE/'observer_protocol.json')['reject_rules'];results={}
 centers=ns['geometry'](42);widths=np.array([(1,4,4,4,4)[i%5] for i in range(42)]);check(widths.sum()==141 and np.all(centers[5:]-centers[:-5]==17),'physical geometry')
 for cid,cp in p['cases'].items():
  run=cp['run_id'];arc=ROOT/'analysis/postrun/captured'/run
  for name,key in [('RUN_GATE.json','run_gate_sha256'),('CPU_COMPLETE.json','CPU_COMPLETE_sha256'),('FILE_INVENTORY.json','inventory_sha256')]:check(sha(arc/name)==cp[key],'verified archive binding '+name)
  check(read(arc/'RUN_GATE.json')['passed'] and read(arc/'CPU_COMPLETE.json')['passed'],'completed actual CPU gate');inv=read(arc/'FILE_INVENTORY.json');condpath=arc/'audit'/f'{run}_conditioning.json';check(sha(condpath)==cp['condition_sha256'],'condition hash');cond=read(condpath)
  check(read(arc/'RUN_GATE.json')['case']['video_sha256']==cp['source_video_sha256'],'source file binding')
  mfpath=arc/'audit/x0'/run/'manifest.json';check(sha(mfpath)==inv[str(mfpath.relative_to(arc))]['sha256'],'x0 manifest hash');mf=read(mfpath);rec=next(x for x in mf['captures'] if x['step_zero_based']==cp['step_zero_based'])
  fp=safe(arc,cp['snapshot_path']);check(fp.name==rec['file']==f"x0_step{cp['step_zero_based']:03d}.pt" and sha(fp)==cp['snapshot_file_sha256']==inv[cp['snapshot_path']]['sha256'],'actual x0 file');value=torch.load(fp,map_location='cpu',weights_only=True,mmap=True);meta={k:v for k,v in rec.items() if k not in ('file','capture_seconds')};check(value['metadata']==meta and rec['snapshot_kind']=='x0_estimate' and rec['model_call_one_based']==cp['step_zero_based']+1 and rec['run_id']==run,'endpoint metadata');check(ts(value['video'])=={k:rec['video'][k] for k in ('shape','dtype','sha256')},'endpoint signature');check(mf['normalization_stage']=='after_process_latent_out' and mf['video_latent_scale_factor']==1 and mf['geometry']=={'width':1312,'height':736,'frames':141,'fps':24},'normalization/geometry')
  shared=safe(arc/'audit',cond['pair_snapshot']['source_manifest']);check(sha(shared)==cond['pair_snapshot']['source_manifest_sha256'],'current condition binding');vc=cond['native_vae_calls'][1]['latent'];check('audit/'+vc['tensor_file']==cp['reference_path'],'current reference path');rp=safe(arc,cp['reference_path']);check(sha(rp)==cp['reference_file_sha256']==inv[cp['reference_path']]['sha256'],'reference file binding');ref=torch.load(rp,map_location='cpu',weights_only=True,mmap=True);check(ts(ref)==cp['reference_tensor']=={k:vc[k] for k in ('shape','dtype','sha256')}==cond['pair_snapshot']['actual']['references'][1]['clean_latent'],'actual reference tensor')
  a=ns['signal'](arr(ref),'same_phase_gap5');b=ns['signal'](arr(value['video']),'same_phase_gap5');rows=[ns['scan'](a,b,w,limits) for w in cp['windows_inclusive']];check(all(len(x['curve'])==49 for x in rows),'full49curves')
  for r in rows:r['would_trigger_coarse_start']=r['accepted'] and r['best'] is not None and r['best']['lag_frames']>=4
  check(sha(fp)==cp['snapshot_file_sha256'] and sha(rp)==cp['reference_file_sha256'] and sha(condpath)==cp['condition_sha256'],'input changed during read')
  results[cid]={'run_id':run,'actual_snapshot_file':str(fp),'actual_snapshot_file_sha256':sha(fp),'actual_snapshot_metadata':meta,'reference_file':str(rp),'reference_file_sha256':sha(rp),'reference_tensor':ts(ref),'condition_sha256':sha(condpath),'rows':rows}
 existing={}
 for key,bind in p['existing_005'].items():
  ep=safe(ROOT,bind['path']);check(sha(ep)==bind['sha256'],'existing005 result changed');old=read(ep);case=old['cases'][bind['case_key']]
  check(old['protocol_sha256']==bind['parent_protocol_sha256'] and case['run_id']==bind['run_id'] and case['actual_snapshot_metadata']['step_zero_based']==5 and case['actual_snapshot_file_sha256']==bind['snapshot_file_sha256'],'existing005 binding')
  check([r['window_inclusive'] for r in case['rows']]==bind['windows_inclusive'] and all(len(r['curve'])==49 for r in case['rows']),'existing005 windows/curves')
  existing[key]={'source_result_path':bind['path'],'source_result_sha256':bind['sha256'],'case':case,'recomputed':False}
 result={'protocol_sha256':sha(HERE/'PROTOCOL.json'),'freeze_sha256':sha(HERE/'FREEZE.json'),'script_sha256':sha(__file__),'cases':results,'existing_005':existing,'limits':limits,'geometry':{'bin_widths':widths.tolist(),'bin_centers':centers.tolist(),'gap5_physical_edge_times':a[0].tolist(),'gap5_span_physical_frames':17},'elapsed_seconds':time.time()-started,'CUDA_initialized':torch.cuda.is_initialized(),'limitations':['Gap5 spans17physicalframes and is a coarse global signed derivative.','Final near-synchronous pose is not index005 same-endpoint truth. A positive early readout may represent temporary early deviation that native later resolves, not proven estimator error.','Only indices005/010/015/019 are observed; no all-step online false-trigger or stop claim.','No endpoint decoding, no new encoding, no controller, no threshold/ROI/window tuning.']}
 with (HERE/'RESULTS.json').open('x') as out:json.dump(result,out,indent=2,allow_nan=False);out.write('\n')
 print(json.dumps({'saved':str(HERE/'RESULTS.json'),'seconds':result['elapsed_seconds'],'rows':{k:[{'window':r['window_inclusive'],'accepted':r['accepted'],'best':r['best'],'rejection_reasons':r['rejection_reasons'],'would_trigger_coarse_start':r['would_trigger_coarse_start']} for r in v['rows']] for k,v in results.items()}}))
if __name__=='__main__':
 try:main()
 except BlockingIOError:print('CPU_LOCK_BUSY');raise SystemExit(75)
