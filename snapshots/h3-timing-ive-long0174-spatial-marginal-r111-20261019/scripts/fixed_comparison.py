"""Read actual R107 fixed records; no model or CUDA operations."""
from pathlib import Path
from r111_contract import ROOT,read,sha,require

def verify(root=ROOT,require_released=False):
 root=Path(root);b=read(root/'design/R107_FIXED_BINDING.json');old=Path(b['root'])
 gp=old/'analysis/postrun/long_0174/PAIR_RUNTIME_GATE.json';g=read(gp)
 require(sha(gp)==b['gate_sha256'] and g==read(root/'design/R107_PAIR_RUNTIME_GATE.json') and g['passed'] is True and all(g['checks'].values()),'actual R107 paired gate changed')
 require(sha(old/'deploy_manifest.json')==b['producer_seal_sha256'],'actual R107 seal changed')
 run=g['runs']['forced'];require(run['run_id']=='r107_long_0174_seed2026101701_forced' and run['routed_blocks']==450 and run['NFE']==20,'actual fixed count differs')
 require(sha(Path(run['video']['file']))==b['video_sha256']==run['video']['sha256'],'actual fixed video changed')
 require(sha(old/'configs/graphs'/ (run['run_id']+'.json'))==b['graph_sha256'],'actual fixed graph changed')
 require(sha(old/'extensions/H3TemporalRouter/core.py')==b['core_sha256']==sha(root/'design/R107_ROUTER_CORE.py'),'actual fixed core changed')
 current=read(root/'configs/runtime.json');prior=g['runtime_profile']
 require(all(current[k]==prior[k] for k in ('host','core','python','dependencies','models','kj_nodes','reserve_vram','memory_mode','gpu_uuid')),'fixed runtime profile differs')
 checks={'actual_gate':True,'actual_video':True,'actual_core':True,'same_host_device_numerics':True}
 if require_released:
  import service
  owner=read(old/'processes/service.json');require(owner==g['service_owner'],'fixed actual service changed')
  cleanup=read(old/'processes/cleanup.json');exit=read(old/'audit/root_long0174_guidance_attempt2/ROOT_EXIT_RECEIPT.json')
  require(exit['passed'] and exit['owner']==owner and exit['process_absent'] and exit['CUDA_allocation_absent'],'fixed exit absent')
  require(cleanup['pid']==owner['pid'] and cleanup['process_absent'] and cleanup['own_compute_absent'],'fixed cleanup absent')
  require(service.current_identity(owner['pid']) is None and not any(x['pid']==owner['pid'] for x in service.compute_processes()),'fixed service/CUDA remains')
  checks['fixed_exact_release']=True
 return {'passed':True,'checks':checks,'binding':b}
