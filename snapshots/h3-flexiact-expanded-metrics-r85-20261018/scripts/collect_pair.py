"""Copy verified 158-frame outputs; no producer verifier is invoked."""
import argparse,shutil,time
from common import *
from remote import read_paths,fetch

def status(pair):
 c=validate_static();binding=read(ROOT/'audit/EXECUTION_BINDING.json');root=Path(c['producer_remote']);names=[str(root/'deploy_manifest.json'),str(root/'processes/service.json'),str(root/'analysis/postrun'/pair/'PAIR_RUNTIME_GATE.json')]
 data=read_paths(names,missing_ok=True)
 require(data[names[0]] and data[names[0]]['sha256']==binding['producer_seal_sha256']==c['producer_seal_sha256'],'producer seal changed')
 require(data[names[1]] and data[names[1]]['value']==binding['owner'],'producer service generation changed; explicit recovery binding required')
 if data[names[2]] is None:return {'pair':pair,'status':'PENDING_GATE'}
 g=data[names[2]]['value']
 if g.get('passed') is not True:return {'pair':pair,'status':'FAILED_GATE','gate_sha256':data[names[2]]['sha256'],'checks':g.get('checks')}
 verify_gate(g,pair);return {'pair':pair,'status':'PASSED_GATE','gate':data[names[2]],'binding':binding}

def collect(pair):
 s=status(pair);require(s['status']=='PASSED_GATE','actual gate is not ready');g=s['gate']['value'];root=Path(config()['producer_remote']);dest=ROOT/'incoming'/pair
 require(not dest.exists(),'intake already exists; preserve previous attempt');staging=ROOT/'audit/collection_staging'/f'{pair}_{time.time_ns()}';staging.mkdir(parents=True)
 save(staging/'PAIR_RUNTIME_GATE.json',g)
 # Gate original bytes are fetched so its exact SHA remains the producer receipt.
 fetch(root/'analysis/postrun'/pair/'PAIR_RUNTIME_GATE.json',staging/'PAIR_RUNTIME_GATE.json');require(sha(staging/'PAIR_RUNTIME_GATE.json')==s['gate']['sha256'],'gate changed during intake')
 for arm in METHODS:
  row=g['runs'][arm];run=row['run_id'];video=safe_output(row['video']['file']);fetch(video,staging/(arm+'.mp4'));require(sha(staging/(arm+'.mp4'))==row['video']['sha256'],'actual video changed')
  for kind,p,digest in [('job',root/'logs'/f'{run}_job.json',row['job_sha256']),('history',root/'logs'/f'{run}_history.json',row['history_sha256']),('router',root/'audit/router'/f'{run}.json',row['router_file_sha256']),('graph',root/'configs/graphs'/f'{run}.json',pair_info(pair)['runs'][arm]['graph_sha256'])]:
   dst=staging/f'{arm}_{kind}.json';fetch(p,dst);require(sha(dst)==digest,kind+' evidence changed')
  verify_job(read(staging/f'{arm}_job.json'),arm,pair,s['binding']['owner'],g)
 for role in ['source','target','provenance']:
  source=ROOT/pair_info(pair)[role]['file'];require(sha(source)==pair_info(pair)[role]['sha256'],role+' input changed')
 # Confirm the same receipt and generation after reads, without requiring CUDA still alive.
 again=status(pair);require(again['status']=='PASSED_GATE' and again['gate']['sha256']==s['gate']['sha256'],'gate/generation changed during intake')
 save(staging/'COLLECTION.json',{'schema':'r85-media-intake-v1','pair':pair,'execution_binding_sha256':sha(ROOT/'audit/EXECUTION_BINDING.json'),'gate_sha256':s['gate']['sha256'],'files':{p.name:sha(p) for p in staging.iterdir() if p.is_file()},'full_output_frames':158,'display_valid_frames':147,'source_fps':8,'display_fps':24,'GPU_started':False})
 dest.parent.mkdir(exist_ok=True);staging.rename(dest);return bound(dest/'COLLECTION.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--pair',choices=PAIRS,required=True);p.add_argument('--status',action='store_true');a=p.parse_args();print(json.dumps(status(a.pair) if a.status else collect(a.pair)))
