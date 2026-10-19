"""CPU deployment bindings only; actual GPU health/capacity belongs to root launch."""
import json,shutil
from pathlib import Path
from r78_contract import ROOT,read,sha,require
import preflight
def main():
    runtime=read(ROOT/'configs/runtime.json');require(ROOT==Path(runtime['remote_root']),'remote-only passive check')
    result={'preflight':preflight.check(),'core':{},'checkpoints':{},'GPU_started':False}
    for rel,digest in read(ROOT/'configs/parent_core_hashes.json').items():
        p=Path(runtime['core'])/rel;result['core'][rel]=sha(p)==digest
    require(all(result['core'].values()),'actual core changed')
    for key in ['python','core','models','dependencies','kj_nodes']:require(Path(runtime[key]).exists(),'missing dependency '+key)
    for rel,b in read(ROOT/'configs/expected_checkpoint_hashes.json').items():
        p=Path(runtime['models'])/rel;s=p.stat();result['checkpoints'][rel]={'resolved':str(p.resolve()),'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'expected_sha256':b['sha256'],'fresh_full_hash_computed':False}
    result['free_disk_bytes']=shutil.disk_usage(ROOT).free;require(result['free_disk_bytes']>=5*1024**3,'two-run storage allowance unavailable')
    require(read(ROOT/'configs/admission.json')['ready_for_launch'] is False,'passive deploy was already admitted')
    seal=read(ROOT/'deploy_manifest.json')
    for rel,b in seal['files'].items():require(sha(ROOT/rel)==b['sha256'],'deployed seal mismatch '+rel)
    result['sealed_files']=len(seal['files']);result['passed']=True
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
