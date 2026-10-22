from pathlib import Path
import sys,json,copy,hashlib,shutil,os,importlib.util,subprocess
R=Path(__file__).resolve().parent;D=R.parent;OLD=D/'h3-reference-origin-positive-retest-r146-20261020';REMOTE='/data4/researcher/h3_runs/timing_phase_combined_r148_20261020'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
sid=sys.argv[1];valid={'short_0252':98,'short_0358':105,'long_0039':106,'long_0059':144}[sid];seed=2026101703 if sid=='short_0252' else 2026101701
d=R/'cases'/sid;assert not (d/'deploy_manifest.json').exists(),'frozen case already exists'
base=OLD/'cases'/(sid if sid.startswith('short') else 'short_0358')
for folder in ['scripts','extensions','configs','design','tests']:
 shutil.copytree(base/folder,d/folder,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
for folder in ['audit','analysis/postrun','inputs','processes','logs','temp']:(d/folder).mkdir(parents=True,exist_ok=True)
for name in ['root_run_batch.py','INHERITANCE.json']:shutil.copy2(base/'audit'/name,d/'audit'/name)
for p in (base/'analysis/postrun').glob('*.py'):shutil.copy2(p,d/'analysis/postrun'/p.name)
cache=read(base/'configs/CONDITION_CACHE.json');meta=read(base/'design/conditioning.json');graph=read(base/'design/parent_native_graph.json');science=read(base/'configs/scientific_contract.json');source=base/'inputs'/f'{sid}_video.mp4'
if sid.startswith('long'):
 c=D/'h3-threecase-auto-r144-20261020/cases'/(sid+'_cached_gpu2');cache=read(c/'configs/CONDITION_CACHE.json');graph=read(c/'configs/PARENT_GRAPH.json');source=c/'inputs'/f'{sid}_video.mp4'
 p=subprocess.run(['ssh','-T','H3_SERVER_B','cat '+cache['conditioning']['file']],capture_output=True,check=True);assert hashlib.sha256(p.stdout).hexdigest()==cache['conditioning']['sha256'];meta=json.loads(p.stdout)
 inv=read(c/'prepared_parent/FILE_INVENTORY.json');noisename=next(x for x in inv if x.endswith('_noise.pt'));science.update(parent_noise_file=cache['parent_root']+'/'+noisename,parent_noise_sha256=inv[noisename]['sha256'],noise_pair_id=Path(noisename).name.removesuffix('_noise.pt'))
 shutil.copy2(c/'configs/PARENT_CAPTURES.json',d/'design/parent_native_x0_manifest.json')
write(d/'configs/CONDITION_CACHE.json',cache)
# Preserve exact shared manifest file bytes, including formatting.
if sid.startswith('long'):(d/'design/conditioning.json').write_bytes(p.stdout)
else:shutil.copy2(base/'design/conditioning.json',d/'design/conditioning.json')
write(d/'design/parent_native_graph.json',graph)
run=f'r148_{sid}_seed{seed}_fixed_phase';remote=REMOTE+'/cases/'+sid;case=copy.deepcopy(science['cases'][0]);case.update(run_id=run,source_id=sid,seed=seed,arm='fixed_phase',prompt=meta['prompt'],prompt_sha256=cache['prompt_sha256'],parent_graph='design/parent_native_graph.json',parent_graph_sha256=sha(d/'design/parent_native_graph.json'),video=source.name,video_sha256=sha(source),geometry=cache['geometry'],valid_frame_count=valid,evaluation_indices=list(range(valid)),target_latent_shapes=meta['target_latent_shapes'])
science.update(schema='r148-fixed-plus-phase-combined-v1',cases=[case],case_order=[run],source_ids=[sid],arms=['fixed_phase'],conditioning_sha256=sha(d/'design/conditioning.json'),historical_shared_run=meta['run_id'],scope='One additional fixed same-bin plus phase output; original Native/fixed retained.',combination={'formula':'O + alpha*m_ref*(z_local_shiftedQ - z_original_allRef)','single_correction':True,'original_mass':True,'local_keys':'original same-bin radius0/time_offset0'})
write(d/'configs/scientific_contract.json',science);write(d/'configs/queue.json',{'jobs':[run],'finalize':True});write(d/'configs/input_hashes.json',{source.name:case['video_sha256']});(d/'configs/prompts'/f'{sid}.txt').write_text(meta['prompt'])
for p in (d/'configs/graphs').glob('*.json'):p.unlink()
for p in (d/'configs/prompts').glob('*.txt'):
 if p.name!=sid+'.txt':p.unlink()
if not (d/'inputs'/source.name).exists():os.link(source,d/'inputs'/source.name)
runtime=read(d/'configs/runtime.json');runtime.update(remote_root=remote,port={'short_0252':8628,'short_0358':8629,'long_0039':8630,'long_0059':8631}[sid],gpu_uuid='GPU-REDACTED' if sid in ('short_0252','long_0039') else 'GPU-REDACTED',profile='r148_'+sid+'_fixed_phase',status='CPU_PREPARED_ROOT_REVIEW_PENDING');runtime['gpu_index']=2 if sid in ('short_0252','long_0039') else 3;write(d/'configs/runtime.json',runtime)
s=(d/'scripts/r132_contract.py').read_text().replace('["reference_origin"]','["fixed_phase"]').replace('"H3ReferenceOrigin"','"H3FixedPhaseCombined"')
s=s.replace('return {"video": (1, 24, 32, 46, 82), "audio": (1, 32, 2, 178)}','return dict(zip(("video","audio"),map(tuple,case["target_latent_shapes"])))')
s=s.replace('spans=[(1,4,4,4,4)[i%5] for i in range(32)]','total=case["target_latent_shapes"][0][2]\n    spans=[(1,4,4,4,4)[i%5] for i in range(total)]').replace('range(32) if sum','range(total) if sum').replace("'total_latent_bins':32, 'pure_pad_bins':list(range(hi,32))","'total_latent_bins':total, 'pure_pad_bins':list(range(hi,total))")
s=s.replace('c["geometry"] ==\n            {"width": 1312, "height": 736, "frames": 107, "fps": 24}', 'c["geometry"]["width"]==1312 and c["geometry"]["height"]==736 and c["geometry"]["frames"] in (107,158) and c["geometry"]["fps"]==24')
s=s.replace('"arm": "reference_origin"','"arm": "fixed_phase"');(d/'scripts/r132_contract.py').write_text(s)
# The original core, phase rotation, layout and table-preservation code remain byte identical.
s=(R/'combined.py').read_text().replace("        self.audit['combined_fixed_phase']={","        self.audit['reference_origin'].update(configuration='existing fixed same-bin routing plus reference-origin Q phase', reference_scope='same-bin keys for shifted readout; allRef only for original mass and subtraction')\n        self.audit['combined_fixed_phase']={")
(d/'extensions/H3TemporalRouter/combined.py').write_text(s)
p=d/'extensions/H3TemporalRouter/__init__.py';s=p.read_text().replace('from .reference_origin import ReferenceOriginState, ReferenceOriginBlockPatch','from .combined import CombinedState as ReferenceOriginState, CombinedBlockPatch as ReferenceOriginBlockPatch').replace('H3ReferenceOrigin','H3FixedPhaseCombined').replace('H3 reference-origin branch (R17 configuration control)','H3 fixed same-bin + phase alignment');p.write_text(s)
shutil.copy2(R/'test_combined.py',d/'tests/test_combined.py')
# HTTP validation uses the actual whitelist before accepting a graph.
p=d/'audit/root_run_batch.py';s=p.read_text().replace('import service','import service\nimport urllib.request',1)
s=s.replace("            require(not q['queue_running'] and not q['queue_pending'],'unexpected existing queue');return True", "            require(not q['queue_running'] and not q['queue_pending'],'unexpected existing queue')\n            with urllib.request.urlopen(f'http://127.0.0.1:{service.PORT}/object_info',timeout=30) as response:info=json.load(response)\n            required={node['class_type'] for name in registry(ROOT)[1] for node in read(ROOT/'configs/graphs'/(name+'.json')).values()}\n            require(required<=set(info),'actual HTTP node types missing: '+repr(sorted(required-set(info))))\n            service.write_json(audit/'HTTP_NODE_SCHEMA.json',{'passed':True,'required':sorted(required),'available':sorted(info)})\n            return True")
s=s.replace("            if actual is None:return True", "            state_path=ROOT/'logs/controller_state.json'\n            if state_path.exists():require(read(state_path).get('status')!='failed','controller failed: '+repr(read(state_path)))\n            if actual is None:return True")
s=s.replace('r132-one-output-completion-v1','r148-fixed-phase-completion-v1').replace('analysis/postrun/'+('short_0358' if sid.startswith('long') else sid)+'/REFERENCE_ORIGIN_RUNTIME_GATE.json','analysis/postrun/'+sid+'/COMBINED_RUNTIME_GATE.json');p.write_text(s)
# CPU validation includes actual task node names and the exact shared cache.
p=d/'scripts/cpu_runtime_smoke.py';s=p.read_text().replace("'actual nodes.load_custom_node(H3AutomaticWindowRouter)','actual nodes.load_custom_node(H3CachedCondition)','pose_probe'","'actual nodes.load_custom_node(H3EventAudit,H3PairAudit,H3TemporalRouter,H3X0Readout,H3CachedCondition)'");p.write_text(s)
# Adapt existing actual-run integrity checks, keeping all original input and count checks strict.
p=d/'analysis/postrun/verify_reference_origin.py';s=p.read_text().replace("branch['reference_scope']=='all_video_reference_keys'","branch['reference_scope']=='same-bin keys for shifted readout; allRef only for original mass and subtraction'")
s=s.replace(" require(abs(layout['target_time_displacement']+178.33333333333334)<1e-8,'actual clock displacement differs')"," require(layout['target_time_displacement']<0,'actual clock displacement sign differs')")
s=s.replace("plan['target_video_segment'][1]-plan['target_video_segment'][0]==32*rows", "plan['target_video_segment'][1]-plan['target_video_segment'][0]==shapes['video'][2]*rows").replace("plan['reference_video_segment'][1]-plan['reference_video_segment'][0]==32*rows", "plan['reference_video_segment'][1]-plan['reference_video_segment'][0]==shapes['video'][2]*rows").replace("plan['signature'][1:]==[32,46,82,178]","plan['signature'][1:]==[shapes['video'][2],46,82,shapes['audio'][-1]]")
s=s.replace(" checks['sampled_finite']", " checks['combined_single_correction']=router['combined_fixed_phase']==dict(science['combination_audit'],local_shifted_calls=450)\n checks['sampled_finite']")
s=s.replace("'runs':{'reference_origin':record}","'runs':{'fixed_phase':record}").replace('r132-reference-origin-runtime-gate-v1','r148-fixed-phase-runtime-gate-v1').replace('REFERENCE_ORIGIN_RUNTIME_GATE.json','COMBINED_RUNTIME_GATE.json').replace('REFERENCE_ORIGIN_RUNTIME_GATE_FAILURE.json','COMBINED_RUNTIME_GATE_FAILURE.json');p.write_text(s)
science['combination_audit']={'formula':'O + alpha*m_ref*(z_local_shifted_Q - z_original_allRef)','original_mass_and_allRef_readout':True,'single_correction':True,'local_reference_selection':'existing same-bin radius0/time_offset0','original_QKV_positions_and_RoPE_table_preserved':True,'phase_source':'actual reference_origin minus target_origin','phase_zero_equals_existing_fixed':True,'alpha_zero_equals_native':True};write(d/'configs/scientific_contract.json',science)
# Parent fixed graph records are evidence, not relabelled native graphs.
e=next(x for x in read(D/'h3-timing-phase-combined-eval-r148-20261020/EVALUATION_MANIFEST.json')['cases'] if x['source_id']==sid);write(d/'design/HISTORICAL_FIXED.json',e['historical_runs']['fixed'])
spec=importlib.util.spec_from_file_location('contract_'+sid,d/'scripts/r132_contract.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);write(d/'configs/graphs'/(run+'.json'),m.expected_graph(d));print(m.registry(d)[1])
write(d/'audit/INHERITANCE.json',{'base':str(base),'operator':'fixed same-bin + reference-origin Q phase in one correction','unchanged_numerics':read(d/'configs/numerical_reuse.json'),'combined_sha256':sha(d/'extensions/H3TemporalRouter/combined.py'),'source_cache_manifest_sha256':sha(d/'configs/CONDITION_CACHE.json')})
