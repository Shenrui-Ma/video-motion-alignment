"""R150 four schedule arms, exact successful R89 references and initial noise."""
import argparse,copy,hashlib,importlib.util,json,pathlib,shutil,sys,time
P=pathlib.Path(__file__).resolve().parents[1];BASE=P.parent
T=BASE/'h3-guidance-schedule-r149-20261020/fallback_host9/cases/05_real_megumi_v'
SRC=BASE/'h3-timing-ive-subject-capacity-r89-20261018';E=BASE/'h3-ive-subject-capacity-metrics-r89-20261018'
SCHEDULES={'early':list(range(9)),'late':list(range(11,20)),'split':list(range(4))+list(range(15,20)),'global_weak':list(range(20))}
def rd(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 a=argparse.ArgumentParser();a.add_argument('source',choices=['short_0085','short_0274']);sid=a.parse_args().source
 R=P/'host9/cases'/sid;assert not R.exists();R.mkdir(parents=True)
 def wr(n,d):
  q=R/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 def cp(p,n):
  q=R/n;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
 for n,v in rd(T/'deploy_manifest.json')['files'].items():
  assert sha(T/n)==v['sha256'],n
  if n.startswith(('configs/graphs/','configs/prompts/','design/','inputs/')) or n=='audit/INHERITANCE.json':continue
  cp(T/n,n)
 cp(P/'cases/long_0039/extensions/H3CachedCondition/__init__.py','extensions/H3CachedCondition/__init__.py')
 for n in ['logs','processes','audit/router','audit/x0','output','input']: (R/n).mkdir(parents=True,exist_ok=True)
 raw=next(x for x in rd(SRC/'configs/scientific_contract.json')['cases'] if x['source_id']==sid and x['arm']=='native')
 ng=SRC/f'configs/graphs/r89_{sid}_seed2026101701_native.json';fg=SRC/f'configs/graphs/r89_{sid}_seed2026101701_forced.json'
 ref=P/'references/r89'/sid;meta=ref/f'r89_{sid}_shared_conditioning.json';m=rd(meta);receipt=rd(ref/'REMOTE_RECEIPT.json')
 gate=rd(E/f'incoming/{sid}/PAIR_RUNTIME_GATE.json');assert gate['passed']
 remote='/home/researcher/h3_runs/guidance_schedule_r150_host9_20261021/cases/'+sid
 runtime=rd(T/'configs/runtime.json');runtime.update(remote_root=remote,port=8652 if sid=='short_0085' else 8653,gpu_uuid='GPU-REDACTED',gpu_index=2,expected_gpu_index=2,minimum_free_mib=40960,profile='r150_'+sid+'_host9_shared_gpu',profile_scope='Exact R89 cached inputs/noise and numerical method; four R149 schedule arms; shared GPU2')
 wr('configs/runtime.json',runtime)
 cp(ng,'design/parent_native_graph.json');cp(meta,'design/conditioning.json');cp(T/'design/R17_core.py','design/R17_core.py')
 cp(T/'design/H3_model.py','design/H3_model.py')
 cp(E/f'incoming/{sid}/native_router.json','design/R122_actual_native_router.json')
 cp(E/f'inputs/{sid}_video.mp4','inputs/'+raw['video']);assert sha(R/'inputs'/raw['video'])==raw['video_sha256']
 fixed=rd(fg)['50'];assert (fixed['inputs']['step_start'],fixed['inputs']['step_end'],fixed['inputs']['alpha'],fixed['inputs']['time_offset'])==(6,15,1,0)
 wr('design/HISTORICAL_FIXED.json',{'source_graph':str(fg),'source_graph_sha256':sha(fg),'router_node_50':fixed,'pair_runtime_gate_sha256':sha(E/f'incoming/{sid}/PAIR_RUNTIME_GATE.json')})
 roles=[('reference_vae_latent',m['native_vae_calls'][0]['latent']),('conditioning_embedding',m['conditioning_embedding']),('conditioning_tags',m['token_tags']),('conditioning_position',m['packed_layout']['position_ids'])]
 tensors=[]
 for role,v in roles:
  x=next(copy.deepcopy(x) for x in gate['condition_tensor_files'] if x['file'].endswith('/'+v['tensor_file']))
  assert x['tensor_signature']=={k:v[k] for k in ('shape','dtype','sha256')};x['role']=role;x['original_file']=x['file'];tensors.append(x)
 parent='/data5/researcher/h3_runs/timing_ive_subject_capacity_r89_20261018'
 cache={'schema':'r144-original-clean-condition-cache-v1','source_id':sid,'seed':raw['seed'],'source_video_sha256':raw['video_sha256'],'prompt_sha256':hashlib.sha256(raw['prompt'].encode()).hexdigest(),'geometry':raw['geometry'],'parent_root':parent,'historical_original_root':parent,'shared_run_id':m['run_id'],'conditioning':{'file':parent+'/audit/'+meta.name,'sha256':sha(meta)},'tensors':tensors,'published_tensor_paths':[v['tensor_file'] for _,v in roles],'RGB_archive_policy':'Only four condition tensors reused; RGB archives remain remote','CPU_compatibility_sources':rd(T/'configs/parent_core_hashes.json')}
 wr('configs/CONDITION_CACHE.json',cache);wr('configs/input_hashes.json',{raw['video']:raw['video_sha256']})
 (R/'configs/prompts').mkdir(exist_ok=True);(R/'configs/prompts'/f'{sid}.txt').write_text(raw['prompt'])
 g=rd(fg)
 for n in ('2','22','23'):g.pop(n)
 g['5']={'class_type':'H3CachedReferenceConditioning','inputs':{'cache_manifest':remote+'/configs/CONDITION_CACHE.json','audit_dir':remote+'/audit','run_id':'unexecuted_parent'}}
 wr('design/parent_cached_graph.json',g)
 s=rd(T/'configs/scientific_contract.json');s.update(schema='r150-r89-schedule-extension-v1',cases=[],source_ids=[sid],conditioning_sha256=sha(meta),historical_shared_run=m['run_id'],noise_pair_id=f'r89_{sid}_seed2026101701',parent_noise_file=receipt['noise']['file'],parent_noise_sha256=receipt['noise']['sha256'],parent_cached_graph_sha256=sha(R/'design/parent_cached_graph.json'),historical_runtime='host9 original R89',execution_runtime='host9 existing environment; shared GPU2',parent_r89_seal_sha256=sha(SRC/'deploy_manifest.json'))
 s.pop('parent_r148_seal_sha256',None)
 sigmas=list(map(float,g['9']['inputs']['sigmas'].split(',')))
 for arm,steps in SCHEDULES.items():
  c=copy.deepcopy(raw);c.update(run_id=f'r150_{sid}_seed2026101701_{arm}',arm=arm,parent_graph='design/parent_native_graph.json',parent_graph_sha256=sha(ng),prompt_sha256=cache['prompt_sha256'],target_latent_shapes=m['target_latent_shapes'],physical_query_window=[0,raw['valid_frame_count']-1],steps_zero_based=steps,alpha=.25 if arm=='global_weak' else 1.,phase_displacement=0,evaluation_indices=list(range(raw['valid_frame_count'])))
  c['sigma_selected']=[{'step':i,'sigma':sigmas[i],'sigma_next':sigmas[i+1]} for i in steps];c['sum_abs_delta_sigma']=sum(abs(sigmas[i]-sigmas[i+1]) for i in steps);s['cases'].append(c)
 s['case_order']=[c['run_id'] for c in s['cases']];wr('configs/scientific_contract.json',s);wr('configs/queue.json',{'jobs':s['case_order'],'finalize':True})
 q=R/'scripts/r132_contract.py';text=q.read_text();old='"05_real_megumi_v": (2026101311, 141, [50, 65])}';new='"05_real_megumi_v": (2026101311, 141, [50, 65]), "short_0085": (2026101701,73,[0,65]), "short_0274": (2026101701,73,[0,71])}'
 assert old in text;q.write_text(text.replace(old,new).replace('frozen R148 cached graph changed','frozen historical cached graph changed'))
 q=R/'audit/root_run_batch.py';text=q.read_text().replace('analysis/postrun/05_real_megumi_v/',f'analysis/postrun/{sid}/')
 old="require(root!=ROOT and root.parent in managed,'peer must be a distinct root in an authorized managed run directory')"
 peers=[f'/home/researcher/h3_runs/reference_feedback_r151_20261021/cases/{x}' for x in ['short_0252','short_0358','05_real_megumi_v']]
 assert old in text;text=text.replace(old,"explicit_peers={Path(p) for p in "+repr(peers)+"}\n        require(root!=ROOT and (root.parent in managed or root in explicit_peers),'peer root is outside explicit authorization')");q.write_text(text)
 for name in ['check_fresh_paths.py','watch_queue.py']:
  p=P/'cases/long_0039/producer'/name;cp(p,'producer/'+name);q=R/'producer'/name;q.write_text(q.read_text().replace('long_0039',sid))
 wr('audit/INHERITANCE.json',{'schema':'r150-r89-exact-input-inheritance-v1','source':str(SRC),'source_seal_sha256':sha(SRC/'deploy_manifest.json'),'runtime_template':str(T),'runtime_template_seal_sha256':sha(T/'deploy_manifest.json'),'parent_pair_gate_sha256':sha(E/f'incoming/{sid}/PAIR_RUNTIME_GATE.json'),'method_equivalence':'Original EventBlockPatch constructor replaced by self.override_class pointing to same TemporalAttentionOverride; all math unchanged; schedule subclass changes only selected Euler steps','root_authorized_peer_roots':peers,'created_unix':time.time()})
 sys.path.insert(0,str(R/'scripts'));spec=importlib.util.spec_from_file_location('r132_contract',R/'scripts/r132_contract.py');mod=importlib.util.module_from_spec(spec);sys.modules['r132_contract']=mod;spec.loader.exec_module(mod)
 for c in s['cases']:wr('configs/graphs/'+c['run_id']+'.json',mod.expected_graph(c['run_id'],R))
 mod.registry(R)
 from execution_gate import seal
 sealed=seal(R);result={'source_id':sid,'case':str(R),'remote_root':remote,'seal_sha256':sha(R/'deploy_manifest.json'),'sealed_files':len(sealed['files']),'jobs':s['case_order']};wr('producer/BUILD_RECEIPT.json',result);print(json.dumps(result))
if __name__=='__main__':main()
