"""Bind the new source and existing actual R26 Native evidence without any inference."""
import json
from pathlib import Path
from observer_import import t

def check(root,remote=False):
 root=Path(root);p=t.read_json(root/'configs/protocol.json');case=p['cases'][0]
 t.require(len(p['cases'])==1 and case['source_id']=='40372' and case['seed']==2026101701,'case changed')
 cap=t.read_json(root/case['parent_captures']);condition=t.read_json(root/case['parent_conditioning']);inventory=t.read_json(root/case['parent_file_inventory']);gate=t.read_json(root/'configs/parent_run_gate.json')
 t.require(gate['passed'] is True and all(gate['checks'].values()) and gate['run_id']==case['parent_run'] and gate['seed']==case['seed'],'parent actual run gate differs')
 t.require(gate['NFE']==gate['callbacks']==gate['Euler_updates']==20,'parent native counts differ')
 t.require(gate['file_inventory_sha256']==t.sha(root/case['parent_file_inventory']),'parent inventory differs')
 t.require(cap['status']=='complete' and cap['seed']==case['seed'] and cap['run_id']==case['parent_run'],'parent capture identity')
 t.require([c['step_zero_based'] for c in cap['captures']]==list(range(20)) and cap['callback_count']==20 and cap['capture_steps_zero_based']==list(range(20)),'parent21 snapshots incomplete')
 source=t.read_json(root/'configs/source.pose.json');v=source['video'];frames=source['frames']
 t.require((v['fps'],v['width'],v['height'],v['container_frame_count'])==(24,1312,736,141),'source pose geometry differs')
 t.require(len(frames)==141 and [f['frame'] for f in frames]==list(range(141)) and all(abs(f['time_s']-i/24)<1e-8 for i,f in enumerate(frames)),'source pose timebase differs')
 provenance=t.read_json(root/'configs/source_provenance.json');inputs=t.read_json(root/'configs/input_hashes.json')
 digest=inputs['source_40372_video.mp4'];t.require(source['video']['sha256']==provenance['prepared_sha256']==digest,'source pose/video binding differs')
 t.require(t.sha(root/'configs/source.pose.json')==p['observer']['source_pose_sha256'],'source pose changed')
 mapping=provenance['frame_map'];t.require(len(mapping)==141 and [r['prepared_frame'] for r in mapping]==list(range(141)) and [r['full_prepared_frame'] for r in mapping]==list(range(66,207)),'physical frame mapping differs')
 t.require(all(abs(r['prepared_time_s']-i/24)<1e-8 for i,r in enumerate(mapping)),'physical frame times differ')
 t.require(condition['packed_layout']['seq_len']==87361 and condition['conditioning_embedding']['shape']==[1,6729,5120],'actual conditioning layout changed')
 checked=[]
 if remote:
  old=Path(case['parent_root']);run=case['parent_run']
  relations={f'audit/{run}_conditioning.json':case['parent_conditioning'],f'audit/{run}_noise.json':case['parent_noise'],f'audit/x0/{run}/manifest.json':case['parent_captures']}
  for rel,local in relations.items():
   t.require(t.sha(old/rel)==t.sha(root/local)==inventory[rel]['sha256'],'actual parent metadata differs: '+rel);checked.append(rel)
  paths=['audit/'+condition['conditioning_embedding']['tensor_file']]+[f'audit/x0/{run}/'+r['file'] for r in cap['captures']+[cap['final_sampler_result']]]
  for rel in paths:
   row=inventory[rel];path=old/rel
   t.require(path.stat().st_size==row['bytes'] and t.sha(path)==row['sha256'],'actual historical file differs: '+rel);checked.append(rel)
  history=t.read_json(old/'logs'/f'{run}_history.json')
  t.require(history['status']['completed'] is True and history['status']['status_str']=='success' and history['prompt'][2]==t.read_json(root/case['parent_graph']),'actual parent history/graph differs')
 return {'passed':True,'all21_native_archived':True,'source_frame_mapping':'full66..206 -> selected0..140 at24fps','historical_actual_files_checked':checked,'actual_embedding_tensor_equal':'runtime after current conditioning; not yet measured','historical_full_postaugmentation_tree':'not available; no equality claim'}
