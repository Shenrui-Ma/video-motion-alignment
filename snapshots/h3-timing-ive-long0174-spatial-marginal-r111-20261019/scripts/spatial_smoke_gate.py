"""Require current-environment actual geometry CUDA evidence before model startup."""
from pathlib import Path
from r111_contract import ROOT,read,sha,require

def verify(root=ROOT):
 root=Path(root);r=read(root/'audit/GPU_SMOKE_RESULT.json');release=read(root/'audit/GPU_SMOKE_RELEASE.json')
 require(r.get('schema')=='r111-spatial-marginal-smoke-v1' and r.get('passed') is True,'spatial GPU smoke failed')
 require(r['torch']=='2.11.0+cu130' and r['cuda']=='13.0','smoke runtime differs')
 require(r['core_sha256']==sha(root/'extensions/H3TemporalRouter/core.py'),'GPU core differs')
 require(r['script_sha256']==sha(root/'scripts/gpu_spatial_marginal_smoke.py'),'GPU smoke script differs')
 require(len(r['cases'])==3 and all(x['passed'] is True and all(x['checks'].values()) for x in r['cases']),'smoke cases incomplete')
 actual=r['cases'][2];require(actual['actual_shape'] and actual['shape']==[1,56,96281,128],'smoke packed geometry differs')
 require(actual['plan']=={'reference_video_segment':[7113,51434],'query_interval_half_open':[51960,92509],'latent_interval_half_open':[0,43],'frame_rows':943,'seq_len':96281},'smoke current layout differs')
 require(release['passed'] and release['process_absent'] and release['CUDA_allocation_absent'] and release['exit_code']==0,'smoke process not released')
 require(release['result_sha256']==sha(root/'audit/GPU_SMOKE_RESULT.json') and release['owner']['uid']==1004,'smoke release binding differs')
 require(release['gpu_uuid']==read(root/'configs/runtime.json')['gpu_uuid'],'smoke ran on different GPU')
 return {'passed':True,'result_sha256':sha(root/'audit/GPU_SMOKE_RESULT.json'),'release_sha256':sha(root/'audit/GPU_SMOKE_RELEASE.json')}
