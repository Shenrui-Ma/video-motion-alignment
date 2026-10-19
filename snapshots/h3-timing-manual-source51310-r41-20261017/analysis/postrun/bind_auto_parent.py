"""Bind only the completed local R40 archive; leaves missing/pending data unbound."""
import argparse
from contract import *
def build(local,p):
 local=Path(local);require(local.is_dir(),'R40 archive pending');done=read(local/'CPU_COMPLETE.json');gate=read(local/'RUN_GATE.json')
 require(done.get('passed') is True and done.get('run_id')==p['auto_parent_run'] and gate.get('passed') is True,'R40 completion missing')
 # Use actual final summary paths; do not infer a native or early endpoint.
 summary=read(local/'final/FINAL_SUMMARY.json');remote=Path(p['auto_parent_root'])
 pose=relative(remote,summary['pose']);video=relative(remote,summary['video'])
 result={'approved':True,'parent_root':str(local),'run_id':p['auto_parent_run'],'required_files':{r:sha(local/r) for r in ('RUN_GATE.json','CPU_COMPLETE.json','FILE_INVENTORY.json','DERIVED_FILES.json','DECISION_LEDGER.json')},'pose_relative':pose,'pose_sha256':summary['pose_sha256'],'video_relative':video,'video_sha256':summary['video_sha256']}
 validate_auto_parent(result,dict(p,auto_parent_root=str(local)));result['parent_root']=p['auto_parent_root'];result['local_verified_archive']=str(local);return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args()
 if not a.execute:print('Preparation only: --execute binds completed actual local R40 final after all archive gates.');return
 protocol=read(HERE/'PROTOCOL.json');local=Path(protocol['auto_parent_local']);out=HERE/'AUTO_PARENT_BINDING.json';require(not out.exists(),'parent binding already exists; explicit review to replace');result=build(local,protocol);save(out,result);print(json.dumps({'passed':True,'binding_sha256':sha(out),'run_id':result['run_id']}))
if __name__=='__main__':main()
