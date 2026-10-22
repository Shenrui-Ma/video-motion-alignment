"""Read only root-produced completion gate; no verifier or policy execution."""
import argparse,time
from common import *
from remote import read_paths,fetch,fetch_json_batch
def status():
 cfg=validate_static();b=read(ROOT/'audit/EXECUTION_BINDING.json');root=Path(cfg['producer_remote'])
 names=[str(root/'deploy_manifest.json'),str(root/'processes/service.json'),str(root/'analysis/postrun/ONLINE_RUNTIME_GATE.json'),str(root/'audit'/b['attempt']/'FAILURE.json')];data=read_paths(names,missing_ok=True)
 require(data[names[0]] and data[names[0]]['sha256']==b['producer_seal_sha256']==cfg['producer_seal_sha256'],'producer seal changed')
 require(data[names[1]] and data[names[1]]['value']==b['owner'],'service generation changed; explicit recovery binding required')
 if data[names[2]] is None:
  if data[names[3]] is not None:return {'status':'FAILED_ATTEMPT','failure':data[names[3]]}
  return {'status':'PENDING_COMPLETE_GATE','GPU_validation':'PENDING'}
 g=data[names[2]]['value'];verify_gate(g,b['owner']);return {'status':'PASSED_GATE','gate':data[names[2]],'binding':b}

def collect():
 s=status();require(s['status']=='PASSED_GATE','actual online gate pending');g=s['gate']['value'];cfg=config();root=Path(cfg['producer_remote']);dest=ROOT/'incoming';require(not dest.exists(),'existing collection retained')
 staging=ROOT/'audit/collection_staging'/str(time.time_ns());staging.mkdir(parents=True)
 files={'ONLINE_RUNTIME_GATE.json':root/'analysis/postrun/ONLINE_RUNTIME_GATE.json','counterfactual.json':root/'audit/counterfactual'/(RUN+'.json'),'job.json':root/'logs'/(RUN+'_job.json'),'history.json':root/'logs'/(RUN+'_history.json'),'graph.json':root/'configs/graphs'/(RUN+'.json'),'ACTUAL_SUCCESS.json':root/'audit'/s['binding']['attempt']/'ACTUAL_SUCCESS.json','ROOT_EXIT_REFERENCE.json':root/'analysis/postrun/ROOT_EXIT_REFERENCE.json','online.mp4':safe_remote(g['video']['file'],'output')}
 for name,path in files.items():fetch(path,staging/name)
 require(sha(staging/'ONLINE_RUNTIME_GATE.json')==s['gate']['sha256'] and sha(staging/'online.mp4')==g['video']['sha256'],'gate/video changed during transfer')
 require(sha(staging/'graph.json')==cfg['graph_sha256'],'actual graph changed')
 job=read(staging/'job.json');success=read(staging/'ACTUAL_SUCCESS.json');owner=s['binding']['owner']
 require(job['status']=='success' and job['name']==RUN and job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'] and job['graph_sha256']==cfg['graph_sha256'],'actual submitted job differs')
 require(success['run_id']==RUN and success['service']==owner and success['history_sha256']==sha(staging/'history.json'),'actual success/history binding differs')
 exitref=read(staging/'ROOT_EXIT_REFERENCE.json');fetch(safe_remote(exitref['file'],'audit'),staging/'ROOT_EXIT_RECEIPT.json');require(sha(staging/'ROOT_EXIT_RECEIPT.json')==exitref['sha256'],'exact root exit receipt changed')
 audit=read(staging/'counterfactual.json');case=verify_gate(g,owner);decisions=read_decisions(audit,case)
 transactions=[]
 for m in audit['counterfactual']['measurements']:
  i=m['physical_index']
  for kind in ['request','response']:transactions.append({'remote':str(safe_remote(m[kind+'_file'],'audit')),'local':staging/f'step{i:03d}_{kind}.json','sha256':m[kind+'_sha256']})
 fetch_json_batch(transactions);observers=[]
 for m in audit['counterfactual']['measurements']:
  i=m['physical_index'];response=read(staging/f'step{i:03d}_response.json')
  observers.append({'remote':str(safe_remote(response['observer']['file'],'audit')),'local':staging/f'step{i:03d}_observer.json','sha256':response['observer']['sha256']})
 fetch_json_batch(observers)
 for m in audit['counterfactual']['measurements']:require(read(staging/f'step{m["physical_index"]:03d}_observer.json')==m['observer'],'observer differs from actual audit')
 again=status();require(again['status']=='PASSED_GATE' and again['gate']['sha256']==s['gate']['sha256'],'gate/generation changed during transfer')
 save(staging/'ACTUAL_DECISIONS.json',decisions)
 save(staging/'COLLECTION.json',{'schema':'r86-actual-online-media-intake-v1','execution_binding_sha256':sha(ROOT/'audit/EXECUTION_BINDING.json'),'gate_sha256':s['gate']['sha256'],'files':{p.name:sha(p) for p in staging.iterdir() if p.is_file()},'historical_parent_gate_sha256':cfg['parent_gate_sha256'],'full_frames':107,'valid_frames':98,'fps':24,'scope':'Actual GPU completion integrity confirmed by root gate; scientific effect pending review','GPU_started_by_consumer':False})
 staging.rename(dest);return bound(dest/'COLLECTION.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--status',action='store_true');a=p.parse_args();print(json.dumps(status() if a.status else collect()))
