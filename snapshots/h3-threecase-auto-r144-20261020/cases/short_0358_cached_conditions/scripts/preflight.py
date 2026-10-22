"""CPU checks and hard gates for exact materialized inputs, runtime and root admission."""
from pathlib import Path
from r86_contract import ROOT,RUN,registry,validate_job,read,sha,require

def check(root=ROOT,live=False):
 root=Path(root);jobs,order=registry(root);validate_job(RUN,root)
 provenance=read(root/'audit/INHERITANCE.json')
 for rel,row in provenance['unchanged_numerics'].items():require(sha(root/rel)==row['sha256'],'numeric source changed: '+rel)
 require(read(root/'configs/runtime.json')['memory_mode']=='normal' and read(root/'configs/runtime.json')['reserve_vram']==8,'main profile differs')
 if live:
  proof=read(root/'audit/CACHED_CONDITION_CPU_PROOF.json');require(proof['passed'] and proof['positive_tree_equal'] and proof['target_tree_equal'] and proof['cache_manifest_sha256']==sha(root/'configs/CONDITION_CACHE.json'),'exact cache CPU proof pending')
  p=read(root/'configs/protocol.json');c=p['cases'][0]
  require(c['source_pose_sha256'] is not None and p['person_selection']['selected_bbox_center_x_fraction'] is not None,'source pose/identity binding pending')
  require(sha(root/c['source_pose_path'])==c['source_pose_sha256'],'source pose changed')
  runtime=read(root/'configs/runtime.json');require(root.resolve()==Path(runtime['remote_root']),'exact remote root required')
  for rel,row in read(root/'deploy_manifest.json')['files'].items():require(sha(root/rel)==row['sha256'],'producer seal differs: '+rel)
  smoke=read(root/'audit/RUNTIME_IMPORT_SMOKE.json');require(smoke.get('passed') is True and smoke['runtime_sha256']==sha(root/'configs/runtime.json') and smoke['cuda_initialized'] is False,'actual CPU runtime smoke pending')
  require(smoke['actual_Comfy_namespace'] and smoke['extensions_sys_path_absent'] and smoke['cached_module_sha256']==sha(root/'extensions/H3CachedCondition/__init__.py'),'unmasked actual custom-node namespace proof pending')
  from observer_import import t
  t.bindings(external=True);t.admission_document(approved=True)
  from execution_gate import approval
  approval(root)
  for rel,digest in read(root/'configs/parent_core_hashes.json').items():require(sha(Path(runtime['core'])/rel)==digest,'Comfy core differs')
  require(__import__('shutil').disk_usage(root).free>=8*1024**3,'insufficient owned-volume storage for endpoint/observation records')
 return {'passed':True,'run_id':RUN,'online_observations':20,'Euler_updates':20,'NFE':'20+actual_ON','spatial_selection':read(root/'configs/protocol.json')['person_selection'],'actual_GPU_launch':False,'live_preconditions':live}

if __name__=='__main__':
 import argparse,json
 p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');a=p.parse_args();print(json.dumps(check(live=a.live),indent=2))
