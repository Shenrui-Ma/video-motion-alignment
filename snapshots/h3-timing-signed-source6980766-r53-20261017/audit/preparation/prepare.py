"""Prepare R53 by byte-copy plus explicit Python-token/JSON-field edits only."""
import ast,hashlib,json,shutil,sys,tokenize,io
from pathlib import Path
R=Path(__file__).resolve().parents[2]
P=R.parent/'h3-timing-auto-source28289-r45-20261017'
N=R.parent/'h3-timing-new-dance-native-r47-20261017';A=N/'analysis/postrun/captured/batch'
S=R.parent/'h3-timing-signed-trigger-r52-20261017'
NR='/data5/researcher/h3_runs/timing_new_dance_native_r47_20261017'
RR='/data5/researcher/h3_runs/timing_signed_source6980766_r53_20261017'
OLD='/data5/researcher/h3_runs/timing_auto_source28289_r45_20261017'
RUN='r53_source_6980766_seed2026101701_auto';PR='r47_source_6980766_seed2026101701_native'
GPU='GPU-REDACTED';PEER='GPU-REDACTED'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def put(rel,data):
 p=R/rel;p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():raise FileExistsError(p)
 p.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
 return sha(p)
records={}
def copy(src,rel):
 dst=R/rel;dst.parent.mkdir(parents=True,exist_ok=True)
 if dst.exists():raise FileExistsError(dst)
 shutil.copyfile(src,dst);records[rel]={'source':str(src),'source_sha256':sha(src),'bytes':src.stat().st_size}
 return dst
for name in ('RUN_GATE.json','FILE_INVENTORY.json','RUNTIME_GATE.json','CPU_COMPLETE.json','DERIVED_FILES.json'):
 assert (A/name).is_file()
g=read(A/'RUN_GATE.json');inv=read(A/'FILE_INVENTORY.json');runtime=read(A/'RUNTIME_GATE.json')
assert g['passed'] is True and PR in g['runs'] and g['file_inventory_sha256']==sha(A/'FILE_INVENTORY.json') and g['runtime_gate_sha256']==sha(A/'RUNTIME_GATE.json')
assert read(A/'CPU_COMPLETE.json')['passed'] is True
for sub in ('scripts','extensions'):
 for src in (P/sub).rglob('*.py'):
  if '__pycache__' not in str(src):copy(src,str(src.relative_to(P)))
# The unchanged R45 algorithms and old known-endpoint/decoder bridge remain evidence,
# except the two Policy entry modules whose declared semantics are signed.
for name in ('AUTOMATIC_CONTROL_BASELINE_SPEC.txt','PAIRWISE_GAIN_PROTOCOL.txt','SCAN_BASELINE_PROTOCOL.txt','model_hashes_host9.json','parent_core_hashes.json'):
 copy((N if name in ('model_hashes_host9.json','parent_core_hashes.json') else P)/'configs'/name,'configs/'+name)
metadata={
 'parent_graph.json':f'configs/graphs/{PR}.json','parent_conditioning.json':f'audit/{PR}_conditioning.json','parent_noise.json':f'audit/{PR}_noise.json','parent_captures.json':f'audit/x0/{PR}/manifest.json',
 'parent_run_gate.json':'RUN_GATE.json','parent_file_inventory.json':'FILE_INVENTORY.json','parent_runtime_gate.json':'RUNTIME_GATE.json','parent_runtime_provenance.json':'configs/runtime_provenance.json','parent_history.json':f'logs/{PR}_history.json','parent_router.json':f'audit/router/{PR}.json',
 'source_provenance.json':'inputs/source_6980766_provenance.json','source.pose.json':'source_pose/source_6980766_video/source_6980766_video.pose.json','parent_final_cpu_complete.json':'CPU_COMPLETE.json','parent_final_derived_files.json':'DERIVED_FILES.json'}
for name,rel in metadata.items():
 if rel in inv:assert sha(A/rel)==inv[rel]['sha256'] and (A/rel).stat().st_size==inv[rel]['bytes']
 copy(A/rel,'configs/'+name)
for name in ('source_6980766_video.mp4','source_6980766_portrait.jpg','source_6980766_provenance.json'):
 assert sha(A/'inputs'/name)==inv['inputs/'+name]['sha256'];copy(A/'inputs'/name,'inputs/'+name)
put('configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()})
condition=read(R/'configs/parent_conditioning.json');embedding='audit/'+condition['conditioning_embedding']['tensor_file']
put('configs/parent_layout.json',{'conditioning_sha256':sha(R/'configs/parent_conditioning.json'),'packed_layout':condition['packed_layout'],'conditioning_embedding':condition['conditioning_embedding'],'embedding_file':inv[embedding],'scope':'actual clean entities; no historical processed tree claim'})
assert condition['packed_layout']['seq_len']==87365
# Freeze experiment semantics BEFORE its tests or generated results.
p=read(P/'configs/protocol.json');p.update(schema='r53-signed-trigger-single-pilot-v1',scope='One previously evaluated R47 dance source6980766 to Elon Musk. Extend current-state trigger to both signs; identical Full operator. Not an independent signed-versus-old-policy effect comparison; old Auto was not run on this source.')
p['cases']=[dict(p['cases'][0],run_id=RUN,source_id='6980766',parent_root=NR,parent_run=PR)]
p['observer'].update(source_pose_sha256=sha(R/'configs/source.pose.json'),persistence='immediately previous endpoint; representative direction identical; shared arm; inclusive intersection/shorter >=0.5',signed_trigger='both confidence lags have same sign and abs(lag)>2; difference<=2; original reliability/common-support gain>.5',component_rule='Original interval-overlap connected components, including opposite signs; strongest minimum absolute error reduction representative; no direction split',earliest_on_index=1)
p['resources'].update(main_uuid=GPU,decoder_uuid=GPU)
p['inherited_rule'].update(detector_policy_actuator_unchanged=False,detector_and_actuator_unchanged=True,policy_change='signed candidate eligibility and same-direction persistence only',old_policy_sha256=sha(P/'scripts/automatic_window_policy.py'),signed_development_protocol_sha256=sha(S/'design/PROTOCOL.json'))
p['prefix'].update(all_OFF='Compare actual R47 Native and final AV; decoded RGB measured separately.',historical_limit='R47 archived eight clean condition entities, exact noise, all21 AV endpoints; full processed/postaugmentation tree and packed sampler inputs absent.',availability='Actual completed R47 archive and final source pose binding.')
p['evaluation']['source_scope']='Gym dance identity editing; both advancement/delay and UNKNOWN remain visible; arms-only observer.'
p['evaluation']['comparison']='R47 Native versus R53 signed Auto only; R52 final offline candidates are screening evidence and are never online windows.'
p['preparation_status']='SCIENCE_FROZEN_ACTUAL_R47_BOUND_GPU_NOT_AUTHORIZED'
put('configs/protocol.json',p);copy(R/'configs/protocol.json','PROTOCOL.json');copy(R/'configs/protocol.json','design/SCIENCE_PROTOCOL.json')
protocol_sha=sha(R/'configs/protocol.json')
# Exact token edits: no replacing content in evidence JSON or source files by substring.
constants={OLD:RR,OLD+'/audit':RR+'/audit','r45_source28289_seed2026101701_auto':RUN,'r45_source28289_shared':'r53_source_6980766_shared','h3-timing-auto-source28289-r45-20261017':'h3-timing-signed-source6980766-r53-20261017',PEER:GPU,GPU:PEER,
 'source28289 Elon Musk transfer; parent closure required':'source6980766 signed-trigger pilot; actual R47 parent closure required',
 'r45-root-resource-admission-v1':'r53-root-resource-admission-v1','R45 actual kernel absent/failed':'R53 actual kernel absent/failed',
 'frozen R45 root':'frozen R53 root',
 'audit root outside frozen R45 root':'audit root outside frozen R53 root',
 'R45 WAITING_R42_PARENT_CLOSURE; no source pose or actual parent evidence may be inferred':'R53 WAITING_R47_PARENT_CLOSURE; no evidence may be inferred',
 'actual R42 parent closure inventory incomplete':'actual R47 parent closure inventory incomplete','actual R42 parent closure changed: ':'actual R47 parent closure changed: ',
 '71e610e7dd90294e195c84890fdcd18beefe1fefabf68f63fa9a107c29291f93':protocol_sha}
changes={}
for src in list((R/'scripts').glob('*.py'))+list((R/'extensions').rglob('*.py')):
 tokens=list(tokenize.generate_tokens(io.StringIO(src.read_text()).readline));delta=[];new=[]
 for token in tokens:
  value=token.string
  if token.type==tokenize.STRING:
   try:v=ast.literal_eval(value)
   except (ValueError,SyntaxError):v=None
   if isinstance(v,str) and v in constants:value=repr(constants[v]);delta.append([token.start,list((v,constants[v]))])
  elif token.type==tokenize.NAME and value=='r45_contract':value='r53_contract';delta.append([token.start,['r45_contract','r53_contract']])
  elif src.name=='service.py' and token.type==tokenize.NUMBER and value=='8507':value='8513';delta.append([token.start,['8507','8513']])
  new.append(token._replace(string=value))
 if delta:src.write_text(tokenize.untokenize(new));changes[str(src.relative_to(R))]=delta
(R/'scripts/r45_contract.py').rename(R/'scripts/r53_contract.py')
# Two signed-policy modules share one byte-identical implementation, with original
# delayed implementation saved as a sibling; only loader resolution differs from R52.
for prefix in ('scripts','extensions/H3AutomaticWindowRouter'):
 copy(P/(prefix+'/automatic_window_policy.py'),prefix+'/delayed_window_policy.py')
 text=(S/'scripts/signed_policy.py').read_text();a=text.index("path=Path(");b=text.index('\n\n\ndef direction',a)
 text=text[:a]+"path=Path(__file__).with_name('delayed_window_policy.py')\nspec=importlib.util.spec_from_file_location('r53_frozen_delayed_policy',path)\nold=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)"+text[b:]
 (R/prefix/'automatic_window_policy.py').write_text(text)
# Inherited evidence narrows to the15 files that remain actually byte-identical.
for name in ('r27_inheritance.json','kernel_inheritance.json'):
 d=read(P/'configs'/name);d['exact_numerical_files']={k:v for k,v in d['exact_numerical_files'].items() if not k.endswith('/automatic_window_policy.py')}
 d['inherited_scope']='15 exact implementation files: Full/transaction/decoder/pose/metric. Signed eligibility/persistence requires independent R53 tests. Actual87365 layout and resource gate remain separate.'
 d['adapter_changes']=['R47 source6980766 actual parent','signed eligibility and directional persistence','GPU2/8513 exact-owner administration'];d['independent_required']=['actual87365 root GPU gate','eligible R47 Native prefix','root resources']
 put('configs/'+name,d)
# Copy suitable small integration fixtures; old case-specific tests are replaced by
# R53-specific contract tests, not executed as if old IDs still applied.
for name in ('counterfactual_support.py','pose_test_support.py','real_comfy_cpu_smoke.py','test_evidence.py','test_lifecycle.py','test_vae_guard.py','test_launch_generation.py'):
 if (P/'tests'/name).exists():copy(P/'tests'/name,'tests/'+name)
# CPU smoke reads the one actual graph via explicit token-only substitutions.
f=R/'tests/real_comfy_cpu_smoke.py';tokens=[]
for tok in tokenize.generate_tokens(io.StringIO(f.read_text()).readline):
 if tok.type==tokenize.STRING:
  try:v=ast.literal_eval(tok.string)
  except (ValueError,SyntaxError):v=None
  if v in ('configs/r45_source28289_seed2026101701_auto.json','r45_source28289_seed2026101701_auto'):
   tok=tok._replace(string=repr('configs/'+RUN+'.json' if v.startswith('configs/') else RUN))
 tokens.append(tok)
f.write_text(tokenize.untokenize(tokens))
# Original current graph derived structurally; prompt/seed/input/codec untouched.
sys.path.insert(0,str(R/'scripts'));from r53_contract import expected_graph
case=p['cases'][0];graph=expected_graph(read(R/'configs/parent_graph.json'),case);put('configs/'+RUN+'.json',graph)
put('configs/queue.json',{'jobs':[RUN],'finalize':False})
a=read(P/'configs/admission_template.json');a['fixed_fields']['gpu_uuid']=GPU if 'gpu_uuid' in a['fixed_fields'] else a['fixed_fields'].get('gpu_uuid')
# Drop no known schema fields; inspect inherited fixed content separately below.
a['fixed_fields']={k:v for k,v in a['fixed_fields'].items() if v is not None}
for k,v in list(a['fixed_fields'].items()):
 if v==PEER:a['fixed_fields'][k]=GPU
 if isinstance(v,list):a['fixed_fields'][k]=[GPU if x==PEER else PEER if x==GPU else x for x in v]
put('configs/admission_template.json',a);put('configs/admission.json',dict(a['fixed_fields'],permitted_compute_processes=[],root_live_review_required=True))
put('audit/preparation/COPY_INVENTORY.json',records);put('audit/preparation/TOKEN_EDITS.json',changes)
put('configs/parent_evidence_bindings.json',{k:records['configs/'+k] for k in metadata})
# Freeze only policy/scope; producer manifest created after CPU/review.
put('FREEZE.json',{'schema':'r53-science-freeze-v1','files':{x:sha(R/x) for x in ('PROTOCOL.json','configs/protocol.json','design/SCIENCE_PROTOCOL.json','scripts/automatic_window_policy.py','scripts/delayed_window_policy.py','extensions/H3AutomaticWindowRouter/automatic_window_policy.py','extensions/H3AutomaticWindowRouter/delayed_window_policy.py')}})
print(json.dumps({'protocol_sha256':protocol_sha,'layout':condition['packed_layout']['seq_len'],'copied':len(records),'token_edited_files':list(changes)}))
