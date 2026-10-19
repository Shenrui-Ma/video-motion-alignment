"""Bind actual R20 host9 source07 evidence; missing old entities stay unavailable."""
from pathlib import Path
from observer_import import t

def check(root,remote=False):
 root=Path(root);p=t.read_json(root/'configs/protocol.json');case=p['cases'][0]
 t.require(len(p['cases'])==1 and case['source_id']=='07_real_ary_v' and case['seed']==2026101311,'case changed')
 cap=t.read_json(root/case['parent_captures']);condition=t.read_json(root/case['parent_conditioning']);inventory=t.read_json(root/case['parent_file_inventory']);gate=t.read_json(root/'configs/parent_run_gate.json')
 t.require(gate['passed'] is True and all(gate['checks'].values()),'parent actual pair gate failed')
 run=case['parent_run'];counts=gate['runs'][run]
 t.require(counts['NFE']==counts['callback_count']==counts['Euler_updates']==20 and counts['routed_calls']==0,'parent native counts differ')
 t.require(counts['manifest_sha256']==t.sha(root/case['parent_captures']),'parent manifest differs')
 t.require(cap['status']=='complete' and cap['seed']==case['seed'] and cap['run_id']==run,'parent capture identity')
 t.require([c['step_zero_based'] for c in cap['captures']]==[5,10,15,19] and cap['callback_count']==20 and cap['capture_steps_zero_based']==[5,10,15,19],'parent available snapshots differ')
 expected={str(Path(row['file']).relative_to(case['parent_root'])):{'bytes':row['bytes'],'sha256':row['sha256']} for row in counts['files']}
 t.require(len(expected)==5 and all(inventory[k]==v for k,v in expected.items()),'parent tensor inventory differs')
 source=t.read_json(root/'configs/source.pose.json');v=source['video'];frames=source['frames']
 t.require((v['fps'],v['width'],v['height'],v['container_frame_count'])==(24,1312,736,141),'source pose geometry differs')
 t.require(len(frames)==141 and [f['frame'] for f in frames]==list(range(141)) and all(abs(f['time_s']-i/24)<1e-8 for i,f in enumerate(frames)),'source pose timebase differs')
 provenance=t.read_json(root/'configs/source_provenance.json');inputs=t.read_json(root/'configs/input_hashes.json')
 t.require(v['sha256']==provenance['prepared_sha256']==inputs['07_real_ary_v.mp4'],'source pose/video binding differs')
 t.require(t.sha(root/'configs/source.pose.json')==p['observer']['source_pose_sha256'],'source pose changed')
 mapping=provenance['frame_map'];t.require(len(mapping)==141 and [r['prepared_frame'] for r in mapping]==list(range(141)) and [r['input_frame'] for r in mapping]==list(range(141)),'physical frame mapping differs')
 t.require(all(abs(r['prepared_time_s']-i/24)<1e-8 for i,r in enumerate(mapping)),'physical times differ')
 t.require(condition['packed_layout']['seq_len']==87592 and condition['conditioning_embedding']['shape']==[1,6960,5120],'actual conditioning layout changed')
 t.require('tensor_file' not in condition['conditioning_embedding'],'historical entity contract changed; review required')
 checked=[]
 if remote:
  old=Path(case['parent_root'])
  relations={f'configs/{run}.json':case['parent_graph'],f'audit/{run}_conditioning.json':case['parent_conditioning'],f'audit/{run}_noise.json':case['parent_noise'],f'audit/x0/{run}/manifest.json':case['parent_captures']}
  for rel,local in relations.items():
   t.require(t.sha(old/rel)==t.sha(root/local)==inventory[rel]['sha256'],'actual parent metadata differs: '+rel);checked.append(rel)
  t.require(t.sha(old/'audit/completed_pair_gate.json')==t.sha(root/'configs/parent_run_gate.json'),'actual completed pair gate changed')
  for rel,row in expected.items():
   path=old/rel;t.require(path.stat().st_size==row['bytes'] and t.sha(path)==row['sha256'],'historical file differs: '+rel);checked.append(rel)
  history=t.read_json(old/'logs'/f'{run}_history.json')
  t.require(t.sha(old/'logs'/f'{run}_history.json')==counts['history_sha256'] and history['status']['completed'] is True and history['status']['status_str']=='success' and history['prompt'][2]==t.read_json(root/case['parent_graph']),'actual parent history/graph differs')
 return {'passed':True,'available_native_indices':[5,10,15,19],'source_frame_mapping':'unchanged input0..140 at24fps','historical_actual_files_checked':checked,'actual_embedding_signature_equal':'runtime original clean embedding; not yet measured','historical_embedding_entity_and_full_processed_tree':'unavailable; no tensor-equality claim','prefix_early_ON':'never postpone; unavailable bridge if firstON<5'}
