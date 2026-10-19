"""Bind completed R42 Native archive JSON only. Do not bind missing pose or seal."""
import ast,hashlib,json,shutil,time
from pathlib import Path
R=Path(__file__).resolve().parents[2]
P=R.parent/'h3-timing-source28289-native-r42-20261017'
A=P/'analysis/postrun/captured/batch'
REMOTE=Path('/data5/researcher/h3_runs/timing_source28289_native_r42_20261017')
RUN='r42_source_28289_seed2026101701_native'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):
 p=R/p
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
def check(ok,msg):
 if not ok:raise ValueError(msg)
check(sha(A/'RUN_GATE.json')=='1ea50cef90e93ea9f90fadb6222d0318aa147a668989b26034e384a7a26e6271','root archive gate differs')
gate=read(A/'RUN_GATE.json');inventory=read(A/'FILE_INVENTORY.json');runtime=read(A/'RUNTIME_GATE.json')
check(gate['passed'] is True and gate['runs']==[RUN],'parent gate identity/status')
check(gate['file_inventory_sha256']==sha(A/'FILE_INVENTORY.json') and gate['runtime_gate_sha256']==sha(A/'RUNTIME_GATE.json'),'archive anchor mismatch')
check(runtime['passed'] is True and all(x is True for x in runtime['checks'].values()),'runtime actual gate failed')
metadata={
 'parent_graph.json':f'configs/graphs/{RUN}.json',
 'parent_conditioning.json':f'audit/{RUN}_conditioning.json',
 'parent_noise.json':f'audit/{RUN}_noise.json',
 'parent_captures.json':f'audit/x0/{RUN}/manifest.json',
 'parent_file_inventory.json':'FILE_INVENTORY.json',
 'parent_run_gate.json':'RUN_GATE.json',
 'parent_runtime_gate.json':'RUNTIME_GATE.json',
 'parent_runtime_provenance.json':'configs/runtime_provenance.json',
 'parent_history.json':f'logs/{RUN}_history.json',
 'parent_router.json':f'audit/router/{RUN}.json',
 'source_provenance.json':'inputs/source_28289_provenance.json',
}
checked_local=[]
for rel,item in inventory.items():
 if rel.endswith('.pt'):continue
 p=A/rel;check(p.exists() and p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],'actual downloaded parent file differs: '+rel);checked_local.append(rel)
records={}
for name,rel in metadata.items():
 src=A/rel;dest=R/'configs'/name
 if rel in inventory:check(sha(src)==inventory[rel]['sha256'],'copied metadata not in actual inventory')
 if dest.exists():check(dest.read_bytes()==src.read_bytes(),'existing prepared source differs: '+name)
 else:shutil.copyfile(src,dest)
 records[name]={'source':str(src),'archive_relative':rel,'sha256':sha(src),'bytes':src.stat().st_size}
put('configs/parent_evidence_bindings.json',records)
c=read(A/f'audit/{RUN}_conditioning.json');cap=read(A/f'audit/x0/{RUN}/manifest.json');router=read(A/f'audit/router/{RUN}.json');h=read(A/f'logs/{RUN}_history.json');counts=runtime['runs'][RUN]
check(counts['NFE']==counts['callback_count']==counts['Euler_updates']==20,'wrong Native trajectory count')
check(router['completed_forward_calls']==20 and router['completed_calls']==1000 and router['routed_calls']==0 and router['calls_by_forward']==[50]*20,'wrong native block counts')
check(h['status']['completed'] is True and h['status']['status_str']=='success' and h['prompt'][2]==read(R/'configs/parent_graph.json'),'actual history differs from frozen graph')
check(cap['status']=='complete' and cap['seed']==2026101701 and cap['callback_count']==20 and [x['step_zero_based'] for x in cap['captures']]==list(range(20)),'actual native endpoint metadata differs')
check(len(counts['snapshots'])==21,'missing final/intermediate snapshots')
for row in counts['snapshots']:
 rel=str(Path(row['file']).relative_to(REMOTE));check(inventory[rel]=={'bytes':row['bytes'],'sha256':row['sha256']},'snapshot inventory mismatch')
check(len(runtime['condition_tensor_files'])==8,'eight clean entities required')
for row in runtime['condition_tensor_files']:
 rel=str(Path(row['file']).relative_to(REMOTE));check(inventory[rel]['sha256']==row['sha256'],'condition entity inventory mismatch')
embedding='audit/'+c['conditioning_embedding']['tensor_file']
put('configs/parent_layout.json',{'schema':'r44-actual-r42-layout-v1','conditioning_sha256':sha(R/'configs/parent_conditioning.json'),'packed_layout':c['packed_layout'],'conditioning_embedding':c['conditioning_embedding'],'embedding_file':inventory[embedding],'scope':'actual R42 clean conditioning metadata and actual archive inventory; not a full processed/postaugmentation tree'})
# Preserve prior draft before filling only newly observed values.
snapshot=R/'audit/preparation/pre_parent_binding_draft';snapshot.mkdir()
for rel in ('PROTOCOL.DRAFT.json','configs/protocol.json','configs/PARENT_CLOSURE.json','extensions/H3AutomaticWindowRouter/transport.py'):
 out=snapshot/rel;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/rel,out)
for rel in ('PROTOCOL.DRAFT.json','configs/protocol.json'):
 p=read(R/rel);p['preparation_status']='ACTUAL_R42_PARENT_BOUND_WAITING_SOURCE_POSE';p['prefix']['old_indices']=list(range(20));p['prefix']['missing_indices']=[];p['prefix']['availability']='Actual R42 RUN_GATE/RUNTIME_GATE/inventory attest Native0..19 plus final; source pose and final case closure still pending.'
 (R/rel).write_text(json.dumps(p,indent=2)+'\n')
closure=read(R/'configs/PARENT_CLOSURE.json');closure['status']='ACTUAL_PARENT_BOUND_WAITING_SOURCE_POSE';closure['ready']=False;closure['actual_layout']=c['packed_layout'];closure['actual_condition_count']=8;closure['actual_native_indices']=list(range(20));closure['parent_archive_inventory_count']=len(inventory);closure['bound_parent_files']={str((Path('configs')/name)):v['sha256'] for name,v in records.items()};closure['bound_parent_files']['configs/parent_layout.json']=sha(R/'configs/parent_layout.json');closure['remaining_required_files']=[rel for rel in closure['required_actual_files'] if not (R/rel).exists()]
(R/'configs/PARENT_CLOSURE.json').write_text(json.dumps(closure,indent=2)+'\n')
p=R/'extensions/H3AutomaticWindowRouter/transport.py';text=p.read_text();node=next(x for x in ast.parse(text).body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PROTOCOL_SHA' for t in x.targets));lines=text.splitlines(keepends=True);lines[node.lineno-1]='PROTOCOL_SHA='+repr(sha(R/'configs/protocol.json'))+'\n';p.write_text(''.join(lines))
report={'schema':'r44-r42-parent-partial-binding-v1','status':'WAITING_SOURCE_POSE_AND_FINAL_CLOSURE','observed_unix':time.time(),'parent_run_gate_sha256':sha(A/'RUN_GATE.json'),'parent_inventory_sha256':sha(A/'FILE_INVENTORY.json'),'inventory_counts':{'total':len(inventory),'PT':sum(k.endswith('.pt') for k in inventory),'nonPT':len(checked_local)},'actual_counts':{'NFE':20,'Euler_updates':20,'callbacks':20,'block_calls':1000,'routed':0,'condition_entities':8,'snapshots':21},'local_nonPT_SHA_rechecked':checked_local,'remote_PT_scope':'actual parent runtime gate and inventoried bytes/SHA copied; no PT downloaded, no model/pose/VAE executed here','layout':c['packed_layout'],'embedding_file':inventory[embedding],'kernel_gate':'87366 new actual layout;87361 is not equivalent evidence for new sequence length/segment offsets','source_pose_sha256':None,'final_seal':False,'GPU':False,'missing_required_files':closure['remaining_required_files']}
put('audit/preparation/PARTIAL_PARENT_BINDING.json',report)
print(json.dumps({k:report[k] for k in ('status','inventory_counts','actual_counts','kernel_gate','missing_required_files')}))
