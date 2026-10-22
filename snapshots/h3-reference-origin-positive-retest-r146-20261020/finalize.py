from pathlib import Path
import ast,json,shutil
R=Path(__file__).resolve().parent;B=R.parent/'h3-timing-ive-reference-origin-r132-20261020';C=R.parent/'h3-threecase-auto-r144-20261020/cases/short_0358_cached_gpu2'
for sid in ['short_0252','short_0358']:
 d=R/'cases'/sid
 for f in ['capacity_trial.py','cgroup_memory.py','working_set_capacity.py']:shutil.copy2(C/'scripts'/f,d/'scripts'/f)
 shutil.copy2(C/'configs/cgroup_policy.json',d/'configs/cgroup_policy.json')
 for f in ['capture_checks.py']:shutil.copy2(B/'analysis/postrun'/f,d/'analysis/postrun'/f)
 for f in ['fixtures.py','test_reference_origin.py']:shutil.copy2(B/'tests'/f,d/'tests'/f)
 # Actual target crop follows the original valid interval, including its partial final positional bin.
 p=d/'scripts/r132_contract.py';s=p.read_text();a=s.index('def routing_layout');b=s.index('\n\ndef expected_graph',a);s=s[:a]+'''def routing_layout(case):
    spans=[(1,4,4,4,4)[i%5] for i in range(32)]
    end=case['valid_frame_count']-1;hi=next(i+1 for i in range(32) if sum(spans[:i+1])>end)
    return {'latent_interval_half_open':[0,hi], 'position_bin_coverage_inclusive':[0,sum(spans[:hi])-1],
            'pixel_interval_inclusive':[0,end], 'total_latent_bins':32, 'pure_pad_bins':list(range(hi,32)), 'frame_rows':943}
'''+s[b:];p.write_text(s)
 p=d/'scripts/launch_remote.py';s=p.read_text().replace("'H3X0Readout']:","'H3X0Readout','H3CachedCondition']:");p.write_text(s)
 # Retain the reviewed monitor unchanged; small parent guard catches monitor death before and during loading.
 p=d/'scripts/capacity_watchdog.py';p.write_text('''import argparse,time
import service,capacity_trial
from r132_contract import read,require
p=argparse.ArgumentParser();p.add_argument('--owner',required=True);a=p.parse_args()
row=read(a.owner);owner=capacity_trial.bind_service(service.RUN)
monitor=read(service.RUN/'processes/capacity_monitor.json')
require(row==read(service.RUN/'processes/service.json'),'owner changed')
try:
 while service.current_identity(row['pid'])==row['identity']:
  if service.current_identity(monitor['pid'])!=monitor['identity']:
   capacity_trial.signal_exact(owner);break
  time.sleep(.25)
except BaseException:
 capacity_trial.signal_exact(owner);raise
''')
 source=(C/'scripts/root_run_online.py').read_text();tree=ast.parse(source);helpers='\n\n'.join(ast.get_source_segment(source,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['start_capacity_monitor','capacity_ready','finish_capacity_monitor'])
 p=d/'audit/root_run_batch.py';s=p.read_text();s=s.replace('def live_peers', 'atomic=service.write_json\n\n'+helpers+'\n\ndef live_peers',1).replace('owner=None;entry=None;peers=[]','owner=None;entry=None;peers=[];monitor=None;monitor_identity=None;capacity_result=None')
 s=s.replace("        service.write_json(ROOT/'processes/cuda_gate_go.json',ready)",'''        monitor,monitor_identity=start_capacity_monitor(owner,audit)
        capacity_ready(monitor,monitor_identity,owner,audit)
        command=['python3','-u',str(ROOT/'scripts/capacity_watchdog.py'),'--owner',str(ROOT/'processes/service.json')]
        with (audit/'capacity_watchdog.log').open('ab',buffering=0) as log:
            child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        service.write_json(ROOT/'processes/capacity_watchdog.json',{'pid':child.pid,'identity':service.bind_child(child,command)})
        service.write_json(ROOT/'processes/cuda_gate_go.json',ready)''')
 s=s.replace("        service.write_json(audit/'ROOT_EXIT_RECEIPT.json'", "        capacity_result=finish_capacity_monitor(monitor,monitor_identity);monitor=None\n        require(capacity_result['exit_code']==0,'capacity monitor failed')\n        service.write_json(audit/'CAPACITY_MONITOR_EXIT.json',capacity_result)\n        service.write_json(audit/'ROOT_EXIT_RECEIPT.json'",1)
 s=s.replace('    finally:\n        try:\n            if entry',"    finally:\n        if monitor is not None:\n            best_effort_receipt(audit/'CAPACITY_MONITOR_EXIT.json',finish_capacity_monitor(monitor,monitor_identity))\n        try:\n            if entry",1);p.write_text(s)
 # Reuse the tested integrity verifier and replace only case/parent bindings.
 s=(B/'analysis/postrun/verify_reference_origin.py').read_text()
 s=s.replace("layout['reference_origin']==4839.0 and layout['original_target_origin']>4839.0","layout['reference_origin']>0 and layout['original_target_origin']>layout['reference_origin']")
 a=s.index('def compare_prefix');b=s.index('\ndef verify',a)
 s=s[:a]+'''def compare_prefix(root,run,case,grid,seed,manifest):
 path=root/'design/parent_native_x0_manifest.json'
 if not path.exists():return {'diagnostics_complete':True,'equality_required':False,'status':'historical snapshot manifest not supplied'}
 parent=read(path)
 keys=('sigmas_video','seed','sampler','audio_scale','video_latent_scale_factor','normalization_stage','geometry','target_latent_shapes')
 require(all(parent[k]==manifest[k] for k in keys),'prefix metadata differ')
 comparisons=[{'step_zero_based':i,'streams':{k:{'actual_sha256':manifest['captures'][i][k]['sha256'],'parent_sha256':parent['captures'][i][k]['sha256'],'sha256_equal':manifest['captures'][i][k]['sha256']==parent['captures'][i][k]['sha256']} for k in ('video','audio')}} for i in range(6)]
 return {'diagnostics_complete':True,'equality_required':False,'comparison':'exact tensor SHA only; cross-host forward values may differ','comparisons':comparisons,'parent_manifest_sha256':sha(path)}

'''+s[b:]
 s=s.replace("shared=root/'audit/r132_long_0039_shared_conditioning.json'","shared=root/'audit'/(science['historical_shared_run']+'_conditioning.json')").replace("parent_path=root/'design/r122_long_0039_shared_conditioning.json'","parent_path=root/'design/conditioning.json'").replace("c['pair_snapshot']['source_run_id']=='r132_long_0039_shared'","c['pair_snapshot']['source_run_id']==science['historical_shared_run']")
 a=s.index(' condition_comparison=');b=s.index(" router_path=",a)
 s=s[:a]+''' condition_comparison={'all_original_clean_condition_metadata_equal':clean_condition(c)==clean_condition(parent)}
 checks['original_conditioning_equal']=condition_comparison['all_original_clean_condition_metadata_equal']
 cache_manifest=read(root/'configs/CONDITION_CACHE.json');blobs=[]
 records=[shared_value['native_vae_calls'][0]['latent'],shared_value['conditioning_embedding'],shared_value['token_tags'],shared_value['packed_layout']['position_ids']]
 for record,blob in zip(records,cache_manifest['tensors']):
  require(sha(root/'audit'/record['tensor_file'])==blob['sha256'],'cache file bytes changed')
  blobs.append(inspect_blob(root/'audit',record))
'''+s[b:]
 s=s.replace("'pixel_interval_inclusive':[0,105]","'pixel_interval_inclusive':[0,case['valid_frame_count']-1]")
 s=s.replace('bins=32;rows=943',"bins=route['latent_interval_half_open'][1];rows=943")
 s=s.replace("cache=root/'audit/r132_long_0039_seed2026101701_noise.pt'","cache=root/'audit'/(science['noise_pair_id']+'_noise.pt')")
 s=s.replace("parent_noise=read(root/'design/r122_long_0039_seed2026101701_native_noise.json')","parent_noise={'signature':saved['signature'],'actual_noise_streams':saved['hashes']}")
 s=s.replace("n['pair_id']=='r132_long_0039_seed2026101701'","n['pair_id']==science['noise_pair_id']")
 s=s.replace("'valid_frames':106","'valid_frames':case['valid_frame_count']").replace("'source_id':'long_0039'","'source_id':case['source_id']").replace("'evaluation_plan_sha256':science['evaluation_plan_sha256'],",'')
 s=s.replace("args.root/'analysis/postrun/long_0039/REFERENCE_ORIGIN_RUNTIME_GATE.json'", "args.root/'analysis/postrun'/SOURCES[0]/'REFERENCE_ORIGIN_RUNTIME_GATE.json'")
 (d/'analysis/postrun/verify_reference_origin.py').write_text(s)
 # Callback manifests are a passive comparison; original four cached tensors remain strict.
 if sid=='short_0252':shutil.copy2(R.parent/'h3-oxygen-generic-retention-metrics-r141b-host9-20261020/incoming/short_0252/binding_03.json',d/'design/parent_native_x0_manifest.json')
 print(sid,'finalized')
