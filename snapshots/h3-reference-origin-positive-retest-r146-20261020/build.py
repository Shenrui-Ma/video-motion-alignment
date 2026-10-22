from pathlib import Path
import ast,copy,hashlib,importlib.util,json,os,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parent
DEV=ROOT.parent
BASE=DEV/'h3-timing-ive-reference-origin-r132-20261020'
CACHE=DEV/'h3-threecase-auto-r144-20261020/cases/short_0358_cached_gpu2'
REMOTE='/data4/researcher/h3_runs/reference_origin_positive_retest_r146_20261020'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
rows=read(ROOT/'HOST9_INPUTS.json');rows={x['file']:x for x in rows}
inc=DEV/'h3-oxygen-generic-retention-metrics-r141b-host9-20261020/incoming/short_0252'
for sid,seed,valid,parent_graph,metadata in [
 ('short_0252',2026101703,98,inc/'native_graph.json',inc/'binding_02.json'),
 ('short_0358',2026101701,105,CACHE/'configs/PARENT_GRAPH.json',ROOT/'drink_conditioning.json')]:
 if sid=='short_0358' and not metadata.exists():
  oldcache=read(CACHE/'configs/CONDITION_CACHE.json');ret=subprocess.run(['ssh','-T','H3_SERVER_B','cat '+oldcache['conditioning']['file']],capture_output=True,text=True,check=True);metadata.write_text(ret.stdout)
  assert sha(metadata)==oldcache['conditioning']['sha256']
 dest=ROOT/'cases'/sid;remote=REMOTE+'/cases/'+sid
 for sub in ['scripts','extensions']:
  shutil.copytree(BASE/sub,dest/sub,ignore=shutil.ignore_patterns('__pycache__'),dirs_exist_ok=True)
 for sub in ['audit','analysis/postrun','configs/graphs','configs/prompts','design','inputs','tests','processes','logs','temp']:(dest/sub).mkdir(parents=True,exist_ok=True)
 for name in ['expected_checkpoint_hashes.json','parent_core_hashes.json','storage_policy.json','readonly_peer.json']:
  shutil.copy2(BASE/'configs'/name,dest/'configs'/name)
 shutil.copy2(ROOT/'contract_template.py',dest/'scripts/r132_contract.py')
 (dest/'scripts/r86_contract.py').write_text('from r132_contract import *\n')
 shutil.copy2(ROOT/'gpu_query_template.py',dest/'scripts/gpu_query.py')
 shutil.copy2(parent_graph,dest/'design/parent_native_graph.json')
 shutil.copy2(metadata,dest/'design/conditioning.json')
 g=read(parent_graph);old=read(metadata);run=f'r146_{sid}_seed{seed}_reference_origin';prompt=g['5']['inputs']['prompt']
 (dest/'configs/prompts'/f'{sid}.txt').write_text(prompt)
 if sid=='short_0252':
  origin='/home/researcher/h3_runs/timing_oxygen_generic_retention_r141b_host9_20261020'
  parent=REMOTE+'/parents/'+sid
  tensors=[]
  for role,t in [('reference_vae_latent',old['native_vae_calls'][0]['latent']),('conditioning_embedding',old['conditioning_embedding']),('conditioning_tags',old['token_tags']),('conditioning_position',old['packed_layout']['position_ids'])]:
   rec=rows[origin+'/audit/'+t['tensor_file']]
   tensors.append(dict(role=role,file=parent+'/audit/'+t['tensor_file'],sha256=rec['sha256'],bytes=rec['bytes'],tensor_signature={k:t[k] for k in ['shape','dtype','sha256']}))
  source=DEV/'h3-timing-oxygen-generic-retention-r141b-host9-20261020/inputs/short_0252_video.mp4'
  noise=rows[origin+'/audit/r141_short_0252_seed2026101703_noise.pt']
  noisefile=parent+'/audit/'+Path(noise['file']).name
  cache=dict(schema='r146-original-clean-condition-cache-v1',source_id=sid,seed=seed,source_video_sha256=sha(source),prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),geometry=dict(width=1312,height=736,frames=107,fps=24),parent_root=parent,shared_run_id=old['run_id'],conditioning=dict(file=parent+'/audit/r141_short_0252_shared_conditioning.json',sha256=sha(metadata)),tensors=tensors,CPU_compatibility_sources=read(CACHE/'configs/CONDITION_CACHE.json')['CPU_compatibility_sources'])
 else:
  cache=read(CACHE/'configs/CONDITION_CACHE.json');source=CACHE/'inputs/short_0358_video.mp4'
  noise=read(CACHE/'configs/PARENT_CLOSURE.json')['noise_copy'];noisefile=noise['file']
 if not (dest/'inputs'/source.name).exists():os.link(source,dest/'inputs'/source.name)
 write(dest/'configs/CONDITION_CACHE.json',cache)
 case=dict(run_id=run,source_id=sid,seed=seed,arm='reference_origin',prompt=prompt,prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),parent_graph='design/parent_native_graph.json',parent_graph_sha256=sha(parent_graph),video=source.name,video_sha256=sha(source),geometry=cache['geometry'],valid_frame_count=valid,evaluation_crop_xywh=[16,8,1280,720],evaluation_indices=list(range(valid)))
 science=dict(schema='r146-positive-reference-origin-retest-v1',cases=[case],case_order=[run],source_ids=[sid],arms=['reference_origin'],NFE_per_job=20,callback_count=20,online_observer=False,conditioning_sha256=sha(metadata),historical_shared_run=old['run_id'],noise_pair_id=Path(noisefile).name.removesuffix('_noise.pt'),parent_noise_file=noisefile,parent_noise_sha256=noise['sha256'],reference_origin=read(BASE/'configs/scientific_contract.json')['reference_origin'],continuous=dict(retain_service_between_jobs=False,cache_none=False,idle_hold_seconds=30,max_service_seconds=18000,job_timeout_seconds=14400,root_final_close_releases=True,failure_releases_exact_owned=True),scope='One new phase output; reuse historical Native/fixed. Exact original four clean conditions and AV noise. No source re-encoding.',historical_runtime='host9 Torch2.5.1' if sid=='short_0252' else 'host41 Torch2.11',execution_runtime='host41; original tensor values retained; floating forward differences recorded')
 write(dest/'configs/scientific_contract.json',science);write(dest/'configs/queue.json',dict(jobs=[run],finalize=True));write(dest/'configs/input_hashes.json',{source.name:sha(source)})
 runtime=read(BASE/'configs/runtime.json');runtime.update(remote_root=remote,port=8626 if sid=='short_0252' else 8627,profile='r146_'+sid+'_cached_reference_origin',profile_scope=science['scope'],status='CPU_PREPARATION_ROOT_REVIEW_PENDING');write(dest/'configs/runtime.json',runtime)
 # Preserve the actual R132 operator and all numerical helper bytes.
 numerical={str(p.relative_to(dest)):sha(p) for p in (dest/'extensions/H3TemporalRouter').glob('*.py') if p.name!='__init__.py'}
 write(dest/'configs/numerical_reuse.json',numerical)
 write(dest/'configs/runtime_kernel_hashes.json',{p:dict(current_sha256=h,parent_sha256=h,byte_equal=True) for p,h in numerical.items()})
 # Same loader reconstruction; publish only four tensors. Historical RGB metadata remains external evidence.
 shutil.copytree(CACHE/'extensions/H3CachedCondition',dest/'extensions/H3CachedCondition',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
 p=dest/'extensions/H3CachedCondition/__init__.py';s=p.read_text();a=s.index('    visit(old)');s=s[:a]+s[a:].replace('    visit(old)','    for record in manifest["tensors"]:\n        origin = Path(record["file"])\n        target = root / "tensor_blobs" / origin.name\n        target.parent.mkdir(parents=True, exist_ok=True)\n        if not target.exists():\n            os.link(origin, target)\n        if sha(target) != record["sha256"]:\n            raise ValueError("published cache blob changed")',1);p.write_text(s)
 p=dest/'extensions/H3PairAudit/__init__.py';s=p.read_text().replace("if source_run_id != 'r132_'+row['case']['source_id']+'_shared':","if source_run_id != __import__('r132_contract').science()['historical_shared_run']:");p.write_text(s)
 # Load the generic contract to build the single explicit graph.
 spec=importlib.util.spec_from_file_location('build_contract_'+sid,dest/'scripts/r132_contract.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 write(dest/'configs/graphs'/f'{run}.json',m.expected_graph(dest))
 # Narrow global malformed-row isolation; selected-GPU health remains original strict admission.
 p=dest/'scripts/service.py';s=p.read_text();a=s.index('    rows = []\n',s.index('def compute_processes')) ;b=s.index('\n\n\ndef queue_at',a);s=s[:a]+"    from gpu_query import parse_and_record\n    return parse_and_record(RUN, GPU, output)"+s[b:];p.write_text(s)
 # Keep conservative original full-session RAM gates until root reviews monitor integration.
 shutil.copy2(BASE/'configs/cgroup_policy.json',dest/'configs/cgroup_policy.json')
 # No stale R131 PID is a predecessor of this independent run.
 p=dest/'scripts/execution_gate.py';s=p.read_text();a=s.index('def predecessor_released');b=s.index('\n\ndef approval',a);s=s[:a]+'''def predecessor_released(root=ROOT):
    review = root_review(root)
    require(review.get("predecessor_release_verified") is True,
            "root must bind actual prior release in this run review")
    return review["predecessor_release_evidence"]
'''+s[b:];p.write_text(s)
 p=dest/'audit/root_run_batch.py';shutil.copy2(BASE/'audit/root_run_batch.py',p);s=p.read_text().replace("analysis/postrun/long_0039/REFERENCE_ORIGIN_RUNTIME_GATE.json",f"analysis/postrun/{sid}/REFERENCE_ORIGIN_RUNTIME_GATE.json");p.write_text(s)
 # Parent state and protected service are read-only; write only this case's queue.
 write(dest/'configs/gpu_quarantine.json',dict(schema='r146-exact-two-UUID-unavailable-rows-v1',uuids=sorted(['GPU-REDACTED','GPU-REDACTED']),only_excluded_fields=dict(pid='[N/A]',used_memory='[N/A]'),numeric_rows_preserved=True,protected_pid=1646285,protected_port=8189,release_of_quarantined_devices='unknown'))
 write(dest/'audit/INHERITANCE.json',dict(base=str(BASE),cached_loader=str(CACHE),numerical_reuse=numerical,original_metadata_sha256=sha(metadata),RGB_evidence='Original RGB signatures retained in historical metadata; RGB blobs not copied or allocated. Original four tensors loaded exactly.'))
 print(sid,'BUILT',m.registry(dest)[1],flush=True)
