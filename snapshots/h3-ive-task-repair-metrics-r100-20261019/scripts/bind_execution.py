"""Read-only binding to root's actual R100 STARTED service generation."""
import argparse,time
from common import *
from remote import read_paths

def bind(attempt):
 c=validate_static();require(attempt.replace('_','').replace('-','').isalnum(),'invalid attempt');root=Path(c['producer_remote'])
 names=[str(root/x) for x in ['deploy_manifest.json','configs/scientific_contract.json','configs/runtime.json',f'audit/{attempt}/STARTED.json','processes/service.json']];data=read_paths(names)
 for n,d in zip(names[:3],[c['producer_seal_sha256'],c['producer_contract_sha256'],c['producer_runtime_sha256']]):require(data[n]['sha256']==d,'producer static binding differs')
 started=data[names[3]]['value'];owner=data[names[4]]['value'];runtime=data[names[2]]['value']
 require(started.get('owner')==owner and started.get('controller') and started.get('unix'),'actual STARTED missing or generation differs')
 require(owner['gpu_uuid']==runtime['gpu_uuid'] and owner['port']==runtime['port'],'device/port mismatch')
 require(owner['identity']['uid']==runtime['uid'] and owner['identity']['start_ticks'] and str(root/'scripts/service_entry.py') in owner['identity']['cmdline'],'service identity differs')
 dest=ROOT/'audit/EXECUTION_BINDING.json'
 if dest.exists():
  old=read(dest);require(old['owner']==owner and old['attempt']==attempt and old['producer_seal_sha256']==c['producer_seal_sha256'],'different binding already exists');return bound(dest)
 save(dest,{'schema':'r100-native-media-execution-binding-v1','producer_seal_sha256':c['producer_seal_sha256'],'owner':owner,'attempt':attempt,'root_receipts':data,'bound_unix':time.time(),'scope':'Read-only CPU media; retrospective completed output permitted after exact service exits'})
 return bound(dest)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);a=p.parse_args();print(json.dumps(bind(a.attempt)))
