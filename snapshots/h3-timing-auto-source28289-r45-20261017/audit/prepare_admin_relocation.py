"""Exact-copy evidence; edit only selected JSON fields and Python tokens."""
import ast,copy,hashlib,io,json,shutil,tokenize
from pathlib import Path

OLD=Path('/Users/researcher/DevProjects/h3-timing-auto-source28289-r44-20261017')
NEW=Path(__file__).resolve().parents[1]
REMOTE_OLD='/data5/researcher/h3_runs/timing_auto_source28289_r44_20261017'
REMOTE_NEW='/data5/researcher/h3_runs/timing_auto_source28289_r45_20261017'
RUN_OLD='r44_source28289_seed2026101701_auto'
RUN_NEW='r45_source28289_seed2026101701_auto'
GPU2='GPU-REDACTED'
GPU3='GPU-REDACTED'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def put(rel,obj):
 p=NEW/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2)+'\n')
def cp(src,rel):
 p=NEW/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,p);return {'source':str(src),'destination':rel,'sha256':sha(p)}

m=read(OLD/'deploy_manifest.json');copies=[]
for rel,row in m['files'].items():
 assert sha(OLD/rel)==row['sha256'],rel
 copies.append(cp(OLD/rel,rel))
for rel in ['configs/admission.json','configs/queue.json']:
 copies.append(cp(OLD/rel,rel))
for name,digest in read(OLD/'configs/input_hashes.json').items():
 assert sha(OLD/'inputs'/name)==digest
 copies.append(cp(OLD/'inputs'/name,'inputs/'+name))
evidence=['deploy_manifest.json','PROTOCOL.json','FREEZE.json','configs/protocol.json','configs/observer_bindings.json','configs/CPU_EVIDENCE.json','configs/PARENT_CLOSURE.json','configs/graph_diff.json','configs/CASE_ROLE_ADDENDUM.json','audit/cpu_stage_attempt3_manifest.json','audit/real_comfy_cpu_attempt3.log','audit/root_actual_admission/FIRST_FAILURE_DIAGNOSIS.json','audit/root_actual_admission/READONLY_GPU2_FOLLOWUP.json','audit/root_actual_admission/DOWNLOAD.json','audit/root_actual_admission/files/audit/gpu_dynamic_union_gate.json','audit/root_actual_admission/files/audit/resource_admission.json','audit/root_actual_admission/files/processes/cleanup.json']
for rel in evidence:
 if (OLD/rel).is_file():copies.append(cp(OLD/rel,'audit/preparation/original_evidence/r44/'+rel))

# Existing scientific implementation and evidence are never subject to text replacement.
numeric=read(OLD/'configs/kernel_inheritance.json')['exact_numerical_files']
token_changes=[]
string_pairs=[(REMOTE_OLD,REMOTE_NEW),(RUN_OLD,RUN_NEW),('r44_source28289_shared','r45_source28289_shared'),('h3-timing-auto-source28289-r44-20261017','h3-timing-auto-source28289-r45-20261017'),('r44-root-resource-admission-v1','r45-root-resource-admission-v1'),('r44-immutable-deploy-v1','r45-immutable-deploy-v1'),('R44 actual kernel','R45 actual kernel'),('R44 WAITING','R45 WAITING'),('frozen R44 root','frozen R45 root')]
for sub in ('scripts','extensions','tests'):
 for p in (NEW/sub).rglob('*.py'):
  rel=str(p.relative_to(NEW));s=p.read_text();lines=s.splitlines(keepends=True);offsets=[0]
  for line in lines:offsets.append(offsets[-1]+len(line))
  edits=[]
  for tok in tokenize.generate_tokens(io.StringIO(s).readline):
   replacement=None
   if tok.type==tokenize.NAME and tok.string=='r44_contract':replacement='r45_contract'
   elif tok.type==tokenize.NUMBER and tok.string=='8506':replacement='8507'
   elif tok.type==tokenize.STRING:
    try:value=ast.literal_eval(tok.string)
    except (ValueError,SyntaxError):continue
    if not isinstance(value,str):continue
    new=value
    for a,b in string_pairs:new=new.replace(a,b)
    if value==GPU2:new=GPU3
    elif value==GPU3:new=GPU2
    if new!=value:replacement=repr(new)
   if replacement is not None:
    assert rel not in numeric,rel
    edits.append((offsets[tok.start[0]-1]+tok.start[1],offsets[tok.end[0]-1]+tok.end[1],replacement))
  for a,b,new in reversed(edits):s=s[:a]+new+s[b:]
  if edits:p.write_text(s);token_changes.append({'file':rel,'token_edits':len(edits),'old_sha256':sha(OLD/rel),'new_sha256':sha(p)})
(NEW/'scripts/r44_contract.py').rename(NEW/'scripts/r45_contract.py')

protocol=read(OLD/'configs/protocol.json')
protocol['schema']='r45-source28289-auto-admin-relocation-v1'
protocol['cases'][0]['run_id']=RUN_NEW
protocol['resources']['main_uuid']=GPU3;protocol['resources']['decoder_uuid']=GPU3
put('configs/protocol.json',protocol);put('PROTOCOL.json',protocol)
put('FREEZE.json',{'schema':'r45-scientific-freeze-v1','files':{'PROTOCOL.json':sha(NEW/'PROTOCOL.json')},'no_GPU_authorized':True})
transport=NEW/'extensions/H3AutomaticWindowRouter/transport.py'
oldhash=sha(OLD/'configs/protocol.json');s=transport.read_text();assert s.count(oldhash)==1
transport.write_text(s.replace(oldhash,sha(NEW/'configs/protocol.json')))

graph=read(OLD/f'configs/{RUN_OLD}.json')
for node in graph.values():
 for key,value in node['inputs'].items():
  if isinstance(value,str):
   if value.startswith(REMOTE_OLD):node['inputs'][key]=REMOTE_NEW+value[len(REMOTE_OLD):]
   elif value==RUN_OLD:node['inputs'][key]=RUN_NEW
   elif value==RUN_OLD+'_noise':node['inputs'][key]=RUN_NEW+'_noise'
   elif value=='r44_source28289_shared':node['inputs'][key]='r45_source28289_shared'
put(f'configs/{RUN_NEW}.json',graph);(NEW/f'configs/{RUN_OLD}.json').unlink()
put('configs/queue.json',{'jobs':[RUN_NEW],'finalize':False})
put('configs/admission.json',{'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[],'root_live_review_required':True})

def diff(a,b,path=''):
 if isinstance(a,dict) and isinstance(b,dict):
  return sum((diff(a.get(k),b.get(k),path+'/'+str(k)) for k in sorted(set(a)|set(b))),[])
 if a!=b:return [{'path':path,'parent':a,'child':b}]
 return []
put('configs/graph_diff.json',{'parent_graph_sha256':sha(NEW/'configs/parent_graph.json'),'graph_sha256':sha(NEW/f'configs/{RUN_NEW}.json'),'leaves':diff(read(NEW/'configs/parent_graph.json'),graph),'prompt_byte_exact':True})
put('configs/ADMIN_RELOCATION.json',{'schema':'r45-admin-relocation-v1','supersedes_unexecuted_scientific_run':'R44','parent_root':str(OLD),'parent_manifest_sha256':sha(OLD/'deploy_manifest.json'),'parent_protocol_sha256':oldhash,'protocol_allowed_changes':['/schema','/cases/0/run_id','/resources/main_uuid','/resources/decoder_uuid'],'protocol_delta':diff(read(OLD/'configs/protocol.json'),protocol),'graph_delta_from_r44':diff(read(OLD/f'configs/{RUN_OLD}.json'),graph),'scientific_parameters_unchanged':True,'same_17_numerical_files':numeric,'R44_failure_scope':'Administrative selected-GPU compute gate before prompt; zero DiT and zero observer. Original failure remains immutable.','R44_role_addendum_applies_without_change':True,'current_GPU_gate':'Pending new actual87366 model-free gate on GPU3; old R44 actual87366 gate preserved as prior evidence only.','current_resource_admission':'Unapproved; root must bind fresh actual GPU3 evidence.','historical_documents':'Original R40/R44 evidence retains original labels, roots and scope as observed; current administrative migration does not rewrite historical certificates.'})

resource=read(OLD/'configs/RESOURCE_ADMISSION_TEMPLATE.json')
resource.update(schema='r45-root-resource-admission-v1',gpu_uuid=GPU3,protocol_sha256=sha(NEW/'configs/protocol.json'))
put('configs/RESOURCE_ADMISSION_TEMPLATE.json',resource)
plan=read(OLD/'configs/KERNEL_PLAN_PENDING.json');plan['schema']='r45-actual-layout-plan-pending-GPU-v1';put('configs/KERNEL_PLAN_PENDING.json',plan)

# Historical documents are preserved raw. Current CPU coverage is explicit inheritance.
oldcpu=read(OLD/'configs/CPU_EVIDENCE.json')
put('configs/CPU_EVIDENCE.json',{'schema':'r45-administrative-cpu-coverage-v1','inherited_actual_Comfy_cpu':{'source':'audit/preparation/original_evidence/r44/configs/CPU_EVIDENCE.json','sha256':sha(OLD/'configs/CPU_EVIDENCE.json'),'log':'audit/preparation/original_evidence/r44/audit/real_comfy_cpu_attempt3.log','log_sha256':sha(OLD/'audit/real_comfy_cpu_attempt3.log'),'exit':0,'scope':oldcpu['scope']},'new_actual_Comfy_run':False,'reason':'Same source, seed, geometry, graph scientific inputs and 17 numerical files. Only root/run/device/port administrative migration; targeted stdlib tests and imports certify these deltas.','targeted_test_evidence':'audit/ADMIN_CPU_TESTS.json','GPU':{'actual_R45_kernel':'PENDING','actual_R45_model_run':'NOT_RUN'}})

bindings=read(OLD/'configs/observer_bindings.json');bindings['schema']='r45-frozen-auto-window-bindings-v1'
for rel in bindings['local_files']:bindings['local_files'][rel]=sha(NEW/rel)
put('configs/observer_bindings.json',bindings)
closure=read(OLD/'configs/PARENT_CLOSURE.json');closure['schema']='r45-actual-parent-closure-v1'
for rel in closure['actual_file_sha256']:closure['actual_file_sha256'][rel]=sha(NEW/rel)
put('configs/PARENT_CLOSURE.json',closure)
for rel,digest in numeric.items():assert sha(NEW/rel)==sha(OLD/rel)==digest
put('audit/ADMIN_COPY_TRACE.json',{'copies':copies,'python_token_edits':token_changes})
(NEW/'README.txt').write_text('R45 is the R44 source28289/Elon Musk normal-protection experiment moved to GPU3, port8507. The algorithm, data, seed and evaluation are unchanged. R44 failed before prompt/DiT/observer during strict GPU admission. R45 is prepared only; root owns actual GPU gate, resource approval and launch.\n')
(NEW/'COMPARABILITY.txt').write_text('Same actual R42 Native parent, exact prompt, input files, noise, eight clean conditions, source pose and all21 endpoint evidence as R44. Full processed/postaugmentation historical tree and raw sampler input entities were not saved by R42. Eligible current Native is compared through firstON inclusive; future old trajectory is permanently N/A after branching. AllOFF final AV exact and RGB equality are reported separately. configs/ADMIN_RELOCATION.json gives the exact administrative whitelist; historical raw evidence is never rewritten.\n')
print(json.dumps({'root':str(NEW),'python_token_changed':len(token_changes),'numeric_exact':len(numeric),'protocol_sha256':sha(NEW/'configs/protocol.json')}))
