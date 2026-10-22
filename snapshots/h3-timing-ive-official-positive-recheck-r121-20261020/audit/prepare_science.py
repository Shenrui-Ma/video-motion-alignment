from pathlib import Path
import copy,hashlib,json,sys,time
R=Path(__file__).resolve().parents[1];B=R.parent
P=B/'h3-timing-ive-basketball-official-prompt-r119-20261019';H=B/'h3-timing-oxygen-seed-replication-r113-host41-20261019';G=B/'h3-timing-ive-subject-capacity-r89-20261018';O=B/'h3-timing-ivebench-expanded-r73-20261018'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
runtime=read(H/'configs/runtime.json');runtime.update(remote_root='/data4/researcher/h3_runs/timing_ive_official_positive_recheck_r121_20261020',port=8585,profile='host41_gpu2_r121_official_prompt',profile_scope='Two existing IVE positive-source rechecks with exact official edit_prompt, fresh Native then same-prompt fixed6..14. R113 H3 and MF release precede launch.')
put(R/'configs/runtime.json',runtime);put(R/'configs/admission.json',{'ready_for_launch':False,'scope':'own_user_video_jobs','existing_comfy_port':None,'permitted_compute_processes':[]})
definitions={};cases=[]
for source,base,valid in [('short_0252',O,98),('short_0358',G,105)]:
 original=next(c for c in read(base/'configs/scientific_contract.json')['cases'] if c['source_id']==source and c['arm']=='native')
 parent_rel='configs/parent_graphs/'+source+'_native.json';q=R/parent_rel;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes((base/'configs/graphs'/(original['run_id']+'.json')).read_bytes())
 d={'source_id':source,'source_producer':str(base),'source_producer_seal_sha256':sha(base/'deploy_manifest.json'),'original_task':original['original_task'],'parent_graph':parent_rel,'parent_graph_sha256':sha(q),'valid_frame_count':valid}
 for key,name in [('video',original['video']),('provenance',original['provenance']),('original_source',source+'_original.mp4')]:
  src=base/'inputs'/name;dst=R/'inputs'/name;dst.parent.mkdir(exist_ok=True);dst.write_bytes(src.read_bytes());d[key]=name;d[key+'_sha256']=sha(dst)
 definitions[source]=d
 prompt=original['original_task']['edit_prompt'];pf=R/'configs/prompts'/(source+'.txt');pf.parent.mkdir(parents=True,exist_ok=True);pf.write_text(prompt)
 for arm in ['native','forced']:
  c=copy.deepcopy(original);c.update(**{k:v for k,v in d.items() if k not in ['source_producer','source_producer_seal_sha256']});c.update(run_id=f'r121_{source}_seed2026101701_{arm}',arm=arm,seed=2026101701,prompt=prompt,prompt_sha256=sha(pf),prompt_version='official_edit_prompt',geometry={'width':1312,'height':736,'frames':107,'fps':24},reference_video_count=1,reference_image_count=0,evaluation_crop_xywh=[16,8,1280,720],evaluation_indices=list(range(valid)),task_scope='subject_editing',evaluation_scope='existing source official-prompt recheck; not a new independent source')
  cases.append(c)
put(R/'design/SOURCE_DEFINITIONS.json',definitions)
s=copy.deepcopy(read(P/'configs/scientific_contract.json'));s.update(schema='r121-two-source-official-prompt-v1',cases=cases,case_order=[c['run_id'] for c in cases],source_ids=list(definitions),pair_keys=list(definitions),prompt_version='official_edit_prompt',source_definitions_sha256=sha(R/'design/SOURCE_DEFINITIONS.json'),scope_note='Existing oxygen-mask and drinking/glasses source rechecks with benchmark original edit_prompt. New prompt protocol, not additional source coverage.')
s['evaluation']={'official':'IVE clip-level MF plus separate basic-task and event-timing review','padding_not_scored':True,'fixed_case_denominator':2,'new_independent_sources':0,'full_benchmark_reproduction':False}
s['continuous'].update(max_service_seconds=43200)
put(R/'configs/scientific_contract.json',s);put(R/'configs/queue.json',{'jobs':s['case_order'],'finalize':True})
put(R/'configs/input_hashes.json',{p.name:sha(p) for p in (R/'inputs').iterdir()})
put(R/'configs/parent_bindings.json',{'sources':definitions})
put(R/'PREPARED_INPUTS_MANIFEST.json',{'schema':'r121-byte-reused-inputs-v1','sources':definitions,'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in (R/'inputs').iterdir()}})
put(R/'configs/storage_policy.json',{'schema':'r121-storage-budget-v1','startup_required_free_bytes':12*1024**3,'estimated_output_bytes':6*1024**3,'expected_new_runs':4,'expected_total_frames':428,'minimum_free_gib':12,'large_tensors':'remote retained; compact consumer receives MP4/JSON only'})
put(R/'configs/predecessor.json',{'schema':'r121-predecessor-v1','required':[{'key':'R113','remote_root':read(H/'configs/runtime.json')['remote_root'],'producer_seal_sha256':sha(H/'deploy_manifest.json'),'runtime_sha256':sha(H/'configs/runtime.json'),'kind':'two_seed_pairs','required_runs':read(H/'configs/queue.json')['jobs'],'runtime_gate':'analysis/postrun/PAIR_RUNTIME_GATE.json','gate_schema':'r113-two-seed-runtime-gate-v1'}],'mf_final_release_path':'/data4/researcher/h3_runs/ive_r113_seed_replication_mf_20261020/audit/FINAL_RELEASE_VERIFIED.json'})
for d in ['logs','processes','output','input']:(R/d).mkdir(exist_ok=True)
sys.path.insert(0,str(R/'scripts'));import r121_contract as c
for case in cases:put(R/'configs/graphs'/(case['run_id']+'.json'),c.expected_graph(R,case))
c.registry();print(json.dumps({'sources':list(definitions),'prompt':[c['prompt'] for c in cases[::2]],'runs':s['case_order']},indent=2))
