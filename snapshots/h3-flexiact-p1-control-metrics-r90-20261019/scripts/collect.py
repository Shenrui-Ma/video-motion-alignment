"""Single explicit read-only intake after root's output gate. Never submits or verifies producer."""
import argparse,time
from common import *
from remote import read_paths,fetch

def names(attempt):
 c=config();r=Path(c['producer_remote']);run=c['run_id']
 return {'seal':r/'deploy_manifest.json','runtime':r/'configs/runtime.json','science':r/'configs/scientific_contract.json','complete':r/'audit'/attempt/'COMPLETE.json','started':r/'audit'/attempt/'STARTED.json','exit':r/'audit'/attempt/'ROOT_EXIT_RECEIPT.json','owner':r/'processes/service.json','gate':r/'analysis/postrun/NATIVE_RUNTIME_GATE.json','job':r/'logs'/(run+'_job.json'),'history':r/'logs'/(run+'_history.json'),'graph':r/'configs/graphs'/(run+'.json')}

def snapshot(attempt):
 c=validate_static();require(attempt==c['expected_attempt'],'unregistered root attempt; preserve this consumer and rebind explicitly')
 paths=names(attempt);data=read_paths([str(x) for x in paths.values()],missing_ok=True);rows={k:data[str(p)] for k,p in paths.items()}
 if any(rows[k] is None for k in ('started','exit','gate','complete')):return {'status':'PENDING_ACTUAL_GATE_OR_ROOT_EXIT'}
 for k,key in [('seal','producer_seal_sha256'),('runtime','producer_runtime_sha256'),('science','producer_contract_sha256'),('graph','graph_sha256')]:require(rows[k] and rows[k]['sha256']==c[key],'producer '+k+' changed')
 owner=rows['owner']['value'];rt=rows['runtime']['value'];started=rows['started']['value'];exit_record=rows['exit']['value']
 require(started['owner']==owner and started.get('controller') and started.get('unix'),'root STARTED owner/controller changed')
 require(owner['gpu_uuid']==rt['gpu_uuid'] and owner['port']==rt['port'] and owner['identity']['uid']==rt['uid'] and owner['identity']['start_ticks'] and str(Path(c['producer_remote'])/'scripts/service_entry.py') in owner['identity']['cmdline'],'actual service binding incomplete')
 require(exit_record['passed'] is True and exit_record['owner']==owner and exit_record['process_absent'] is True and exit_record['CUDA_allocation_absent'] is True,'root exact exit pending/different')
 require(rows['complete']['value'].get('passed') is True and rows['complete']['value'].get('GPU_released') is True and rows['complete']['value'].get('runtime_gate_sha256')==rows['gate']['sha256'],'actual COMPLETE gate binding differs')
 verify_gate(rows['gate']['value']);require(rows['job'] and rows['history'],'actual successful records missing')
 return {'status':'READY','rows':rows,'owner':owner,'paths':paths}

def collect(attempt):
 c=validate_static();dest=ROOT/'incoming'
 if dest.exists():verify_intake();return bound(dest/'COLLECTION.json')
 s=snapshot(attempt)
 if s['status']!='READY':return s
 rows=s['rows'];binding={'schema':'r90-media-actual-attempt-binding-v1','attempt':attempt,'owner':s['owner'],'producer_seal_sha256':c['producer_seal_sha256'],'root_started':rows['started'],'root_exit':rows['exit']}
 bp=ROOT/'audit/EXECUTION_BINDING.json'
 if bp.exists():require(read(bp)==binding,'execution binding conflict')
 else:save(bp,binding)
 staging=ROOT/'audit/collection_staging'/str(time.time_ns());staging.mkdir(parents=True)
 for role,name in [('complete','COMPLETE.json'),('gate','NATIVE_RUNTIME_GATE.json'),('history','history.json'),('job','job.json'),('graph','graph.json'),('owner','service.json'),('started','STARTED.json'),('exit','ROOT_EXIT_RECEIPT.json')]:
  fetch(s['paths'][role],staging/name);require(sha(staging/name)==rows[role]['sha256'],'small evidence changed during transfer: '+role)
 g=rows['gate']['value'];fetch(safe_output(g['video']['file']),staging/'native.mp4');verify_small_evidence(staging,s['owner'],g)
 again=snapshot(attempt);require(again['status']=='READY' and all(again['rows'][k]['sha256']==v['sha256'] for k,v in rows.items()),'evidence changed during transfer')
 save(staging/'COLLECTION.json',{'schema':'r90-one-time-media-intake-v1','run_id':c['run_id'],'execution_binding_sha256':sha(bp),'files':{p.name:sha(p) for p in staging.iterdir() if p.is_file()},'valid_frames':147,'fps':24,'GPU_started':False})
 staging.rename(dest);return bound(dest/'COLLECTION.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);a=p.parse_args();print(json.dumps(collect(a.attempt)))
