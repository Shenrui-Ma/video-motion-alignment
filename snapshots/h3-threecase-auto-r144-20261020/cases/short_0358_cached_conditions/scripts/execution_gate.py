"""Explicit root capacity approval; no automatic or offline-observation launch."""
from pathlib import Path
import json,os,time
from r86_contract import ROOT,RUN,read,sha,registry,require

def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp.'+str(os.getpid()));tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,path)

def approval(root=ROOT):
 root=Path(root);p=root/'audit/ROOT_ONLINE_APPROVAL.json';a=read(p)
 require(a.get('schema')=='r86-online-capacity-trial-v1' and a.get('root_approved') is True,'root online approval missing')
 require(a['runtime_sha256']==sha(root/'configs/runtime.json') and a['decoder_profile_sha256']==sha(root/'configs/decoder_memory_profile.json'),'root runtime/decoder binding differs')
 require(a['main_required_free_bytes']==34*1024**3 and a['decoder_required_free_bytes']==16*1024**3,'trial memory budgets differ')
 require(a['run_id']==RUN and a['protocol_sha256']==sha(root/'configs/protocol.json'),'trial protocol/run differs')
 return a

def admitted_job(name,root=ROOT):
 require(name==RUN,'unregistered run');approval(root)
 from observer_import import t
 t.require_parent_closure(root)
 return True

def seal(root=ROOT):
 root=Path(root);files={}
 excluded={'configs/admission.json','configs/runtime_provenance.json','configs/observer_bindings.json','configs/PARENT_CLOSURE.json'}
 for folder in ('scripts','extensions','configs','inputs','design','analysis/postrun','tests','source_snapshot'):
  for p in sorted((root/folder).rglob('*')):
   rel=str(p.relative_to(root))
   if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and rel not in excluded:files[rel]={'sha256':sha(p),'bytes':p.stat().st_size}
 files['audit/INHERITANCE.json']={'sha256':sha(root/'audit/INHERITANCE.json'),'bytes':(root/'audit/INHERITANCE.json').stat().st_size}
 result={'schema':'r86-producer-seal-v1','files':files,'mutable':['configs/admission.json','configs/PARENT_CLOSURE.json','configs/observer_bindings.json','prepared_parent/','audit/ROOT_ONLINE_APPROVAL.json','configs/runtime_provenance.json'],'created_unix':time.time()};atomic(root/'deploy_manifest.json',result);return result

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('action',choices=['seal','approve-trial']);a=p.parse_args()
 if a.action=='seal':print(json.dumps({'files':len(seal()['files'])}))
 else:
  registry();atomic(ROOT/'audit/ROOT_ONLINE_APPROVAL.json',{'schema':'r86-online-capacity-trial-v1','root_approved':True,'runtime_sha256':sha(ROOT/'configs/runtime.json'),'decoder_profile_sha256':sha(ROOT/'configs/decoder_memory_profile.json'),'protocol_sha256':sha(ROOT/'configs/protocol.json'),'run_id':RUN,'main_required_free_bytes':34*1024**3,'decoder_required_free_bytes':16*1024**3,'measured_capacity':False,'created_unix':time.time()})
