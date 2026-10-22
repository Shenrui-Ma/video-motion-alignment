"""Bind actual R86 root STARTED, using its service/root_controller schema."""
import argparse,time
from common import *
from remote import read_paths
def bind(attempt):
 cfg=validate_static();require(attempt.startswith('root_') and attempt.replace('_','').isalnum(),'invalid actual attempt');root=Path(cfg['producer_remote'])
 names=[str(root/'deploy_manifest.json'),str(root/'configs/scientific_contract.json'),str(root/'configs/runtime.json'),str(root/'configs/protocol.json'),str(root/'audit'/attempt/'STARTED.json'),str(root/'processes/service.json')];data=read_paths(names)
 for i,key in [(0,'producer_seal_sha256'),(1,'producer_contract_sha256'),(2,'producer_runtime_sha256'),(3,'protocol_sha256')]:require(data[names[i]]['sha256']==cfg[key],'actual producer binding changed: '+key)
 started=data[names[4]]['value'];owner=data[names[5]]['value'];runtime=data[names[2]]['value']
 require(started.get('service')==owner and started.get('root_controller') and started.get('ready') and started['protocol_sha256']==cfg['protocol_sha256'],'R86 actual STARTED owner/controller/protocol differs')
 require(owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port'],'R86 actual GPU/port differs');identity=owner['identity']
 require(type(identity['uid']) is int and identity['start_ticks'] and str(root) in identity['cmdline'] and 'main.py' in identity['cmdline'],'exact main service identity incomplete')
 save(ROOT/'audit/EXECUTION_BINDING.json',{'schema':'r86-media-actual-root-binding-v1','attempt':attempt,'owner':owner,'producer_seal_sha256':cfg['producer_seal_sha256'],'root_receipts':data,'bound_unix':time.time(),'scope':'CPU consumer only; allows result collection after exact main/observer release'})
 return bound(ROOT/'audit/EXECUTION_BINDING.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);a=p.parse_args();print(json.dumps(bind(a.attempt)))
