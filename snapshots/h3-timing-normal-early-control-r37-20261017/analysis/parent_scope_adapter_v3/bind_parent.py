"""Explicit limited-scope binding; no change to the frozen R37 numerical evaluator."""
import argparse,hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
EXPECTED={'completion_scope':'archive_integrity_and_existing_measurements_with_failed_RGB_replay','original_outcome_gate_passed':False,'all_OFF_141RGB_equal':False,'final_AV_latent_exact':True,'pixel_difference_origin':'undetermined','new_model_invocations':0,'new_metric_invocations':0}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def require(v,m):
 if not v:raise ValueError(m)
def check_scope(done,summary,protocol):
 for record in (done,summary):
  for k,v in EXPECTED.items():require(type(record.get(k)) is type(v) and record[k]==v,'unexpected parent completion scope '+k)
 require(done['recovery_protocol_sha256']==protocol['parent_recovery_protocol_sha256'],'parent recovery not reviewed protocol')
 require(done['passed'] is True and done['completion_status']=='complete_with_original_RGB_gate_failed','parent limited completion absent')
 return dict(EXPECTED)
def main():
 a=argparse.ArgumentParser();a.add_argument('--execute',action='store_true');args=a.parse_args()
 if not args.execute:print('Preparation only. Root approval required. Actual Auto OFF comparator retains failed Native RGB equivalence.');return
 p=read(HERE/'PROTOCOL.json');approval=read(HERE/'APPROVAL.json');require(approval.get('approved') is True and approval['protocol_sha256']==sha(HERE/'PROTOCOL.json'),'adapter approval absent')
 for rel,d in read(HERE/'FREEZE.json')['files'].items():require(sha(HERE/rel)==d,'adapter source changed '+rel)
 old=Path(p['root_local'])/p['target_postrun'];require(sha(old/'FREEZE.json')==p['target_freeze_sha256'] and sha(old/'PROTOCOL.json')==p['target_protocol_sha256'],'target postrun seal changed')
 for rel,d in read(old/'FREEZE.json')['files'].items():require(sha(old/rel)==d,'target payload changed '+rel)
 parent=Path(p['local_parent']);scope=check_scope(read(parent/'CPU_COMPLETE.json'),read(parent/'final/FINAL_SUMMARY.json'),p)
 sys.path.insert(0,str(old));import bind_auto_parent as legacy
 target=read(old/'PROTOCOL.json');require(target['auto_parent_root']==p['remote_parent'],'remote parent mismatch')
 binding=legacy.build(parent,target);binding['parent_completion_scope']=scope;binding['parent_scope_adapter_protocol_sha256']=sha(HERE/'PROTOCOL.json');binding['parent_scope_adapter_freeze_sha256']=sha(HERE/'FREEZE.json');binding['interpretation']=p['scope']
 out=old/'AUTO_PARENT_BINDING.json'
 with out.open('x') as f:f.write(json.dumps(binding,indent=2,allow_nan=False)+'\n')
 print(json.dumps({'passed':True,'binding':str(out),'sha256':sha(out),'parent_scope':scope}))
if __name__=='__main__':main()
