"""Exact current actual-noise verification; cross-host historical metadata only."""
from pathlib import Path
from r86_contract import read,sha,require

def compare_clean_inputs(root,case):
 import torch
 from H3X0Readout.core import tensor_signature
 root=Path(root);spec=read(root/'configs/ACTUAL_NOISE.json');n=read(root/'audit'/(case['run_id']+'_noise.json'));p=Path(n['cache_file'])
 require(p==root/'audit/r113_short_0252_seed2026101703_noise.pt' and sha(p)==spec['source_sha256'],'current exact noise cache differs')
 payload=torch.load(p,map_location='cpu',weights_only=True);sigs=[{k:v for k,v in tensor_signature(x).items() if k in ('shape','dtype','sha256')} for x in payload['tensors']]
 require(payload['signature']==n['signature']==spec['signature'] and sigs==n['actual_noise_streams']==spec['actual_noise_streams'],'actual noise payload/signatures differ')
 old=read(root/case['parent_conditioning']);current=read(root/'audit'/(case['run_id']+'_conditioning.json'));require(old['prompt']==current['prompt']==case['prompt'],'prompt mismatch')
 return {'actual_initial_AV_noise_exact':True,'noise_file_sha256':sha(p),'cross_host_historical_equality_required':False}

def compare_prefix(case,inventory,old,index,current):
 from H3X0Readout.core import tensor_signature
 signatures=[tensor_signature(current[k]) for k in ('video','audio')];historical=[old['video'],old['audio']]
 return {'physical_index':index,'current':signatures,'historical':historical,'signature_equal':signatures==historical,'cross_host_equality_required':False}

def checked_parent(*args):raise RuntimeError('historical tensors are deliberately not copied for host comparison')
