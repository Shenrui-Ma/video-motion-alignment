from pathlib import Path
import hashlib,json,shutil,time
R=Path(__file__).resolve().parents[1];P=Path('/Users/researcher/DevProjects/h3-timing-ive-reference-origin-r132-20261020');OLD=Path('/Users/researcher/DevProjects/h3-ive-aligned-media-clock-metrics-r129-20261020')
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
assert h(P/'deploy_manifest.json')=='0275d8171f8631cd98ac20f96602941767df7a969613b48f3cb2a11c407e0386'
for d in ['scripts','configs/graphs','design','audit']: (R/d).mkdir(parents=True,exist_ok=True)
for p in (OLD/'scripts').glob('*.py'):shutil.copy2(p,R/'scripts'/p.name)
for p in (OLD/'design').glob('*.json'):shutil.copy2(p,R/'design'/p.name)
for name in ['R122_native_x0_manifest.json','R122_native_prefix_statistics.json']:
 shutil.copy2(P/'design'/name,R/'design'/name)
for name in ['runtime.json','scientific_contract.json']:shutil.copy2(P/'configs'/name,R/'configs'/name)
science=read(P/'configs/scientific_contract.json');runtime=read(P/'configs/runtime.json');case=science['cases'][0]
shutil.copy2(P/'configs/graphs'/f'{case["run_id"]}.json',R/'configs/graphs'/f'{case["run_id"]}.json')
c=read(OLD/'configs/contract.json');c.update(schema='r132-single-reference-origin-consumer-v1',host=runtime['host'],producer_local=str(P),producer_remote=runtime['remote_root'],producer_seal_sha256=h(P/'deploy_manifest.json'),science_sha256=h(P/'configs/scientific_contract.json'),runtime_sha256=h(P/'configs/runtime.json'),case=case)
save(R/'configs/contract.json',c)
# Use the previously verified host-aware transport, rather than R129's host9 transport.
shutil.copy2(Path('/Users/researcher/DevProjects/h3-ive-prompt-envelope-metrics-r123-20261020/scripts/remote.py'),R/'scripts/remote.py')
p=R/'scripts/common.py';s=p.read_text();s=s.replace('import json,hashlib,time','import json,hashlib,time,copy,math')
a=s.index('REQUIRED_CHECKS=');b=s.index('\ndef require',a)
s=s[:a]+"REQUIRED_CHECKS=('producer_seal','actual_runtime_device','history','service','shared_conditions','original_input_pixels_tokens_positions_equal_R122','fixed_reference_origin_execution_counts','actual_layout','sampled_finite','actual_reference_branch_origin','origin_recomputed_from_actual_original','first_six_cross_host_diagnostics_complete','actual_R122_AV_noise')"+s[b:]
s=s.replace('r129-aligned-runtime-gate-v1','r132-reference-origin-runtime-gate-v1').replace('r129-one-output-completion-v1','r132-one-output-completion-v1').replace("{'aligned'}","{'reference_origin'}").replace("g['runs']['aligned']","g['runs']['reference_origin']").replace("r['routed_blocks']==0 and r['aligned_blocks']==1000","r['routed_blocks']==450 and r['original_rope_table_blocks']==1000")
a=s.index(" a=g['alignment'];");b=s.index(" require(g['evaluation_plan_sha256']",a)
s=s[:a]+''' a=g['reference_origin'];layout=a['layout'];rotation=a['rotation']
 require(a['new_method_claim'] is False and a['original_QKV_and_table_preserved'] is True,'reference branch scope differs')
 require(a['extra_query_scope']=='target_video_only' and a['reference_scope']=='all_video_reference_keys','auxiliary token scope differs')
 require(a['first_six_prediction_equality_required'] is False and a['layout_validation_count']==1 and a['rotation_calls']==450 and a['original_rope_table_calls']==1000,'reference-origin execution counts differ')
 parent=read(ROOT/'design/r122_long_0039_shared_conditioning.json');pos=parent['packed_layout']['position_ids']
 require(layout['original_position_sha256']==pos['sha256'],'original position binding differs')
 require(layout['reference_origin']==4839 and layout['original_target_origin']>4839 and abs(layout['target_time_displacement']+178.33333333333334)<1e-8,'actual origin differs')
 require(rotation['displacement_rope_units']==layout['target_time_displacement'] and rotation['time_channel_pairs']==[[0,16],[48,64]] and len(rotation['inv_freq'])==16 and len(rotation['inv_freq_sha256'])==64,'checkpoint frequency or rotation sign differs')
 require(all(layout[k]is True for k in ('reference_text_unchanged','spatial_unchanged','target_video_matches_reference_all_coordinates','target_audio_video_common_origin')),'canonical geometry differs')
 verify_prefix_diagnostics(g['prefix_comparison'])
 require(g['condition_comparison']['strict_metadata_pixels_tokens_positions_equal'] is True,'strict original inputs differ')
''' + s[b:]
s=s.replace("D/'ALIGNED_RUNTIME_GATE.json'","D/'REFERENCE_ORIGIN_RUNTIME_GATE.json'").replace("D/'aligned.mp4'","D/'reference_origin.mp4'")
a=s.index(' clean=lambda x:');b=s.index(" n=read(D/'noise.json')",a)
s=s[:a]+" require(compare_condition_metadata(read(D/'conditioning.json'),read(ROOT/'design/r122_long_0039_shared_conditioning.json'))==g['condition_comparison']['floating_model_output_hashes'],'actual condition diagnostic differs')\n"+s[b:]
s=s.replace("require(read(D/'alignment.json')==g['alignment']and read(D/'router.json')['routed_calls']==0,'actual operator audit differs');return m","router=read(D/'router.json');require(router['reference_origin']==g['reference_origin'] and router['routed_calls']==450 and router['routed_by_forward']==[0]*6+[50]*9+[0]*5 and router['routed_by_block']==[9]*50,'actual operator audit differs');return m")
s+='''

def compare_condition_metadata(actual,parent):
 clean=lambda x:{k:v for k,v in copy.deepcopy(x).items()if k not in ('run_id','pair_snapshot')}
 a,b=clean(actual),clean(parent);out={}
 for label,x,y in [('vae_latent',a['native_vae_calls'][0]['latent'],b['native_vae_calls'][0]['latent']),('conditioning_embedding',a['conditioning_embedding'],b['conditioning_embedding'])]:
  require(x['shape']==y['shape'] and x['dtype']==y['dtype'],'floating condition geometry differs')
  out[label]={'actual_sha256':x['sha256'],'R122_sha256':y['sha256'],'sha256_equal':x['sha256']==y['sha256'],'equality_required':False}
  for z in (x,y):z.pop('sha256');z.pop('tensor_file')
 require(a==b,'original pixels/tokens/positions or other metadata differ')
 return out

def verify_prefix_diagnostics(p):
 require(p['diagnostics_complete'] is True and p['equality_required'] is False and p['steps_zero_based']==list(range(6)) and p['streams']==['video','audio'],'prefix diagnostic coverage differs')
 require(p['parent_manifest_sha256']==sha(ROOT/'design/R122_native_x0_manifest.json') and p['parent_statistics_sha256']==sha(ROOT/'design/R122_native_prefix_statistics.json'),'historical diagnostic binding differs')
 stats=read(ROOT/'design/R122_native_prefix_statistics.json');rows=p['comparisons'];require(len(rows)==6,'prefix diagnostic row count differs')
 for i,row in enumerate(rows):
  require(row['step_zero_based']==i and set(row['streams'])=={'video','audio'},'prefix step/stream differs')
  for key,d in row['streams'].items():
   require(d['equality_required'] is False and d['sample_count']==1024 and d['parent_tensor_sha256']==stats['captures'][i]['streams'][key]['tensor_sha256'],'prefix source binding differs')
   require(len(d['actual_tensor_sha256'])==64 and d['full_tensor_sha256_equal']==(d['actual_tensor_sha256']==d['parent_tensor_sha256']),'prefix hash equality record differs')
   require(all(math.isfinite(d[k]) and d[k]>=0 for k in ('sample_difference_rms','sample_difference_max_abs','actual_whole_tensor_rms','parent_whole_tensor_rms')),'invalid prefix difference statistic')
   require(all(math.isfinite(d[k]) for k in ('actual_whole_tensor_mean','parent_whole_tensor_mean')),'invalid prefix mean')
 return p
'''
p.write_text(s)
p=R/'scripts/consumer.py';s=p.read_text().replace('R129','R132').replace('r129-','r132-').replace('ALIGNED_RUNTIME_GATE','REFERENCE_ORIGIN_RUNTIME_GATE').replace('aligned','reference_origin').replace('RoPE原点对齐','参考分支原点引导')
s=s.replace(",'alignment.json':(f'audit/router/{run}_alignment.json',r['alignment_file_sha256'])",'')
# The global replacement renamed the old separate audit filename; this branch uses router JSON only.
s=s.replace(",'alignment.json':(f'audit/router/{run}_alignment.json',r['alignment_file_sha256'])",'')
s=s.replace("All-step reference_origin target audio/video RoPE origin; Native attention; 0 temporal routing","Reference-video branch query-origin rotation; fixed steps 6–14; original joint RoPE preserved; 450 routed blocks")
p.write_text(s.replace('R132_EVALUATION_PLAN.json','R129_EVALUATION_PLAN.json'))
p=R/'scripts/full_frame_review.py';p.write_text(p.read_text().replace('RoPE原点对齐','参考分支原点引导'))
# Frozen bindings; no generated results or GPU entry.
files={str(p.relative_to(R)):h(p) for d in ['scripts','configs','design'] for p in (R/d).rglob('*')if p.is_file() and '__pycache__'not in p.parts}
save(R/'CONSUMER_FREEZE.json',{'schema':'r132-consumer-binding-v1','files':files,'producer_seal_sha256':c['producer_seal_sha256'],'GPU_entry':False,'created_unix':time.time()})
print(json.dumps({'consumer':str(R),'freeze_sha256':h(R/'CONSUMER_FREEZE.json'),'files':len(files)}))
