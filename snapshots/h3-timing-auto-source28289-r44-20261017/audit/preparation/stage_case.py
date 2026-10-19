"""Local draft preparation only. Copy evidence bytes, edit known code tokens/JSON fields."""
import ast,copy,difflib,hashlib,io,json,shutil,tokenize
from pathlib import Path
R=Path(__file__).resolve().parents[2]
P=R.parent/'h3-timing-auto-source51310-r40-20261017'
N=R.parent/'h3-timing-source28289-native-r42-20261017'
OLD='/data5/researcher/h3_runs/timing_auto_source51310_r40_20261017'
REMOTE='/data5/researcher/h3_runs/timing_auto_source28289_r44_20261017'
NREMOTE='/data5/researcher/h3_runs/timing_source28289_native_r42_20261017'
RUN='r44_source28289_seed2026101701_auto';NRUN='r42_source_28289_seed2026101701_native'
GPU2='GPU-REDACTED';GPU3='GPU-REDACTED'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def put(p,v):
 p=R/p;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
copied=[]
def cp(src,rel):
 src=Path(src);dst=R/rel;dst.parent.mkdir(parents=True,exist_ok=True)
 assert not dst.exists(),dst
 shutil.copyfile(src,dst);assert sha(src)==sha(dst)
 copied.append({'source':str(src),'destination':str(rel),'sha256':sha(src),'bytes':src.stat().st_size})
manifest=read(P/'deploy_manifest.json')
for rel,v in manifest['files'].items():assert sha(P/rel)==v['sha256'],rel
# Code only: no historical case-specific config or result copied into active paths.
for rel in manifest['files']:
 if rel.split('/')[0] in ('scripts','extensions','tests'):
  cp(P/rel,rel if rel!='scripts/r40_contract.py' else 'scripts/r44_contract.py')
for name in ('AUTOMATIC_CONTROL_BASELINE_SPEC.txt','PAIRWISE_GAIN_PROTOCOL.txt','SCAN_BASELINE_PROTOCOL.txt','r27_inheritance.json','r27_parent_manifest.json','r28_parent_manifest.json'):
 cp(P/'configs'/name,'configs/'+name)
for name in ('parent_core_hashes.json','model_hashes_host9.json'):
 cp(N/'configs'/name,'configs/'+name)
cp(N/'configs/graphs'/f'{NRUN}.json','configs/parent_graph.json')
cp(N/'inputs/source_28289_provenance.json','configs/source_provenance.json')
cp(N/'design/INPUT_PROBE.json','configs/source_input_probe.json')
cp(N/'design/SOURCE_ONLY_SELECTION.json','configs/source_selection.json')
for name in ('source_28289_video.mp4','source_28289_portrait.jpg','source_28289_provenance.json'):
 cp(N/'inputs'/name,'inputs/'+name)
for parent,label,rels in ((P,'r40',('deploy_manifest.json','PROTOCOL.json','configs/protocol.json','configs/CPU_EVIDENCE.json','configs/kernel_inheritance.json','configs/inherited_actual87361_kernel.json','configs/observer_bindings.json')),(N,'r42',('deploy_manifest.json','configs/scientific_contract.json','configs/job_registry.json','configs/runtime.json','configs/parent_runtime_provenance.json'))):
 for rel in rels:cp(parent/rel,Path('audit/preparation/original_evidence')/label/rel)
# Exact token changes only in explicit code files. No rewriting evidence text.
case_token_map={OLD:REMOTE,OLD+'/audit':REMOTE+'/audit','r40_source51310_seed2026101701_auto':RUN,'r40_source51310_shared':'r44_source28289_shared','h3-timing-auto-source51310-r40-20261017':R.name,'source51310 development-screened same-corpus transfer':'source28289 Elon Musk transfer; parent closure required','configs/r40_source51310_seed2026101701_auto.json':'configs/'+RUN+'.json','source51310':'source28289'}
changed=[]
files={
 'scripts/r44_contract.py':case_token_map,
 'extensions/H3EventAudit/__init__.py':case_token_map,
 'extensions/H3AutomaticWindowRouter/__init__.py':case_token_map,
 'extensions/H3AutomaticWindowRouter/pair_gate.py':case_token_map,
 'extensions/H3AutomaticWindowRouter/transport.py':dict(case_token_map,**{GPU3:GPU2,GPU2:GPU3}),
 'scripts/service.py':dict(case_token_map,**{GPU3:GPU2,GPU2:GPU3}),
 'scripts/job.py':case_token_map,'scripts/preflight.py':case_token_map,'scripts/run_queue.py':case_token_map,
 'scripts/verify_completed.py':case_token_map,
 'scripts/gpu_dynamic_union_smoke.py':{GPU3:GPU2,'requires explicit root admission and exact GPU3 UUID':'requires explicit root admission and exact GPU2 UUID'},
 'scripts/prelaunch_gates.py':{GPU3:GPU2,'r40-root-resource-admission-v1':'r44-root-resource-admission-v1'},
 'scripts/build_manifest.py':{'r40-immutable-deploy-v1':'r44-immutable-deploy-v1'},
 'tests/real_comfy_cpu_smoke.py':case_token_map,
 'tests/test_automatic.py':case_token_map,
 'tests/test_admin_relocation.py':dict(case_token_map,**{GPU3:GPU2,GPU2:GPU3,'51310':'28289'}),
 'tests/test_case_evidence.py':case_token_map,
 'tests/test_resource_relocation.py':{GPU3:GPU2,GPU2:GPU3,'r40-root-resource-admission-v1':'r44-root-resource-admission-v1'},
}
for rel,mapping in files.items():
 p=R/rel;before=p.read_text();out=[];edits=[]
 for tok in tokenize.generate_tokens(io.StringIO(before).readline):
  v=tok.string
  if tok.type==tokenize.STRING:
   try:literal=ast.literal_eval(v)
   except (ValueError,SyntaxError):literal=None
   if isinstance(literal,str) and literal in mapping:v=repr(mapping[literal])
  elif tok.type==tokenize.NAME and v=='r40_contract':v='r44_contract'
  elif tok.type==tokenize.NUMBER and v=='8502' and rel in ('scripts/service.py','tests/test_admin_relocation.py'):v='8506'
  if v!=tok.string:edits.append({'line':tok.start[0],'before':tok.string,'after':v})
  out.append(tok._replace(string=v))
 after=tokenize.untokenize(out);ast.parse(after)
 if after!=before:p.write_text(after);changed.append({'file':rel,'edits':edits})
# Draft science: missing data are null, not inherited source51310 success certificates.
p=copy.deepcopy(read(P/'PROTOCOL.json'))
p['schema']='r44-source28289-auto-transfer-draft-v1'
p['scope']='Source28289 green-background gestures, Elon Musk identity, seed2026101701; frozen R40 automatic policy and Full operator. Actual R42 Native parent closure pending. Full141 scan; no human action window.'
p['preparation_status']='WAITING_R42_PARENT_CLOSURE'
p['cases']=[dict(p['cases'][0],run_id=RUN,source_id='28289',identity='Elon Musk',parent_root=NREMOTE,parent_run=NRUN)]
p['observer']['source_pose_sha256']=None
p['resources']['main_uuid']=p['resources']['decoder_uuid']=GPU2
p['prefix']['old_indices']=None;p['prefix']['missing_indices']=None
p['prefix']['expected_indices']=list(range(20));p['prefix']['availability']='PENDING actual R42 archive; no checkpoint evidence claimed yet'
p['prefix']['all_OFF']='Compare all available current Native/chosen and final AV with actual R42 Native; decoded141RGB equality is separately measured, never inferred from latent equality.'
p['prefix']['historical_limit']='R42 producer does not save full processed/postaugmentation tree or packed sampler inputs. Actual8 clean-condition entities, noise and21 Native endpoint closure await completion; no missing historical object is inferred.'
p['evaluation']['fixed_windows']=read(N/'configs/scientific_contract.json')['evaluation']['fixed_windows']
p['evaluation']['visual_frames']=read(N/'configs/scientific_contract.json')['evaluation']['stills']
p['evaluation']['source_scope']='Upper-body gestures on green background; cropped lower body retains UNKNOWN when support is insufficient.'
put('PROTOCOL.DRAFT.json',p);put('configs/protocol.json',p)
old_policy=read(P/'configs/protocol.json');put('configs/inherited_policy.json',{'observer':old_policy['observer'],'actuator':old_policy['actuator']})
inputs={n:sha(R/'inputs'/n) for n in ('source_28289_video.mp4','source_28289_portrait.jpg','source_28289_provenance.json')};put('configs/input_hashes.json',inputs)
put('configs/queue.json',{'jobs':[RUN],'finalize':False})
put('configs/admission_template.json',read(P/'configs/admission_template.json'))
put('configs/admission.json',dict(read(P/'configs/admission_template.json')['fixed_fields'],permitted_compute_processes=[],root_live_review_required=True))
put('configs/RESOURCE_ADMISSION_TEMPLATE.json',{'schema':'r44-root-resource-admission-v1','root_approved':False,'gpu_uuid':GPU2,'protocol_sha256':None,'actual_parent_layout':None,'kernel_gate_sha256':None,'known_endpoint_gate_sha256':None,'resource_measurements':None,'required_free_before_decoder_mib':12288,'scope':'single GPU isolated exec; runtime exact-parent admission remains mandatory','evidence':[]})
required=['configs/parent_conditioning.json','configs/parent_noise.json','configs/parent_captures.json','configs/parent_file_inventory.json','configs/parent_run_gate.json','configs/parent_runtime_gate.json','configs/parent_runtime_provenance.json','configs/parent_history.json','configs/parent_router.json','configs/source.pose.json','configs/parent_layout.json','configs/observer_bindings.json','configs/kernel_inheritance.json']
put('configs/PARENT_CLOSURE.json',{'schema':'r44-parent-closure-draft-v1','status':'WAITING_R42_PARENT_CLOSURE','ready':False,'parent_run':NRUN,'parent_root':NREMOTE,'required_actual_files':required,'actual_source_pose_sha256':None,'actual_layout':None,'actual_condition_count':None,'actual_native_indices':None,'actual_CPU_smoke':'not_run','GPU':'not_authorized'})
# Pin this *draft* protocol; ready gates added separately and final hash will change only after closure.
pth=R/'extensions/H3AutomaticWindowRouter/transport.py';txt=pth.read_text();tree=ast.parse(txt)
node=next(v for v in tree.body if isinstance(v,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PROTOCOL_SHA' for t in v.targets))
lines=txt.splitlines(keepends=True);lines[node.lineno-1]='PROTOCOL_SHA='+repr(sha(R/'configs/protocol.json'))+'\n';pth.write_text(''.join(lines))
# Derive graph with the exact target contract, not by replacing JSON text.
import importlib.util
spec=importlib.util.spec_from_file_location('stage_contract',R/'scripts/r44_contract.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
g=m.expected_graph(read(R/'configs/parent_graph.json'),p['cases'][0]);put('configs/'+RUN+'.json',g)
def diff(a,b,path=''):
 if isinstance(a,dict) and isinstance(b,dict):
  out=[]
  for k in sorted(a.keys()|b.keys()):out+=diff(a.get(k),b.get(k),path+'/'+k)
  return out
 return [] if a==b else [{'path':path,'parent':a,'child':b}]
put('configs/graph_diff.json',{'parent_graph_sha256':sha(R/'configs/parent_graph.json'),'graph_sha256':sha(R/'configs'/f'{RUN}.json'),'leaves':diff(read(R/'configs/parent_graph.json'),g),'prompt_byte_exact':g['5']['inputs']['prompt']==read(R/'configs/parent_graph.json')['5']['inputs']['prompt']})
put('audit/preparation/COPY_INVENTORY.json',copied)
put('audit/preparation/CODE_TOKEN_EDITS.json',changed)
put('audit/preparation/NUMERICAL_INHERITANCE.json',{'source':str(P),'parent_manifest_sha256':sha(P/'deploy_manifest.json'),'exact_numerical_files':read(P/'configs/kernel_inheritance.json')['exact_numerical_files'],'actual_layout_evidence':'pending R42; old87361 gate is historical only','actual_current_CPU':'not_run'})
print(json.dumps({'root':str(R),'copied_files':len(copied),'changed_code_files':len(changed),'graph_leaf_changes':len(diff(read(R/'configs/parent_graph.json'),g)),'status':'DRAFT_PARENT_PENDING'}))
