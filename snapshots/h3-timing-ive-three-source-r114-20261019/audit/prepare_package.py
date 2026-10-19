"""Derive local R114 from sealed R93. No remote or CUDA action."""
from pathlib import Path
import json,copy,hashlib,shutil,re,sys
R=Path(__file__).resolve().parents[1];P=R.parent/'h3-timing-ive-event-candidates-r93-20261018';H=R.parent/'h3-timing-flexiact-remaining-repair-r104-20261019'
S=('long_0081','long_0059','long_0163');L={'long_0081':(124,120),'long_0059':(158,144),'long_0163':(158,144)}
REMOTE='/home/researcher/h3_runs/timing_ive_three_source_r114_20261019'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def cp(p,q):q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
assert not (R/'deploy_manifest.json').exists()
seal=read(P/'deploy_manifest.json');numeric=read(P/'configs/runtime_kernel_hashes.json')
for rel,row in seal['files'].items():
 assert sha(P/rel)==row['sha256'],rel
 if rel.startswith(('scripts/','extensions/','tests/','analysis/postrun/','source_snapshot/')) or rel in ('audit/root_run_batch.py',):
  dst=R/rel.replace('r93_contract.py','r114_contract.py');cp(P/rel,dst)
  if rel.endswith('.py') and not rel.startswith('source_snapshot/') and rel not in numeric:
   dst.write_text(dst.read_text().replace('r93','r114').replace('R93','R114'))
for rel in ('configs/parent_core_hashes.json','configs/expected_checkpoint_hashes.json','configs/storage_policy.json','configs/parent_graphs/r63_template_native.json','configs/R54_evidence/short_0210/captures.json'):
 cp(P/rel,R/rel)
# Retain original sealed design snapshots for subset and byte equality checks.
for rel in ('deploy_manifest.json','design/PROPOSAL.json','design/INPUT_PLAN.json','design/REFERENCE_EVENT_REVIEW_PLAN.json','PREPARED_INPUTS_MANIFEST.json','configs/scientific_contract.json','configs/runtime.json','audit/ROOT_DESIGN_BINDINGS.json'):
 cp(P/rel,R/'source_snapshot/r93'/rel)
cp(H/'audit/root_run_batch.py',R/'source_snapshot/r104/root_run_batch.py')
for rel,key in [('design/PROPOSAL.json','cases'),('design/INPUT_PLAN.json','pairs'),('design/REFERENCE_EVENT_REVIEW_PLAN.json','items'),('PREPARED_INPUTS_MANIFEST.json','pairs'),('configs/source_selection/SELECTED_5_MANIFEST.json','pairs')]:
 v=read(P/rel);lookup={x.get('source_id',x.get('pair_id')):x for x in v[key]};v[key]=[lookup[s] for s in S];dest=rel.replace('SELECTED_5','SELECTED_3');put(R/dest,v)
put(R/'configs/source_selection/OFFICIAL_SOURCE_RECEIPTS.json',{s:read(P/'configs/source_selection/OFFICIAL_SOURCE_RECEIPTS.json')[s] for s in S})
for s in S:
 for folder,suffix in [('configs/prompts','.txt'),('design','_P1_candidate.txt'),('design','_input_probe.json')]:cp(P/folder/(s+suffix),R/folder/(s+suffix))
 for p in (P/'inputs').glob(s+'_*'):cp(p,R/'inputs'/p.name)
(R/'design/README.txt').write_text('R114：R93中三个尚未运行的主体/接触物体编辑，原提示词、输入字节、选段、固定引导方法保持。顺序long0081、long0059、long0163。后两条为6秒素材片段。仅CPU准备，等待R104精确释放、短MF补齐与root放行。\n')
for folder in ('input','output','temp','user','custom_nodes','processes','logs','configs/graphs','audit/router','audit/x0'):(R/folder).mkdir(parents=True,exist_ok=True)
put(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()})
# Manifest references must point to the derived subset, while all selected rows stay exact.
v=read(R/'PREPARED_INPUTS_MANIFEST.json');v['input_plan_sha256']=sha(R/'design/INPUT_PLAN.json');put(R/'PREPARED_INPUTS_MANIFEST.json',v)
v=read(R/'configs/source_selection/SELECTED_3_MANIFEST.json');v['root_proposal_sha256']=sha(R/'design/PROPOSAL.json');v['root_review_events_sha256']=sha(R/'design/REFERENCE_EVENT_REVIEW_PLAN.json');put(R/'configs/source_selection/SELECTED_3_MANIFEST.json',v)
put(R/'configs/source_selection_hashes.json',{p.name:sha(p) for p in (R/'configs/source_selection').iterdir()})
runtime=read(P/'configs/runtime.json');runtime.update(status='CPU_PREPARED_ROOT_REVIEW_AND_RELEASE_PENDING',remote_root=REMOTE,gpu_uuid='GPU-REDACTED',expected_gpu_index=3,port=8574,profile='host9_gpu3_r114_normal_reserve8',profile_scope='Three selected previously unrun R93 official-source tasks; exact inherited input/prompt/method. Native actual review then guide/skip; first actual guided pair review. Root waits R104 release and short MF before launch.')
put(R/'configs/runtime.json',runtime);put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
s=read(P/'configs/scientific_contract.json');oldcases=s['cases'];s.update(schema='r114-native-first-three-source-v1',source_ids=list(S),cases=[],case_order=[],purpose='Three new source IDs from the R93 source-only selection. Exact inherited P1/input/method; actual Native acceptance precedes matched fixed guidance.')
for src in S:
 for arm in ('native','forced'):
  c=copy.deepcopy(next(x for x in oldcases if x['source_id']==src and x['arm']==arm));c['run_id']=c['run_id'].replace('r93','r114');s['cases'].append(c);s['case_order'].append(c['run_id'])
s['screening'].update(schema='r114-native-screen-policy-v1',fixed_source_denominator=3)
s['evaluation'].update(official='long0081 full official source; long0059/0163 six-second preselected source excerpts.',fixed_case_denominator=3,rules_sha256=sha(R/'configs/source_selection/SELECTED_3_MANIFEST.json'),adaptation='Exact R93 source bytes, rational PTS mapping and pixel geometry; source excerpts reported explicitly.')
for key in ('task_scopes','source_extent_scopes'):s['evaluation'][key]={k:v for k,v in s['evaluation'][key].items() if k in S}
s['acceleration_axes'].update(cache='Shared same-host conditions/noise within each pair; three independent pair caches.',postprocessing='Inherited R93 bytes: valid120/144/144, total124/158/158; crop16,8,1280,720; all terminal padding excluded.')
for key,rel in [('input_plan_sha256','design/INPUT_PLAN.json'),('prepared_input_manifest_sha256','PREPARED_INPUTS_MANIFEST.json'),('source_selection_sha256','configs/source_selection/SELECTED_3_MANIFEST.json'),('root_proposal_sha256','design/PROPOSAL.json'),('root_event_review_sha256','design/REFERENCE_EVENT_REVIEW_PLAN.json')]:s[key]=sha(R/rel)
s['prompt_sha256']={k:v for k,v in s['prompt_sha256'].items() if k in S};put(R/'configs/scientific_contract.json',s);put(R/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
for rel,row in numeric.items():row.update(parent_file=str(P/rel),parent_sha256=sha(P/rel),current_sha256=sha(R/rel),byte_equal=sha(P/rel)==sha(R/rel));assert row['byte_equal']
put(R/'configs/runtime_kernel_hashes.json',numeric)
put(R/'audit/ROOT_DESIGN_BINDINGS.json',{str(p.relative_to(R)):sha(p) for p in (R/'design').iterdir() if p.is_file()})
put(R/'audit/INHERITED_BYTE_BINDINGS.json',{'parent_r93_seal_sha256':sha(P/'deploy_manifest.json'),'six_numerical_files':numeric,'inputs':{p.name:{'parent_sha256':sha(P/'inputs'/p.name),'sha256':sha(p),'equal':sha(P/'inputs'/p.name)==sha(p)} for p in (R/'inputs').iterdir()},'prompts':{src:sha(R/'configs/prompts'/(src+'.txt')) for src in S}})
# Narrow selection and namespace changes.
p=R/'scripts/r114_contract.py';t=p.read_text();t=re.sub(r'^SOURCES=.*$',f'SOURCES={S!r}',t,flags=re.M);t=re.sub(r'^SOURCE_LENGTHS=.*$',f'SOURCE_LENGTHS={L!r}',t,flags=re.M);t=t.replace("len(s['cases'])==10","len(s['cases'])==6").replace('fixed five Native-first','fixed three Native-first').replace('SELECTED_5_MANIFEST','SELECTED_3_MANIFEST').replace('Five source-selected','Three source-selected');p.write_text(t)
p=R/'scripts/input_contract.py';t=p.read_text();t=re.sub(r'^SOURCES=.*$',f'SOURCES={S!r}',t,flags=re.M);t=re.sub(r'^LENGTHS=.*$',f'LENGTHS={tuple(L[k] for k in S)!r}',t,flags=re.M);p.write_text(t.replace('five source-preserving','three source-preserving'))
p=R/'scripts/preflight.py';p.write_text(p.read_text().replace("'sources':5","'sources':3"))
p=R/'scripts/prepare_inputs.py';t=p.read_text().replace('five source-selected','three source-selected').replace("['all', 'short_0370', 'long_0163', 'long_0059', 'long_0081', 'short_0203']",repr(['all',*S])).replace("['short_0370', 'long_0163', 'long_0059', 'long_0081', 'short_0203']",repr(list(S)));t=re.sub(r"^SELECTION_SHA = .*$",f"SELECTION_SHA = {sha(R/'design/INPUT_PLAN.json')!r}",t,flags=re.M);p.write_text(t)
# Cross-managed-root peer ownership is copied exactly from reviewed R104 function.
p=R/'audit/root_run_batch.py';t=p.read_text();a=t.index('def live_peers(');b=t.index('\ndef peer_policy(',a);ht=(H/'audit/root_run_batch.py').read_text();ha=ht.index('def live_peers(');hb=ht.index('\ndef peer_policy(',ha);p.write_text(t[:a]+ht[ha:hb]+t[b:])
# Adapt inherited dataset-specific expected shapes/counts without reducing generic lifecycle coverage.
p=R/'tests/test_registered_pairs.py';t=p.read_text().replace('exact_ten_pair','exact_six_pair').replace('len(order),10','len(order),6').replace('r114_short_0370_seed2026101701_forced.json','r114_long_0081_seed2026101701_forced.json');p.write_text(t)
p=R/'tests/test_host_migration.py';t=p.read_text().replace("(0,'GPU-REDACTED',8558)","(3,'GPU-REDACTED',8574)");p.write_text(t)
p=R/'tests/test_inputs.py';t=p.read_text();a=t.index(' def test_original_ntsc_valid_counts_are_not_original_frame_counts');b=t.index(' def test_original_LFS_bytes_and_full_or_clip_scope',a);t=t[:a]+''' def test_source_30fps_count_and_clipped_25fps_counts(self):
  self.assertEqual(c.LENGTHS,((124,120),(158,144),(158,144)))
  rows={r['source_id']:r for r in c.read(ROOT/'design/INPUT_PLAN.json')['pairs']}
  self.assertEqual(rows['long_0081']['source']['frame_count'],149)
  self.assertEqual(rows['long_0059']['clip']['start_frame'],175)
  self.assertEqual(rows['long_0163']['clip']['start_frame'],52)
'''+t[b:];t=t.replace('[False,False,False,False,True]','[False,False,False]').replace('[False,True,True,False,False]','[False,True,True]');p.write_text(t)
# Rebuild only graph paths/names from exact inherited prompt and numerical templates.
sys.path.insert(0,str(R/'scripts'));import r114_contract as c
for row in s['cases']:put(R/'configs/graphs'/(row['run_id']+'.json'),c.expected_graph(R,row))
put(R/'audit/PREPARE_RECEIPT.json',{'parent':str(P),'parent_seal_sha256':sha(P/'deploy_manifest.json'),'source_ids':list(S),'jobs':s['case_order'],'local_only':True,'remote_deployed':False,'gpu_started':False,'port_fresh_observation':'8574 was not listening on H3_SERVER_A at preparation; must recheck at launch.'})
print('PREPARED',R,'sources',len(S),'jobs',len(s['cases']))
