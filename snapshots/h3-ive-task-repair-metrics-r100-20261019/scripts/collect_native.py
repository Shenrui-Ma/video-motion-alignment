"""One-shot Native-only collection; never invokes the producer verifier."""
import argparse,time
from common import *
from remote import read_paths,fetch

def status(source):
 c=validate_static();binding=read(ROOT/'audit/EXECUTION_BINDING.json');root=Path(c['producer_remote']);gate=root/'analysis/postrun'/source/'NATIVE_RUNTIME_GATE.json'
 names=[str(root/'deploy_manifest.json'),str(root/'configs/runtime.json'),str(root/'processes/service.json'),str(gate),str(gate.with_name('NATIVE_RUNTIME_GATE_FAILURE.json'))];data=read_paths(names,missing_ok=True)
 for n,d in zip(names[:2],[c['producer_seal_sha256'],c['producer_runtime_sha256']]):require(data[n] and data[n]['sha256']==d,'producer seal/runtime changed')
 require(data[names[2]] and data[names[2]]['value']==binding['owner'],'producer service generation changed; explicit recovery required')
 if data[str(gate)] is None:
  return {'source_id':source,'status':'FAILED_GATE' if data[names[4]] else 'PENDING_GATE','failure':data[names[4]]}
 g=data[str(gate)]['value'];verify_gate(g,source,binding['owner']);return {'source_id':source,'status':'PASSED_GATE','gate':data[str(gate)],'binding':binding}

def collect(source):
 dest=ROOT/'incoming'/source
 if dest.exists():verify_intake(source);return bound(dest/'COLLECTION.json')
 s=status(source);require(s['status']=='PASSED_GATE','actual Native gate not ready');g=s['gate']['value'];root=Path(config()['producer_remote']);p=info(source);r=g['runs']['native']
 staging=ROOT/'audit/collection_staging'/f'{source}_{time.time_ns()}';staging.mkdir(parents=True)
 fetch(root/'analysis/postrun'/source/'NATIVE_RUNTIME_GATE.json',staging/'NATIVE_RUNTIME_GATE.json');require(sha(staging/'NATIVE_RUNTIME_GATE.json')==s['gate']['sha256'],'gate changed')
 fetch(safe_path(r['video']['file'],'output'),staging/'native.mp4');require(sha(staging/'native.mp4')==r['video']['sha256'],'actual video changed')
 for label,rel,digest in [('job',f'logs/{p["run_id"]}_job.json',r['job_sha256']),('history',f'logs/{p["run_id"]}_history.json',r['history_sha256']),('router',f'audit/router/{p["run_id"]}.json',r['router_file_sha256']),('graph',f'configs/graphs/{p["run_id"]}.json',p['graph_sha256'])]:
  target=staging/f'native_{label}.json';fetch(root/rel,target);require(sha(target)==digest,label+' changed')
 # Small originals only; tensor payloads remain remote and were checked by the actual producer gate.
 extra={rel:d for rel,d in r['binding_artifacts'].items() if rel.endswith('.json')}
 for i,(rel,digest) in enumerate(sorted(extra.items())):
  target=staging/f'binding_{i:02d}.json';fetch(root/rel,target);require(sha(target)==digest,'binding JSON changed')
 source_receipts=read_paths([str(root/p[k]['file']) for k in ('provenance',)])
 for k in ('source','provenance'):require(sha(ROOT/p[k]['file'])==p[k]['sha256'],'local source changed')
 require(source_receipts[str(root/p['provenance']['file'])]['sha256']==p['provenance']['sha256'],'remote provenance differs')
 # Read prepared source bytes only once for its SHA, without transferring a duplicate.
 from remote import verify_source_bytes
 verify_source_bytes(root/p['source']['file'],p['source']['sha256'])
 verify_small_evidence(staging,source,s['binding']['owner'],g)
 again=status(source);require(again['status']=='PASSED_GATE' and again['gate']['sha256']==s['gate']['sha256'],'gate/service changed during reads')
 save(staging/'COLLECTION.json',{'schema':'r100-native-media-intake-v1','source_id':source,'execution_binding_sha256':sha(ROOT/'audit/EXECUTION_BINDING.json'),'gate_sha256':s['gate']['sha256'],'files':{x.name:sha(x) for x in staging.iterdir() if x.is_file()},'extra_binding_jsons':extra,'full_output_frames':p['geometry']['frames'],'display_valid_frames':p['valid_frames'],'display_fps':24,'crop_xywh':p['crop_xywh'],'GPU_started':False,'mode':'Native-only'})
 dest.parent.mkdir(exist_ok=True);staging.rename(dest);return bound(dest/'COLLECTION.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',choices=SOURCES,required=True);p.add_argument('--status',action='store_true');a=p.parse_args();print(json.dumps(status(a.source) if a.status else collect(a.source)))
