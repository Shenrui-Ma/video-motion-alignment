from pathlib import Path
import json,hashlib,shutil
R=Path('/Users/researcher/DevProjects/h3-timing-flexiact-expanded-r66-20261018')
P=Path('/Users/researcher/DevProjects/h3-timing-flexiact-forced-r65-20261018')
S=Path('/Users/researcher/DevProjects/h3-flexiact-expanded-selection-20261018')
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
inherit={}
for folder in ['scripts','extensions','tests','analysis/postrun','source_snapshot']:
 for p in (P/folder).rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts or p.suffix!='.py':continue
  rel=p.relative_to(P);dest=R/str(rel).replace('r65_contract.py','r66_contract.py');dest.parent.mkdir(parents=True,exist_ok=True)
  text=p.read_text().replace('r65','r66').replace('R65','R66').replace('timing-flexiact-forced-r66','timing-flexiact-expanded-r66')
  # Preserve reference numerical files byte for byte (these contain no task import).
  if 'source_snapshot' in p.parts:text=p.read_text()
  dest.write_text(text);inherit[str(dest.relative_to(R))]={'source':str(p),'source_sha256':sha(p),'initial_copy_sha256':sha(dest)}
for name in ['parent_core_hashes.json','runtime_kernel_hashes.json','admission.json']:
 (R/'configs').mkdir(exist_ok=True);shutil.copy2(P/'configs'/name,R/'configs'/name)
# Retain the original fixture as historical test data, never an R66 output.
for name in ['conditioning.json','captures.json','noise.json']:
 d=R/'configs/R49_evidence/fitness'/name;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(P/'configs/R49_evidence/fitness'/name,d)
# Frozen R65 native graph is only a graph template, not an R66 completed parent result.
graph_parent=P/'configs/graphs/r65_fitness_seed2026101701_native.json'
d=R/'configs/parent_graphs/r65_native_graph_template.json';d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(graph_parent,d)
for name in ['PREPARED_8_PAIRS.json','SELECTED_8_MANIFEST.json','SELECTION_FREEZE.json','EXPECTED_SHAPES.json','QUEUE_RECOMMENDATION.json','SOURCE_REVIEW.json','TARGET_REVIEW.json','REPORT.txt']:
 d=R/'configs/source_selection'/name;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(S/name,d)
for p in (S/'inputs').iterdir():
 if p.is_file():d=R/'inputs'/p.name;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
runtime=read(P/'configs/runtime.json');runtime.update(remote_root='/data3/researcher/h3_runs/timing_flexiact_expanded_r66_20261018',gpu_uuid='GPU-REDACTED',expected_gpu_index=2,port=8536,profile='host41_gpu2_normal_reserve8',status='PENDING_ROOT_CAPACITY')
put(R/'configs/runtime.json',runtime);put(R/'configs/profiles/host41_gpu2_normal_reserve8.json',runtime)
pairs={p['pair_id']:p for p in read(S/'PREPARED_8_PAIRS.json')['pairs']}
order=read(S/'QUEUE_RECOMMENDATION.json')['pair_order'];expected=read(S/'EXPECTED_SHAPES.json');cases=[];keys=[]
for pair_id in order:
 p=pairs[pair_id];key=p['action']+'__'+Path(p['target']['official_path']).stem;keys.append(key)
 for arm in ['native','forced']:
  target=Path(p['target']['prepared_local_path']).name
  cases.append(dict(source_id=key,pair_key=key,motion_source_id=p['action'],original_pair_id=pair_id,group=p['group'],source_is_new_motion_content=p['source_is_new_motion_content'],parent_graph=str(d.relative_to(R)) if False else 'configs/parent_graphs/r65_native_graph_template.json',parent_graph_sha256=sha(graph_parent),graph_template_only=True,video=Path(p['source']['video']).name,portrait=target,provenance=Path(p['source']['provenance']).name,seed=2026101701,run_id='r66_'+key+'_seed2026101701_'+arm,identity=p['target']['official_path'],prompt=p['prompt_exact'],video_sha256=p['source']['video_sha256'],portrait_sha256=p['target']['prepared_sha256'],provenance_sha256=p['source']['provenance_sha256'],arm=arm,prompt_version='R49_original',geometry=p['geometry'],valid_frame_count=147,evaluation_indices=p['evaluation_indices'],evaluation_crop_xywh=[0,0,1152,768],reference_image_expected=expected['reference_images'][target]))
sci=read(P/'configs/scientific_contract.json');sci.update(schema='r66-flexiact-expanded-fixed-route-development-pairs-v1',cases=cases,case_order=[c['run_id'] for c in cases],source_ids=keys,pair_keys=keys,motion_source_ids=list(dict.fromkeys(c['motion_source_id'] for c in cases)),purpose='Source-only frozen extension: six custom crosspairs from three new motion sequences and two official CSV identity pairs on development sources; report groups separately.',selection_scope={'official_csv_pairs':2,'custom_crosspairs':6,'total_pairs':8,'distinct_motion_sources':5,'new_motion_sources':3,'development_motion_sources':2,'generated_output_selection':False,'source_manifest':'configs/source_selection/SELECTED_8_MANIFEST.json'},condition_scope='Each action+target pair has its own shared Qwen/tag/reference/position conditioning and AV noise cache; its Native and forced runs share these entities. Verify actual conditions, initial AV noise, first six AV x0 predictions and all 21 endpoint files per run.')
sci['acceleration_axes']['cache']='default Comfy model/node cache across sequential jobs; conditioning node and noise cache identity include action+target pair'
sci['acceleration_axes']['runtime']='.41 GPU2 original compatible H3 core, normal memory mode reserve8; actual live admission pending'
put(R/'configs/scientific_contract.json',sci);put(R/'configs/queue.json',{'jobs':sci['case_order'],'finalize':False});put(R/'configs/input_hashes.json',{p.name:sha(p) for p in sorted((R/'inputs').iterdir()) if p.is_file()})
put(R/'audit/R65_INHERITANCE_INITIAL.json',inherit)
put(R/'configs/source_selection_hashes.json',{str(p.relative_to(R)):sha(p) for p in sorted((R/'configs/source_selection').iterdir())})
put(R/'audit/PREPARATION_PLAN.json',{'scope':'CPU only; new R66 directory only','parent':str(P),'input_package':str(S),'changes':['pair-scoped conditioning and noise keys','eight frozen pairs and variable reference-image shapes','GPU2/8536 isolation','actual image shape and packed-layout verification','reuse numerical kernels and resource lifecycle'],'validation':['frozen input and queue bindings','graph diff allowlist','eight distinct cache IDs','actual-output verifier negative fixtures','parent route mathematics and pure-padding tests','own-GPU union/peer admission tests'],'live_status':'PENDING; no GPU or service launched'})
print(keys)
