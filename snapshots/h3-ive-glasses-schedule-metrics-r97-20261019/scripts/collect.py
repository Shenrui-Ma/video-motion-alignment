"""One-shot read-only collection after root's actual CONTROL gate."""
import argparse,time
from common import *
from remote import read_paths,fetch

def status():
 c=validate_static();binding=read(ROOT/'audit/EXECUTION_BINDING.json');root=Path(c['producer_remote']);gate=root/'analysis/postrun/CONTROL_RUNTIME_GATE.json'
 names=[str(root/'deploy_manifest.json'),str(root/'configs/runtime.json'),str(root/'processes/service.json'),str(gate),str(gate.with_name('CONTROL_RUNTIME_GATE_FAILURE.json'))]
 data=read_paths(names,missing_ok=True)
 for n,d in zip(names[:2],[c['producer_seal_sha256'],c['producer_runtime_sha256']]):require(data[n] and data[n]['sha256']==d,'producer seal/runtime changed')
 require(data[names[2]] and data[names[2]]['value']==binding['owner'],'producer generation differs')
 if data[str(gate)] is None:return {'status':'FAILED_GATE' if data[names[4]] else 'PENDING_GATE','failure':data[names[4]]}
 verify_gate(data[str(gate)]['value']);return {'status':'PASSED_GATE','gate':data[str(gate)],'binding':binding}

def collect():
 dest=ROOT/'incoming'
 if dest.exists():verify_intake();return bound(dest/'COLLECTION.json')
 s=status();require(s['status']=='PASSED_GATE','control gate not ready');g=s['gate']['value'];c=config();root=Path(c['producer_remote']);run=c['run_id']
 staging=ROOT/'audit/collection_staging'/str(time.time_ns());staging.mkdir(parents=True)
 fetch(root/'analysis/postrun/CONTROL_RUNTIME_GATE.json',staging/'CONTROL_RUNTIME_GATE.json');require(sha(staging/'CONTROL_RUNTIME_GATE.json')==s['gate']['sha256'],'gate changed during collection')
 fetch(safe_path(g['video']['file'],'output'),staging/'extended.mp4')
 records={'job':f'logs/{run}_job.json','history':f'logs/{run}_history.json','graph':f'configs/graphs/{run}.json','router':f'audit/router/{run}.json','conditioning':f'audit/{run}_conditioning.json','noise':f'audit/{run}_noise.json'}
 before=read_paths([str(root/x) for x in records.values()])
 for label,rel in records.items():
  target=staging/f'extended_{label}.json';fetch(root/rel,target);require(sha(target)==before[str(root/rel)]['sha256'],'evidence changed during collection: '+label)
 verify_small(staging,s['binding']['owner'],g)
 again=status();require(again['status']=='PASSED_GATE' and again['gate']['sha256']==s['gate']['sha256'],'gate changed after collection')
 after=read_paths([str(root/x) for x in records.values()]);require({k:v['sha256'] for k,v in before.items()}=={k:v['sha256'] for k,v in after.items()},'small evidence changed')
 save(staging/'COLLECTION.json',{'schema':'r97-control-media-intake-v1','execution_binding_sha256':sha(ROOT/'audit/EXECUTION_BINDING.json'),'gate_sha256':s['gate']['sha256'],'files':{p.name:sha(p) for p in staging.iterdir() if p.is_file()},'remote_small_records':records,'old_media':c['old_media'],'valid_frames':105,'total_frames':107,'fps':24,'crop_xywh':c['crop_xywh'],'GPU_started':False})
 staging.rename(dest);return bound(dest/'COLLECTION.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--status',action='store_true');a=p.parse_args();print(json.dumps(status() if a.status else collect()))
