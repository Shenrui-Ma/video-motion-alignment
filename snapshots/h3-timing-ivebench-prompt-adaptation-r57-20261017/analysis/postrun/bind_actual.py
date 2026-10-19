"""Explicit root-invoked CPU binding after formal deployment and actual service exist."""
import argparse,os,shutil,time
from pathlib import Path
from contract import *


def freeze():
 names=[p.name for p in HERE.iterdir() if p.is_file() and (p.suffix in ('.py','.json','.txt'))
        and p.name not in ('FREEZE.json','BINDING.json','LATEST.json','LAST_ONE_PHASE.json','ONE_PHASE_STABILITY.json','CONSUMER_FAILURE.json','DOWNLOAD.json')]
 result={'schema':'r57-consumer-freeze-v1','files':{n:sha(HERE/n) for n in sorted(names)},
         'scope':'Fixed-five Native P1 archive, actual P0 input equality, exact original score crop/PTS, minimal local download; no GPU execution or metrics score claimed'}
 save(HERE/'FREEZE.json',result);return result


def validate_deployed(root,p):
 require(str(root)==p['root_remote'],'binding must read actual planned remote producer root')
 path=root/'deploy_manifest.json';manifest=read(path)
 require(manifest.get('status')=='ROOT_APPROVED_DEPLOYMENT','formal root deployment required')
 verify_producer_sources(root,sha(path),all_files=True)
 preparation=read(HERE/'PRODUCER_PREPARATION.json')
 require(sha(HERE/'PRODUCER_PREPARATION.json')==p['producer_preparation_sha256'],'preparation seal changed')
 for rel,expected in preparation['files'].items():
  if rel.startswith(('scripts/','extensions/','design/','configs/graphs/','configs/prompts/','configs/parents/')) or rel=='configs/scientific_contract.json':
   require(sha(safe(root,rel))==expected['sha256'],'prepared scientific/code bytes changed: '+rel)
 check_declared_cases(p,read(root/'configs/scientific_contract.json'))
 return manifest


def bind_producer(root):
 p=read(HERE/'PROTOCOL.json');require(p['producer_state']=='PENDING_FORMAL_DEPLOYMENT','producer already bound; preserve a revision before rebinding')
 validate_deployed(root,p)
 revision=HERE/'audit/predeployment';revision.mkdir(parents=True,exist_ok=False)
 for name in ('PROTOCOL.json','FREEZE.json'):
  if (HERE/name).exists():shutil.copyfile(HERE/name,revision/name)
 p.update(producer_state='DEPLOYMENT_BOUND',producer_manifest_sha256=sha(root/'deploy_manifest.json'))
 save(HERE/'PROTOCOL.json',p);freeze()
 result={'status':'PRODUCER_BOUND_SERVICE_PENDING','producer_manifest_sha256':p['producer_manifest_sha256'],'consumer_freeze_sha256':sha(HERE/'FREEZE.json'),'GPU_started':False}
 save(HERE/'audit/PRODUCER_BINDING.json',result);return result


def validate_service_identity(expected,actual,uid):
 require(actual==expected and actual['uid']==uid,'actual service generation/uid/command differs')
 return True

def bind_service(root):
 p=read(HERE/'PROTOCOL.json');require(p['producer_state']=='DEPLOYMENT_BOUND','formal producer deployment remains PENDING')
 validate_deployed(root,p);require(sha(root/'deploy_manifest.json')==p['producer_manifest_sha256'],'actual deployment changed')
 require(not (HERE/'BINDING.json').exists(),'actual service already bound; explicit revision required')
 owner=read(root/'processes/service.json');pid=owner['pid'];identity=owner['identity'];proc=Path('/proc')/str(pid)
 stat=(proc/'stat').read_text();tail=stat[stat.rindex(')')+2:].split()
 require(tail[0]!='Z','actual service is a zombie')
 raw=(proc/'cmdline').read_bytes()
 actual={'uid':proc.stat().st_uid,'start_ticks':tail[19],'cmdline':raw.replace(b'\0',b' ').decode()}
 validate_service_identity(identity,actual,os.getuid())
 external={'uid':actual['uid'],'start_ticks':actual['start_ticks'],'cmdline_sha256':hashlib.sha256(raw).hexdigest()}
 record={'approved_for_consumer_start':True,'remote_root':str(root),'protocol_sha256':sha(HERE/'PROTOCOL.json'),'consumer_freeze_sha256':sha(HERE/'FREEZE.json'),'producer_manifest_sha256':p['producer_manifest_sha256'],'service_record':owner,'external_identity':external,'status':'ACTUAL_ROOT_SERVICE_BOUND','bound_unix':time.time()}
 save(HERE/'BINDING.json',record);return record


def main():
 a=argparse.ArgumentParser();a.add_argument('--producer',action='store_true');a.add_argument('--service',action='store_true');args=a.parse_args();require(args.producer != args.service,'select one explicit binding stage')
 root=Path(read(HERE/'PROTOCOL.json')['root_remote'])
 print(json.dumps(bind_producer(root) if args.producer else bind_service(root),indent=2))
if __name__=='__main__':main()
