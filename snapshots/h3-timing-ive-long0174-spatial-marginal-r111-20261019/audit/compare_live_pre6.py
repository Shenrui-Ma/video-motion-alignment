"""Read sealed actual captures, compare the six pre-intervention AV predictions on CPU."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import json,sys,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'analysis/postrun'),str(ROOT/'scripts')]
import torch
from capture_checks import checked_snapshot
from r111_contract import SHAPES,read,sha

torch.set_num_threads(1)
runs={
 'spatial':(ROOT,'r111_long_0174_seed2026101701_forced'),
 'fixed':(Path('/data4/researcher/h3_runs/timing_ive_long0174_guidance_r107_20261019'),'r107_long_0174_seed2026101701_forced'),
 'native':(Path('/data4/researcher/h3_runs/timing_ive_native_screen_r96_20261018'),'r96_long_0174_seed2026101701_native')}
manifest={key:read(root/'audit/x0'/run/'manifest.json') for key,(root,run) in runs.items()}
assert all(len(m['captures'])>=6 for m in manifest.values()),'first6 captures pending'
assert all(m['noise']==manifest['native']['noise'] and m['sigmas_video']==manifest['native']['sigmas_video'] for m in manifest.values())
rows=[]
for i in range(6):
 values={};files={}
 for key,(root,run) in runs.items():
  record=manifest[key]['captures'][i]
  assert record['step_zero_based']==i and record['model_call_one_based']==i+1
  values[key],files[key]=checked_snapshot(root/'audit/x0'/run,record,run,SHAPES)
 equal={a+'_vs_'+b:{kind:torch.equal(values[a][kind],values[b][kind]) for kind in ('video','audio')} for a,b in [('spatial','native'),('spatial','fixed'),('fixed','native')]}
 rows.append({'step_zero_based':i,'snapshots':files,'equality':equal})
 del values
result={'schema':'r111-actual-pre6-threeway-AV-trajectory-comparison-v1','created_unix':time.time(),'passed':all(x for row in rows for e in row['equality'].values() for x in e.values()),'run_ids':{k:v[1] for k,v in runs.items()},'predictions':rows,'manifest_prefix_records':{k:m['captures'][:6] for k,m in manifest.items()},'same_initial_packed_noise_signature':manifest['native']['noise'],'same_sampler_sigmas':manifest['native']['sigmas_video'],'meaning':'Exact actual CPU tensor equality of current-sigma denoised AV predictions for steps0..5, after_process_latent_out. Separate from before-DiT condition equality.','intermediate_noisy_states_captured':False,'state_scope':'Intermediate noisy x states are not archived. Same initial noise, Euler grid and these equal predictions support equal pre-intervention progression under the pinned deterministic sampler; this receipt measures the saved predictions directly.','runtime_modified':False,'CUDA_started':False}
p=ROOT/'audit/ACTUAL_PRE6_THREEWAY_TRAJECTORY.json'
with p.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'file':str(p),'sha256':sha(p),'passed':result['passed'],'steps':len(rows)}))
assert result['passed']
