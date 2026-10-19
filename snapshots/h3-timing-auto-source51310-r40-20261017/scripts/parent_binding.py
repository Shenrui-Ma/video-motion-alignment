"""Read actual R38 source51310 archives; never infer absent historical trees."""
from pathlib import Path
from observer_import import t

def check(root,remote=False):
 root=Path(root);p=t.read_json(root/'configs/protocol.json');case=p['cases'][0]
 t.require(len(p['cases'])==1 and case['source_id']=='51310' and case['seed']==2026101701,'case changed')
 run=case['parent_run'];cap=t.read_json(root/case['parent_captures']);condition=t.read_json(root/case['parent_conditioning']);inventory=t.read_json(root/case['parent_file_inventory'])
 gate=t.read_json(root/'configs/parent_run_gate.json');runtime=t.read_json(root/'configs/parent_runtime_gate.json');history=t.read_json(root/'configs/parent_history.json');router=t.read_json(root/'configs/parent_router.json')
 t.require(gate['passed'] is True and run in gate['runs'] and all(runtime['checks'].values()),'parent actual gates failed')
 t.require(gate['file_inventory_sha256']==t.sha(root/case['parent_file_inventory']) and gate['runtime_gate_sha256']==t.sha(root/'configs/parent_runtime_gate.json'),'parent gate binding differs')
 count=runtime['runs'][run]
 t.require(count['NFE']==count['callback_count']==count['Euler_updates']==20,'parent native counts differ')
 t.require(router['completed_forward_calls']==20 and router['completed_calls']==1000 and router['routed_calls']==0 and router['calls_by_forward']==[50]*20,'parent native block counters differ')
 t.require(history['status']['completed'] is True and history['status']['status_str']=='success' and history['prompt'][2]==t.read_json(root/case['parent_graph']),'parent actual graph/history differs')
 t.require(cap['status']=='complete' and cap['seed']==case['seed'] and cap['run_id']==run and cap['callback_count']==20,'parent capture identity')
 t.require([c['step_zero_based'] for c in cap['captures']]==list(range(20)) and cap['capture_steps_zero_based']==list(range(20)),'parent21 snapshots incomplete')
 expected={str(Path(row['file']).relative_to(case['parent_root'])):{'bytes':row['bytes'],'sha256':row['sha256']} for row in count['snapshots']}
 t.require(len(expected)==21 and all(inventory[k]==v for k,v in expected.items()),'parent tensor inventory differs')
 source=t.read_json(root/'configs/source.pose.json');v=source['video'];frames=source['frames']
 t.require((v['fps'],v['width'],v['height'],v['container_frame_count'])==(24,1312,736,141),'source pose geometry differs')
 t.require(len(frames)==141 and [f['frame'] for f in frames]==list(range(141)) and all(abs(f['time_s']-i/24)<1e-8 for i,f in enumerate(frames)),'source pose timebase differs')
 provenance=t.read_json(root/'configs/source_provenance.json');inputs=t.read_json(root/'configs/input_hashes.json')
 t.require(v['sha256']==provenance['prepared_sha256']==inputs['source_51310_video.mp4'],'source pose/video binding differs')
 t.require(t.sha(root/'configs/source.pose.json')==p['observer']['source_pose_sha256'],'source pose changed')
 times=provenance['probe']['frames'];t.require(len(times)==141 and all(abs(float(row['best_effort_timestamp_time'])-i/24)<1e-6 for i,row in enumerate(times)),'prepared video PTS differs')
 selection=provenance['source_selection'];t.require(selection['id']=='51310' and selection['source_only_start_seconds']==0 and selection['output_frame_range_inclusive']==[0,140] and selection['output_fps']==24,'source selection mapping differs')
 t.require(condition['packed_layout']['seq_len']==87361 and condition['conditioning_embedding']['shape']==[1,6729,5120],'actual conditioning layout changed')
 embedding='audit/'+condition['conditioning_embedding']['tensor_file'];t.require(inventory[embedding]['bytes']==137811656,'historical embedding entity inventory absent')
 relations={f'configs/graphs/{run}.json':case['parent_graph'],f'audit/{run}_conditioning.json':case['parent_conditioning'],f'audit/{run}_noise.json':case['parent_noise'],f'audit/x0/{run}/manifest.json':case['parent_captures'],f'logs/{run}_history.json':'configs/parent_history.json',f'audit/router/{run}.json':'configs/parent_router.json'}
 for rel,local in relations.items():t.require(t.sha(root/local)==inventory[rel]['sha256'],'copied parent evidence differs: '+rel)
 checked=[]
 if remote:
  old=Path(case['parent_root'])
  for rel,local in relations.items():t.require(t.sha(old/rel)==t.sha(root/local),'actual parent metadata differs: '+rel);checked.append(rel)
  for rel in [embedding,*expected]:
   row=inventory[rel];path=old/rel
   t.require(path.stat().st_size==row['bytes'] and t.sha(path)==row['sha256'],'actual historical file differs: '+rel);checked.append(rel)
 return {'passed':True,'available_native_indices':list(range(20)),'all21_native_archived':True,'source_frame_mapping':'prepared0..140 at24fps; exact raw video/PTS preserved','historical_actual_files_checked':checked,'actual_embedding_tensor_equal':'runtime after current conditioning; not yet measured','historical_full_postaugmentation_tree_and_raw_sampler_inputs':'not available; no equality claim'}
