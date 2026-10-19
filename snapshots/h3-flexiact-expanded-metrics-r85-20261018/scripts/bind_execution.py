"""Bind only after root's real STARTED receipt; read-only remote operation."""
import argparse,time
from common import *
from remote import read_paths

def bind(attempt):
 c=validate_static();require(attempt.replace('_','').replace('-','').isalnum(),'invalid attempt')
 root=Path(c['producer_remote']);names=[str(root/'deploy_manifest.json'),str(root/'configs/scientific_contract.json'),str(root/'configs/runtime.json'),str(root/'audit'/attempt/'STARTED.json'),str(root/'processes/service.json')]
 data=read_paths(names);require(data[names[0]]['sha256']==c['producer_seal_sha256'],'producer seal changed');require(data[names[1]]['sha256']==c['producer_contract_sha256'],'producer science changed');require(data[names[2]]['sha256']==c['producer_runtime_sha256'],'runtime changed')
 started=data[names[3]]['value'];owner=data[names[4]]['value'];runtime=data[names[2]]['value']
 require(started.get('owner')==owner and started.get('controller') and started.get('unix'),'root STARTED owner/controller missing or changed')
 require(owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port'],'actual device/port mismatch')
 require(owner['identity']['start_ticks'] and str(root/'scripts/service_entry.py') in owner['identity']['cmdline'],'service identity incomplete')
 save(ROOT/'audit/EXECUTION_BINDING.json',{'schema':'r85-media-root-execution-binding-v1','producer_seal_sha256':c['producer_seal_sha256'],'producer_remote':str(root),'owner':owner,'attempt':attempt,'root_receipts':data,'bound_unix':time.time(),'scope':'CPU media only; permits retrospective consumption after exact service exits'})
 return bound(ROOT/'audit/EXECUTION_BINDING.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);a=p.parse_args();print(json.dumps(bind(a.attempt)))
