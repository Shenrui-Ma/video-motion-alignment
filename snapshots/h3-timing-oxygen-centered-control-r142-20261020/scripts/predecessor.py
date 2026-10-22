"""Root binds the actual successful R141b generation; no implicit PID reuse."""
from pathlib import Path
from r86_contract import ROOT,read,sha,require

def same_generation(saved, current):
 # Linux may reuse the numeric PID immediately after the recorded service exits.
 # UID and start time identify its lifetime even if that process executes a new command.
 return current is not None and current['uid']==saved['uid'] and str(current['start_ticks'])==str(saved['start_ticks'])

def check(root=ROOT):
 import service
 root=Path(root);b=read(root/'audit/PREDECESSOR_RELEASE_BINDING.json')
 require(b.get('root_reviewed') is True and b.get('host')=='H3_SERVER_A','actual predecessor binding pending')
 old=Path(b['remote_root']);require(old.parent==root.parent and old!=root,'predecessor root scope')
 require(sha(old/'deploy_manifest.json')==b['producer_seal_sha256'],'predecessor seal changed')
 attempt=b['attempt'];require(attempt.replace('_','').isalnum(),'unsafe predecessor attempt')
 d=old/'audit'/attempt;ex=read(d/'ROOT_EXIT_RECEIPT.json');done=read(d/'COMPLETE.json');owner=read(old/'processes/service.json')
 require(sha(d/'ROOT_EXIT_RECEIPT.json')==b['ROOT_EXIT_RECEIPT_sha256'] and sha(d/'COMPLETE.json')==b['COMPLETE_sha256'],'predecessor release/completion differs')
 require(ex['passed'] and ex['owner']==owner and ex['process_absent'] and ex['CUDA_allocation_absent'],'predecessor exact release failed')
 require(done['passed'] and done['GPU_released'] and done['all_sources_reviewed'] and done['remaining_sources']==[],'predecessor screening incomplete')
 current=service.current_identity(owner['pid'])
 require(owner['identity']['uid']==1016 and not same_generation(owner['identity'],current),'predecessor owner generation still live')
 started=read(d/'STARTED.json');require(started['owner']==owner,'predecessor started owner differs')
 controller=started['controller']
 require(not same_generation(controller['identity'],service.current_identity(controller['pid'])),'predecessor queue controller generation still live')
 reused=current is not None and not same_generation(owner['identity'],current)
 require(reused or not any(x['pid']==owner['pid'] for x in service.compute_processes()),'predecessor CUDA remains')
 return {'passed':True,'binding_sha256':sha(root/'audit/PREDECESSOR_RELEASE_BINDING.json'),'owner':owner,'actual_attempt':attempt}
