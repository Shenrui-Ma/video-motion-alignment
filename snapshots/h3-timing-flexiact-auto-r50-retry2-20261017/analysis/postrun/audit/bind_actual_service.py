"""Bind CPU-only incremental consumers to the current root-started service."""
from pathlib import Path
import sys,json,os
POST=Path(__file__).resolve().parents[1];ROOT=POST.parent.parent
sys.path[:0]=[str(ROOT/'scripts'),str(POST)]
import service
from contract import read,sha,save,check_binding
owner=read(ROOT/'processes/service.json');service.assert_owned(owner)
external=service.external_identity(owner['pid'])
assert external and external['uid']==os.getuid()
protocol=read(POST/'PROTOCOL.json')
value={'approved_for_consumer_start':True,'remote_root':str(ROOT),'producer_manifest_sha256':sha(ROOT/'deploy_manifest.json'),'protocol_sha256':sha(POST/'PROTOCOL.json'),'consumer_freeze_sha256':sha(POST/'FREEZE.json'),'service_record':owner,'external_identity':external,'scope':'four incremental releases with external chest retained in fixed five'}
check_binding(ROOT,value,protocol)
path=POST/'BINDING.json'
if path.exists():assert read(path)==value,'existing service binding changed'
else:save(path,value)
print(json.dumps({'file':str(path),'sha256':sha(path),'pid':owner['pid'],'GPU_started':False}))
