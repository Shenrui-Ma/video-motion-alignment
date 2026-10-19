"""Read existing local evidence; no model, tensor loading, pose or remote calls."""
import hashlib,json,time
from pathlib import Path

HERE=Path(__file__).resolve().parent
R3=Path('/Users/researcher/DevProjects/h3-timing-spatial-r3-20261016')
R25=Path('/Users/researcher/DevProjects/h3-timing-reverse-reference-r25-20261017')
B=R25/'analysis/postrun/captured/r25_s05_reverse_block_6to14'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def clean(v):
    if isinstance(v,dict):return {k:clean(x) for k,x in v.items() if k!='tensor_file'}
    if isinstance(v,list):return [clean(x) for x in v]
    return v
def main():
    evidence={};checks={};cells={}
    def bind(p):
        p=Path(p);evidence[str(p)]={'sha256':sha(p),'bytes':p.stat().st_size};return read(p)
    for label,run in [('N','r3_s05_native'),('F','r3_s05_full_6to14')]:
        folder=R3/'analysis/pose/pilot'/f'{run}_provenance'
        cell={k:bind(folder/f'{name}.json') for k,name in [('condition','conditioning'),('noise','noise'),('graph','config'),('router','router_audit'),('history','history')]}
        arc=bind(folder/'archive_manifest.json');video=R3/'analysis/pose/raw'/arc['relative_video'];pose=R3/'analysis/pose/pilot'/f'{video.stem}.pose.json'
        checks[label+'_video_hash']=sha(video)==arc['video_sha256']
        items={x['path']:x for x in arc['files']}
        checks[label+'_pose_archived_hash']=sha(pose)==items[str(pose)]['sha256']
        checks[label+'_metadata_archive_binding']=sha(folder/'config.json')==arc['config_sha256'] and sha(folder/'history.json')==arc['history_sha256']
        for x in (video,pose):evidence[str(x)]={'sha256':sha(x),'bytes':x.stat().st_size}
        cell.update(run_id=run,video=str(video),pose=str(pose));cells[label]=cell
    run='r25_s05_reverse_block_6to14'
    cells['B']={k:bind(B/name) for k,name in [('condition',f'audit/{run}_conditioning.json'),('noise',f'audit/{run}_noise.json'),('graph',f'configs/graphs/{run}.json'),('router',f'audit/router/{run}.json'),('history',f'logs/{run}_history.json')]}
    gate=bind(B/'RUN_GATE.json');inv=bind(B/'FILE_INVENTORY.json');done=bind(B/'CPU_COMPLETE.json');play=bind(B/'PLAYBACK_GATE.json')
    original_local={rel:sha(B/rel)==row['sha256'] for rel,row in inv.items() if not rel.endswith('.pt')}
    checks['B_all_original_local_nonPT_hashes']=all(original_local.values())
    checks['B_historical_actual_tensor_runtime_gate']=gate['passed'] is True and all(gate['checks'].values())
    video=B/'output'/Path(done['video']).name;pose=B/'pose'/Path(done['pose']).name
    checks['B_video_pose_hash']=sha(video)==done['video_sha256'] and sha(pose)==done['pose_sha256']
    checks['B_playback']=play['passed'] is True and play['video_sha256']==sha(video)
    cells['B'].update(run_id=run,video=str(video),pose=str(pose))
    for x in (video,pose):evidence[str(x)]={'sha256':sha(x),'bytes':x.stat().st_size}
    fields=('prompt','input_video','native_vae_calls','qwen_presentation','tokenization_before_vision_expansion','conditioning_embedding','token_tags','target_latent_shapes','packed_layout')
    pair_fields={}
    for name,cell in cells.items():
        pair_fields[name]={field:clean(cell['condition'][field])==clean(cells['N']['condition'][field]) for field in fields}
        pair_fields[name]['noise_signature']=cell['noise']['signature']==cells['N']['noise']['signature']
        pair_fields[name]['actual_noise_streams']=cell['noise']['actual_noise_streams']==cells['N']['noise']['actual_noise_streams']
        checks[name+'_actual_inputs_equal']=all(pair_fields[name].values())
        r=cell['router'];h=cell['history'];g=cell['graph']
        checks[name+'_completed_graph']=h['status']['completed'] is True and h['status']['status_str']=='success' and h['prompt'][2]==g
        checks[name+'_grid']=r['sample_sigmas']==cells['N']['router']['sample_sigmas'] and g['9']==cells['N']['graph']['9']
        checks[name+'_layout']=r['validated_layout']==cells['N']['router']['validated_layout']
        checks[name+'_blocks_forwards']=r['completed_forward_calls']==20 and r['started_calls']==r['completed_calls']==1000 and r['calls_by_forward']==[50]*20 and r['calls_by_block']==[20]*50
        checks[name+'_routing_schedule']=r['routed_calls']==(0 if name=='N' else 450) and r['routed_by_forward']==([0]*20 if name=='N' else [0]*6+[50]*9+[0]*5)
        checks[name+'_fixed_scope']=r['pixel_interval_inclusive']==[50,65] and r['step_interval_half_open']==[6,15] and r['block_interval_half_open']==[0,50] and r['alpha']==1 and r['radius']==r['time_offset']==0
    fm=bind(R25/'parent_evidence/full_x0_manifest.json');bm=bind(B/f'audit/x0/{run}/manifest.json');native=bind(R3/'analysis/pose/replication/native_replay_actual_tensors.json')
    f5=next(x for x in fm['captures'] if x['step_zero_based']==5);b5=next(x for x in bm['captures'] if x['step_zero_based']==5);n5=next(x for x in native['rows'] if x['stem']=='x0_step005')
    checks['B_F_same_capture_semantics']=all(bm[k]==fm[k] for k in ('sigmas_video','geometry','seed','audio_scale','video_latent_scale_factor','normalization_stage','expected_callback_count','callback_count'))
    checks['N_F_B_actual_prefix005_AV']=all(f5[k]==b5[k] and f5[k]['sha256']==n5['tensors'][k]['actual_sha256'][1] and n5['tensors'][k]['equal'] for k in ('video','audio'))
    checks['B_prefix_actual_not_only_manifest']=gate['checks']['independent_actual_native005_AV'] and gate['checks']['parent_Full005_native_equivalence']
    gpu=bind(R25/'audit/reverse_block_gpu_gate.json');checks['B_backend_bridge']=gpu['passed'] and gpu['actual_Comfy_native_matches_archived_Flash']
    runtime=bind(B/'configs/runtime_provenance.json');oldruntime=bind(R25/'configs/parent_runtime_provenance.json')
    checks['same_model_fingerprints']=runtime['models']==oldruntime['models']
    checks['same_official_core_recorded']=all(runtime['core_matches'].values())
    inputhash=bind(R25/'configs/input_hashes.json')
    for rel,digest in inputhash.items():
        p=R25/'inputs'/rel
        checks['local_input_'+rel]=p.exists() and sha(p)==digest
        if p.exists():evidence[str(p)]={'sha256':sha(p),'bytes':p.stat().st_size}
    scope={k:{'run_id':v['run_id'],'video':v['video'],'video_sha256':sha(v['video']),'pose':v['pose'],'pose_sha256':sha(v['pose']),'backend':v['router']['backend'],'NFE':20,'Euler_updates':20,'eligible_correction_calls':v['router']['routed_calls']} for k,v in cells.items()}
    result={'schema':'r30-existing-three-cells-readonly-audit-v1','created_unix':time.time(),'passed':all(checks.values()),'checks':checks,'input_fields':pair_fields,'cells':scope,'actual_noise':cells['N']['noise'],'source_input_hashes':inputhash,'sigma_video':cells['N']['router']['sample_sigmas'],'layout':cells['N']['router']['validated_layout'],'prefix005':{'video':f5['video'],'audio':f5['audio'],'source_scope':'historical actual tensor read/torch.equal report plus B actual runtime gate; no new tensor load'},'evidence':evidence,'B_original_local_nonPT':original_local,'historical_limits':['R3 clean condition tensor signatures are available; historical processed/postaugmentation full tree is not.','R25 B sampler_gate.actual_current_condition tree is available for a stronger B-to-FB runtime comparison, excluding only the two exact UUID leaves.','R3 used explicit Flash; B used native attention_pytorch with Flash groups. Full-size model-free backend equality and actual005 bridge passed; this does not assert all future perturbed trajectories bitwise equal.','Models are prior full SHA plus size/mtime checks; this review does not reread remote20GB model files.','Large PT remain remote; this metadata review binds existing actual tensor gates and does not rerun their computation.','A single selected development case; no population-level factorial inference.']}
    (HERE/'EXISTING_CELLS_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'failed':[k for k,v in checks.items() if not v],'files_bound':len(evidence)},indent=2))
if __name__=='__main__':main()
