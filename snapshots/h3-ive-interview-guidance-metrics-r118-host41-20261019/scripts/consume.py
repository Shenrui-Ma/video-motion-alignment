"""Receive one completed guided output with existing Native and released ownership."""
import argparse,shlex,subprocess,shutil,time
from common import *
def remote_json(c,rel):
 p=Path(c['producer_remote'])/relative(rel);code='from pathlib import Path;p=Path('+repr(str(p))+');print(p.read_text() if p.exists() else "null")'
 r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12',c['host'],shlex.join(['python3','-c',code])],capture_output=True,text=True,check=True,timeout=50);return json.loads(r.stdout)
def fetch(c,rel,out):
 out=Path(out);out.parent.mkdir(parents=True,exist_ok=True);subprocess.run(['rsync','-az','-e','ssh -o BatchMode=yes -o ConnectTimeout=12',c['host']+':'+str(Path(c['producer_remote'])/relative(rel)),str(out)],check=True,timeout=300)
def compact_artifacts(g):
 # Large tensor records remain in the producer archive. Actual manifest digests stay bound.
 return {rel:digest for rel,digest in g['runs']['forced']['binding_artifacts'].items() if relative(rel).suffix=='.json'}
def collect(attempt):
 c=verify_static();require(attempt.startswith('root_') and attempt.replace('_','').isalnum(),'unsafe attempt');dest=ROOT/'incoming/long_0047'
 if dest.exists():require(verify_collection(dest)['attempt']==attempt,'other attempt already collected');return dest
 gate_rel='analysis/postrun/long_0047/PAIR_RUNTIME_GATE.json';g=remote_json(c,gate_rel);complete=remote_json(c,'audit/'+attempt+'/COMPLETE.json');release=remote_json(c,'audit/'+attempt+'/ROOT_EXIT_RECEIPT.json')
 if any(x is None for x in (g,complete,release)):return None
 verify_gate(g,c);require(remote_json(c,'deploy_manifest.json')==read(ROOT/'configs/producer_seal.json'),'remote producer differs')
 stage=ROOT/'audit'/('intake_'+str(time.time_ns()));stage.mkdir(parents=True);run=c['runs']['forced']
 files={'PAIR_RUNTIME_GATE.json':gate_rel,'COMPLETE.json':f'audit/{attempt}/COMPLETE.json','ROOT_EXIT_RECEIPT.json':f'audit/{attempt}/ROOT_EXIT_RECEIPT.json','STARTED.json':f'audit/{attempt}/STARTED.json','cleanup.json':'processes/cleanup.json','service.json':'processes/service.json','forced_graph.json':f'configs/graphs/{run}.json','forced_job.json':f'logs/{run}_job.json','forced_history.json':f'logs/{run}_history.json','forced_router.json':f'audit/router/{run}.json','forced.mp4':str(remote_relative(g['runs']['forced']['video']['file'],c))}
 for name,rel in files.items():fetch(c,rel,stage/name)
 for rel,digest in compact_artifacts(g).items():fetch(c,rel,stage/'evidence'/rel);require(sha(stage/'evidence'/rel)==digest,'compact binding differs')
 require(read(stage/'PAIR_RUNTIME_GATE.json')==g and read(stage/'COMPLETE.json')==complete and read(stage/'ROOT_EXIT_RECEIPT.json')==release,'actual receipts changed during transfer')
 verify_release(g,complete,release,read(stage/'STARTED.json'),read(stage/'cleanup.json'),sha(stage/'PAIR_RUNTIME_GATE.json'),c);verify_job(stage,g,c)
 shutil.copy2(ROOT/c['source']['file'],stage/'source.mp4');shutil.copy2(c['historical_native']['file'],stage/'native.mp4')
 require(remote_json(c,gate_rel)==g,'gate changed after collection')
 save(stage/'COLLECTION.json',dict(passed=True,attempt=attempt,consumer_freeze_sha256=sha(ROOT/'CONSUMER_FREEZE.json'),roles=['source','native','forced'],valid_frames=97,total_frames=107,fps=24,crop_xywh=[16,8,1280,720],files={str(p.relative_to(stage)):sha(p) for p in stage.rglob('*') if p.is_file()},historical_native=c['expected_historical_native'],visual_review='PENDING_FULL97',official_MF='PENDING',unix=time.time()))
 dest.parent.mkdir(exist_ok=True);stage.rename(dest);verify_collection(dest);return dest
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--attempt',required=True);a.add_argument('--status',action='store_true');x=a.parse_args()
 if x.status:
  c=verify_static();print(json.dumps(dict(pair_present=remote_json(c,'analysis/postrun/long_0047/PAIR_RUNTIME_GATE.json') is not None,complete_present=remote_json(c,f'audit/{x.attempt}/COMPLETE.json') is not None)))
 else:
  dest=collect(x.attempt)
  if dest is None:print(json.dumps(dict(state='PENDING_ACTUAL_COMPLETED_RELEASED_R118')))
  else:
   from prepare import prepare
   print(json.dumps(prepare(dest),ensure_ascii=False))
