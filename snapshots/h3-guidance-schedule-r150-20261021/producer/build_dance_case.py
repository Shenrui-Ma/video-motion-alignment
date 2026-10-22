"""Build five same-bin schedules after actual single-load Qwen cache recovery."""
import argparse,copy,hashlib,importlib.util,json,shutil,sys,time
from pathlib import Path
P=Path(__file__).resolve().parents[1];R149=P.parent/'h3-guidance-schedule-r149-20261020';TPL=R149/'cases/05_real_megumi_v';LIVE=P/'cases/long_0059';CACHED=R149/'global_weak_host41/cases/05_real_megumi_v'
SCHED={'fixed':list(range(6,15)),'early':list(range(9)),'late':list(range(11,20)),'split':list(range(4))+list(range(15,20)),'global_weak':list(range(20))}
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def cp(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
def one(s,a,b):assert s.count(a)==1,(a,s.count(a));return s.replace(a,b)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('candidate',choices=['musk05','firefly06','sam07']);ap.add_argument('--host9',action='store_true');args=ap.parse_args();cid=args.candidate;admin=P/'host9/cases/short_0274' if args.host9 else LIVE
 recroot=P/'condition_recovery'/cid;cfg=read(recroot/'config.json');result=read(recroot/'CACHE_RECOVERY_RESULT.json');metadata=recroot/'recovered_conditioning.json';old=read(metadata)
 assert result['passed'] and sha(metadata)==result['metadata_sha256'] and result['input_config_sha256']==sha(recroot/'config.json')
 assert result['requires_shared_cache_native']==(not result['same_historical_embedding'])
 schedules=copy.deepcopy(SCHED)
 if result['requires_shared_cache_native']:schedules={'native':[],**schedules}
 root=(P/'host9' if args.host9 else P)/'cases'/cid;assert not root.exists();root.mkdir(parents=True)
 for rel,item in read(TPL/'deploy_manifest.json')['files'].items():
  assert sha(TPL/rel)==item['sha256'],rel
  if rel.startswith(('configs/graphs/','configs/prompts/','design/','inputs/','tests/')) or rel in ('audit/INHERITANCE.json','configs/runtime_device_rebind.json'):continue
  cp(TPL/rel,root/rel)
 for folder in ['logs','processes','output','input','audit/router','audit/x0','producer']:(root/folder).mkdir(parents=True,exist_ok=True)
 for name in ['configs/gpu_quarantine.json','configs/readonly_peer.json','configs/storage_policy.json','configs/cgroup_policy.json','scripts/service.py','audit/root_run_batch.py','scripts/cgroup_memory.py','scripts/supervise_service.py','scripts/execution_gate.py','scripts/capacity_trial.py','scripts/preflight.py']:
  cp(admin/name,root/name)
 if args.host9:cp(admin/'scripts/parent_stop.py',root/'scripts/parent_stop.py')
 cp(CACHED/'extensions/H3CachedCondition/__init__.py',root/'extensions/H3CachedCondition/__init__.py')
 nativepath=Path(cfg['native_graph']['file']);assert sha(nativepath)==cfg['native_graph']['sha256'];native=read(nativepath)
 cp(nativepath,root/'design/parent_native_graph.json');cp(metadata,root/'design/conditioning.json');cp(recroot/'CACHE_RECOVERY_RESULT.json',root/'design/CACHE_RECOVERY_RESULT.json');cp(recroot/'config.json',root/'design/CONDITION_RECOVERY_INPUT.json')
 inventory=read(P.parent/'h3-guidance-schedule-eval-r149-20261020/extension/candidate_inventory.json');candidate=next(x for x in inventory['candidates'] if x['candidate_id']==cid)
 src=Path(candidate['media']['source']['file']);assert sha(src)==cfg['source_video_sha256'];cp(src,root/'inputs'/src.name)
 image_name=native['21']['inputs']['image'];image=nativepath.parent.parent/'inputs'/image_name
 assert image.exists();cp(image,root/'inputs'/image_name)
 write(root/'configs/input_hashes.json',{src.name:sha(src),image_name:sha(image)})
 cp(TPL/'design/H3_model.py',root/'design/H3_model.py');cp(TPL/'design/R17_core.py',root/'design/R17_core.py')
 (root/'configs/prompts').mkdir(exist_ok=True);(root/'configs/prompts'/(cid+'.txt')).write_text(old['prompt'])
 assert old['prompt']==native['5']['inputs']['prompt'] and hashlib.sha256(old['prompt'].encode()).hexdigest()==cfg['prompt_sha256']
 remote=('/home/researcher/h3_runs/guidance_schedule_r150_host9_20261021/cases/' if args.host9 else '/data4/researcher/h3_runs/guidance_schedule_r150_20261021/cases/')+cid
 runtime=read(admin/'configs/runtime.json');runtime.update(remote_root=remote,port={'musk05':8655,'firefly06':8656,'sam07':8657}[cid],profile='r150_'+cid+'_schedule_only',profile_scope='New same-bin fixed plus four schedule controls; shared recovered conditions; optional same-cache native')
 write(root/'configs/runtime.json',runtime)
 parent_graph=read(TPL/'design/parent_cached_graph.json')
 for n in ('1','3','4','8','9','41'):parent_graph[n]=copy.deepcopy(native[n])
 parent_graph['6']['inputs']['noise_seed']=cfg['seed']
 write(root/'design/parent_cached_graph.json',parent_graph)
 cache=read(TPL/'configs/CONDITION_CACHE.json');cache.update(source_id=cid,seed=cfg['seed'],source_video_sha256=cfg['source_video_sha256'],prompt_sha256=cfg['prompt_sha256'],geometry=cfg['geometry'],parent_root=cfg['remote_root'],shared_run_id=old['run_id'],conditioning={'file':result['metadata_file'],'sha256':result['metadata_sha256']})
 cache['tensors']=[x for x in cfg['roles'] if x['role'] in ('reference_image_latent','reference_vae_latent','conditioning_tags','conditioning_position')]
 cache['tensors'].insert(2,{'role':'conditioning_embedding','file':result['embedding_file'],'sha256':result['embedding_file_sha256'],'tensor_signature':result['actual_embedding_signature']})
 if args.host9:
  binding=read(recroot/'HOST9_CACHE_BINDING.json');assert binding['passed'] and binding['result_sha256']==sha(recroot/'CACHE_RECOVERY_RESULT.json')
  for record in cache['tensors']:
   oldpath=record['file'];newrow=binding['files'][oldpath];assert record['sha256']==newrow['sha256'];record['file']=newrow['target_file']
  cm=binding['files'][cache['conditioning']['file']];assert cm['sha256']==cache['conditioning']['sha256'];cache['conditioning']['file']=cm['target_file'];cache['parent_root']=binding['target_root']
 write(root/'configs/CONDITION_CACHE.json',cache)
 science=read(TPL/'configs/scientific_contract.json');basecase=science['cases'][0];grid=[float(v) for v in native['9']['inputs']['sigmas'].split(',')];science['cases']=[]
 for arm,steps in schedules.items():
  c=copy.deepcopy(basecase);c.update(run_id=f'r150_{cid}_seed{cfg["seed"]}_{arm}',source_id=cid,original_source_id=cfg['source_id'],seed=cfg['seed'],arm=arm,prompt=old['prompt'],prompt_sha256=cfg['prompt_sha256'],parent_graph_sha256=sha(root/'design/parent_native_graph.json'),video=src.name,video_sha256=cfg['source_video_sha256'],geometry=cfg['geometry'],target_latent_shapes=old['target_latent_shapes'],physical_query_window=[0,140] if arm=='global_weak' else cfg['window'],steps_zero_based=steps,alpha=.25 if arm=='global_weak' else 1.)
  c['sigma_selected']=[{'step':i,'sigma':grid[i],'sigma_next':grid[i+1]} for i in steps];c['sum_abs_delta_sigma']=sum(abs(grid[i]-grid[i+1]) for i in steps);science['cases'].append(c)
 science.update(schema='r150-legacy-dance-shared-condition-schedule-v1',case_order=[c['run_id'] for c in science['cases']],source_ids=[cid],arms=list(schedules),conditioning_sha256=sha(metadata),historical_shared_run=old['run_id'],noise_pair_id='r150_'+cid+'_original_av_noise',parent_noise_file=cfg['noise_file'],parent_noise_sha256=cfg['noise_sha256'],parent_cached_graph_sha256=sha(root/'design/parent_cached_graph.json'),scope='Original prompt/geometry/noise; five current same-bin schedules; recovered shared Qwen cache',historical_runtime='Original historical archive',condition_recovery={'result_sha256':sha(recroot/'CACHE_RECOVERY_RESULT.json'),'same_historical_embedding':result['same_historical_embedding'],'requires_shared_cache_native':result['requires_shared_cache_native'],'historical_native':cfg['legacy_native'],'current_native_run':science['cases'][0]['run_id'] if result['requires_shared_cache_native'] else None})
 if args.host9:
  nn=binding['files'][cfg['noise_file']];assert nn['sha256']==cfg['noise_sha256'];science['parent_noise_file']=nn['target_file'];science['execution_runtime']='host9 Torch2.5.1; original conditions and noise retained'
 science.pop('parent_r148_seal_sha256',None)
 write(root/'configs/scientific_contract.json',science);write(root/'configs/queue.json',{'jobs':science['case_order'],'finalize':True})
 p=root/'scripts/r132_contract.py';s=p.read_text();begin=s.index('SCHEDULES =');end=s.index('\n\n\ndef read',begin);s=s[:begin]+'SCHEDULES = '+repr(schedules)+s[end:]
 s=s.replace('len(set(order)) == 4','len(set(order)) == len(SCHEDULES)').replace('four ordered unique arms required','registered ordered unique arms required').replace('(20 if c["arm"] == "global_weak" else 9)','len(SCHEDULES[c["arm"]])')
 begin=s.index('        expected = {');end=s.index('\n        expected_window =',begin);s=s[:begin]+'        expected = '+repr({'musk05':(2026101311,141,[50,65]),'firefly06':(2026101312,141,[39,44]),'sam07':(2026101311,141,[54,69])})+'[c["source_id"]]'+s[end:]
 # Reuse the already verified cross-filesystem noise copy before changing schedules.
 admin_contract=(admin/'scripts/r132_contract.py').read_text()
 admin_ast=__import__('ast').parse(admin_contract)
 loader=next(n for n in admin_ast.body if isinstance(n,__import__('ast').FunctionDef) and n.name=='prepare_loader_inputs')
 original_ast=__import__('ast').parse(s)
 previous=next(n for n in original_ast.body if isinstance(n,__import__('ast').FunctionDef) and n.name=='prepare_loader_inputs')
 lines=s.splitlines(keepends=True);lines[previous.lineno-1:previous.end_lineno]=[__import__('ast').get_source_segment(admin_contract,loader)+'\n'];s=''.join(lines)
 p.write_text(s)
 p=root/'extensions/H3TemporalRouter/schedule.py';s=p.read_text();begin=s.index('SCHEDULES =');end=s.index('\n\n\nclass ScheduleState',begin);p.write_text(s[:begin]+'SCHEDULES = '+repr({k:tuple(v) for k,v in schedules.items()})+s[end:])
 p=root/'scripts/cpu_runtime_smoke.py';s=p.read_text().replace('==4 and all(x.forward_index','=='+str(len(schedules))+' and all(x.forward_index').replace("'actual_ModelPatcher_clone_isolated_four_arms':True","'actual_ModelPatcher_clone_count':"+str(len(schedules)));p.write_text(s)
 p=root/'audit/root_run_batch.py';p.write_text(p.read_text().replace('analysis/postrun/long_0059/',f'analysis/postrun/{cid}/').replace('analysis/postrun/short_0274/',f'analysis/postrun/{cid}/'))
 p=root/'analysis/postrun/verify_schedule.py';p.write_text(p.read_text().replace('"historical_mid_reused": True','"historical_mid_reused": False, "new_fixed_generated": True'))
 # The fixed base core/layout stay byte-identical. Only explicit schedule membership is extended.
 for rel,digest in read(root/'configs/numerical_reuse.json').items():assert sha(root/rel)==digest,rel
 for name in ['check_fresh_paths.py','watch_queue.py']:cp(admin/'producer'/name,root/'producer'/name)
 cp(P/'producer'/('launch_host9_case.py' if args.host9 else 'launch_host41_dance.py'),root/'producer/launch_case.py')
 if args.host9:
  p=root/'producer/launch_case.py';p.write_text(p.read_text().replace('Root explicitly authorized R150 short_0085 then short_0274 on shared host9 GPU2 after CPU and fresh admission','Root explicitly authorized R150 selected dance schedules with shared conditions on host9 GPU2 after CPU and fresh admission'))
 p=root/'producer/check_fresh_paths.py';p.write_text(p.read_text().replace('analysis/postrun/long_0059/',f'analysis/postrun/{cid}/').replace('analysis/postrun/short_0274/',f'analysis/postrun/{cid}/'))
 sys.path.insert(0,str(root/'scripts'));spec=importlib.util.spec_from_file_location('r132_contract',root/'scripts/r132_contract.py');mod=importlib.util.module_from_spec(spec);sys.modules['r132_contract']=mod;spec.loader.exec_module(mod)
 for c in science['cases']:write(root/'configs/graphs'/(c['run_id']+'.json'),mod.expected_graph(c['run_id'],root))
 mod.registry(root)
 cp(LIVE/'tests/test_cross_device_cache.py',root/'tests/test_cross_device_cache.py')
 ts=(TPL/'tests/test_schedule.py').read_text().replace('self.assertEqual(len(jobs), 4)','self.assertEqual(len(jobs), '+str(len(schedules))+')').replace('["early", "late", "split", "global_weak"]',repr(list(schedules))).replace('run_queue.subprocess.run.call_count, 5','run_queue.subprocess.run.call_count, '+str(len(schedules)+1)).replace('20 if name == "global_weak" else 9','len(contract.SCHEDULES[name])')
 (root/'tests/test_schedule.py').write_text(ts)
 write(root/'producer/HISTORICAL_BINDING.json',{'candidate_id':cid,'original_source_id':cfg['source_id'],'native_graph':cfg['native_graph'],'old_native':cfg['legacy_native'],'condition_recovery':result,'new_samebin_fixed_required':True,'legacy_weight3_used_as_fixed':False,'actual_roles':list(schedules),'core_same_R149':sha(root/'extensions/H3TemporalRouter/core.py')==sha(TPL/'extensions/H3TemporalRouter/core.py'),'created_unix':time.time()})
 write(root/'audit/INHERITANCE.json',{'schema':'r150-legacy-dance-schedule-inheritance-v1','source_id':cid,'template_root':str(TPL),'template_seal_sha256':sha(TPL/'deploy_manifest.json'),'historical_native_graph_sha256':cfg['native_graph']['sha256'],'condition_recovery_result_sha256':sha(recroot/'CACHE_RECOVERY_RESULT.json'),'condition_policy':science['condition_recovery'],'original_noise_file_sha256':cfg['noise_sha256'],'new_fixed_samebin_steps':list(range(6,15)),'created_unix':time.time()})
 from execution_gate import seal
 seal(root);print(json.dumps({'case':str(root),'remote_root':remote,'seal_sha256':sha(root/'deploy_manifest.json'),'roles':list(schedules)}))
if __name__=='__main__':main()
