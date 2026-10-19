"""One-shot CPU intake of a completed pair. Producer verifier is root-owned."""
import argparse,time
from common import *
from paired import verify_pair_gate,verify_pair_intake,require_same_native
from remote import read_paths,fetch,verify_source_bytes

def status(source):
 c=validate_static();binding=read(ROOT/'audit/EXECUTION_BINDING.json');root=Path(c['producer_remote']);gate=root/'analysis/postrun'/source/'PAIR_RUNTIME_GATE.json'
 names=[str(root/'deploy_manifest.json'),str(root/'configs/runtime.json'),str(root/'processes/service.json'),str(gate),str(gate.with_name('PAIR_RUNTIME_GATE_FAILURE.json'))];data=read_paths(names,missing_ok=True)
 for name,digest in zip(names[:2],[c['producer_seal_sha256'],c['producer_runtime_sha256']]):require(data[name] and data[name]['sha256']==digest,'producer seal/runtime changed')
 require(data[names[2]] and data[names[2]]['value']==binding['owner'],'producer service generation changed; explicit recovery required')
 if data[str(gate)] is None:return {'source_id':source,'status':'FAILED_GATE' if data[names[4]] else 'PENDING_GATE','failure':data[names[4]]}
 g=data[str(gate)]['value'];verify_pair_gate(g,source,binding['owner']);require_same_native(source,g)
 return {'source_id':source,'status':'PASSED_GATE','gate':data[str(gate)],'binding':binding}

def collect(source):
 dest=ROOT/'incoming_pairs'/source
 if dest.exists():verify_pair_intake(source);return bound(dest/'COLLECTION.json')
 state=status(source);require(state['status']=='PASSED_GATE','actual paired gate not ready');g=state['gate']['value'];root=Path(config()['producer_remote']);p=info(source)
 staging=ROOT/'audit/pair_collection_staging'/f'{source}_{time.time_ns()}';staging.mkdir(parents=True)
 fetch(root/'analysis/postrun'/source/'PAIR_RUNTIME_GATE.json',staging/'PAIR_RUNTIME_GATE.json');require(sha(staging/'PAIR_RUNTIME_GATE.json')==state['gate']['sha256'],'paired gate changed')
 extra={}
 for mode in ('native','forced'):
  r=g['runs'][mode];run=r['run_id'];graph_sha=p['graph_sha256'] if mode=='native' else p['forced_graph_sha256']
  fetch(safe_path(r['video']['file'],'output'),staging/f'{mode}.mp4');require(sha(staging/f'{mode}.mp4')==r['video']['sha256'],'actual video changed')
  for label,rel,digest in [('job',f'logs/{run}_job.json',r['job_sha256']),('history',f'logs/{run}_history.json',r['history_sha256']),('router',f'audit/router/{run}.json',r['router_file_sha256']),('graph',f'configs/graphs/{run}.json',graph_sha)]:
   target=staging/f'{mode}_{label}.json';fetch(root/rel,target);require(sha(target)==digest,label+' changed')
  for rel,digest in r['binding_artifacts'].items():
   if rel.endswith('.json'):
    require(rel not in extra or extra[rel]==digest,'shared actual evidence differs');extra[rel]=digest
  verify_small_evidence(staging,source,state['binding']['owner'],g,mode)
 for i,(rel,digest) in enumerate(sorted(extra.items())):
  target=staging/f'binding_{i:02d}.json';fetch(root/rel,target);require(sha(target)==digest,'binding JSON changed')
 remote_provenance=read_paths([str(root/p['provenance']['file'])])
 for k in ('source','provenance'):require(sha(ROOT/p[k]['file'])==p[k]['sha256'],'local source changed')
 require(remote_provenance[str(root/p['provenance']['file'])]['sha256']==p['provenance']['sha256'],'remote provenance differs')
 verify_source_bytes(root/p['source']['file'],p['source']['sha256'])
 again=status(source);require(again['status']=='PASSED_GATE' and again['gate']['sha256']==state['gate']['sha256'],'gate/service changed during reads')
 save(staging/'COLLECTION.json',{'schema':'r119-paired-media-intake-v1','source_id':source,'execution_binding_sha256':sha(ROOT/'audit/EXECUTION_BINDING.json'),'gate_sha256':state['gate']['sha256'],'files':{x.name:sha(x) for x in staging.iterdir() if x.is_file()},'extra_binding_jsons':extra,'full_output_frames':p['geometry']['frames'],'display_valid_frames':p['valid_frames'],'display_fps':24,'crop_xywh':p['crop_xywh'],'GPU_started':False,'mode':'Native+fixed guidance'})
 dest.parent.mkdir(exist_ok=True);staging.rename(dest);return bound(dest/'COLLECTION.json')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',choices=SOURCES,required=True);p.add_argument('--status',action='store_true');a=p.parse_args();print(json.dumps(status(a.source) if a.status else collect(a.source)))
