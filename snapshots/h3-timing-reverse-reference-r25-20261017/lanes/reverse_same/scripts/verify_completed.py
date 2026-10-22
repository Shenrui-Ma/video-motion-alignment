"""Actual four-job paired integrity gate; CPU only. Motion quality is separate."""
import argparse,json,os,sys
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extensions'))
from H3X0Readout.core import tensor_signature
from r25_contract import read,sha as digest,registry,validate_job
from preflight import check
CAPTURES=(5,6,7,8,9,10,15,19)
SHAPES = {'video':(1,24,42,46,82), 'audio':(1,32,2,235)}

def signature(tensor):
    if not isinstance(tensor,torch.Tensor) or tensor.device.type != 'cpu' or not bool(torch.isfinite(tensor).all()):
        raise ValueError('invalid/nonfinite CPU tensor')
    return tensor_signature(tensor)

def safe_file(root, name):
    path=Path(name)
    if path.is_absolute() or '..' in path.parts or (root/path).is_symlink() or not (root/path).resolve().is_relative_to(root.resolve()):
        raise ValueError('unsafe archive file: '+name)
    return root/path

def checked_snapshot(folder, record, run_id):
    path=safe_file(folder,record['file'])
    if Path(record['file']).name != record['file']:
        raise ValueError('snapshot filename must be one component')
    value=torch.load(path,map_location='cpu',weights_only=True)
    if set(value) != {'video','audio','metadata'}:
        raise ValueError('unexpected snapshot schema')
    metadata={k:v for k,v in record.items() if k not in ('file','capture_seconds')}
    if value['metadata'] != metadata or metadata['run_id'] != run_id:
        raise ValueError('snapshot metadata/manifest/run mismatch')
    for key,shape in SHAPES.items():
        if tuple(value[key].shape) != shape or value[key].dtype != torch.float32 or signature(value[key]) != record[key]:
            raise ValueError('snapshot actual tensor signature mismatch: '+key)
    return value, {'file':str(path), 'bytes':path.stat().st_size,'sha256':digest(path)}

def expected_routing(full):
    return [0]*6+[50 if full else 0]*9+[0]*5

def check_record_semantics(record, seed):
    expected={'seed':seed,'geometry':{'width':1312,'height':736,'frames':141,'fps':24},
              'normalization_stage':'after_process_latent_out','audio_scale':4,
              'video_latent_scale_factor':1,'total_steps':20,'schema':'h3-x0-readout-v1'}
    if any(record.get(k)!=v for k,v in expected.items()):
        raise ValueError('snapshot per-record frozen semantics mismatch')

def inspect_capture(folder, run_id, grid, seed):
    m=read(folder/'manifest.json')
    if (m['status']!='complete' or m['callback_count']!=20 or m['expected_callback_count']!=20 or
            m['run_id']!=run_id or m['capture_steps_zero_based']!=list(CAPTURES) or
            [r['step_zero_based'] for r in m['captures']]!=list(CAPTURES) or
            m['sigmas_video']!=grid or m['seed']!=seed or m['sampler']!='sample_euler' or
            m['audio_scale']!=4 or m['video_latent_scale_factor']!=1 or
            m['normalization_stage']!='after_process_latent_out' or
            m['geometry']!={'width':1312,'height':736,'frames':141,'fps':24} or
            m['target_latent_shapes'] != [list(SHAPES[k]) for k in ('video','audio')]):
        raise ValueError('capture run/geometry/count/sigma/normalization gate failed: '+run_id)
    if any(r['snapshot_kind']!='x0_estimate' for r in m['captures']):
        raise ValueError('wrong intermediate snapshot kind')
    final=m['final_sampler_result']
    if final['snapshot_kind']!='sampler_final' or final['sigma_video']!=0.0 or final['sigma_audio']!=0.0 or final['step_zero_based']!=19:
        raise ValueError('wrong final snapshot semantics')
    records=m['captures']+[final]
    names=[r['file'] for r in records]
    expected=[f'x0_step{i:03d}.pt' for i in CAPTURES]+['sampler_final.pt']
    if names!=expected or sorted(p.name for p in folder.glob('*.pt'))!=sorted(expected):
        raise ValueError('missing/extra/duplicated actual endpoint inventory')
    files=[];prefix=None
    for r in records:
        check_record_semantics(r,seed)
        value,inventory=checked_snapshot(folder,r,run_id);files.append(inventory)
        if r['file']=='x0_step005.pt':prefix=value
        if r['snapshot_kind']=='x0_estimate':
            i=r['step_zero_based']; sv=grid[i]
            if (r['sigma_video']!=sv or r['sigma_next_video']!=grid[i+1] or
                    r['model_call_one_based']!=i+1 or r['sigma_audio']!=sv/(4-3*sv)):
                raise ValueError('snapshot sigma/index mismatch')
    return m,files,prefix

def inspect_blob(root,record):
    path=safe_file(root,record['tensor_file'])
    value=torch.load(path,map_location='cpu',weights_only=True)
    expected={k:record[k] for k in ('shape','dtype','sha256')}
    # EventAudit signatures have exactly these three fields; x0 adds no assumption.
    got=signature(value)
    if {k:got[k] for k in expected} != expected:
        raise ValueError('actual condition tensor blob mismatch: '+str(path))
    return {'file':str(path),'sha256':digest(path),'tensor_signature':expected}

def verify(root,output,parent_root):
 torch.set_num_threads(1);root=Path(root).resolve();parent_root=Path(parent_root).resolve();jobs,order=registry(root)
 if len(order)!=1:raise ValueError('exact one run required')
 run=order[0];row=validate_job(run,root);arm=row['arm'];graph=read(root/'configs/graphs'/f'{run}.json');grid=torch.tensor([float(x) for x in graph['9']['inputs']['sigmas'].split(',')],dtype=torch.float32).tolist()
 result={'static':check(root),'checks':{},'run':run,'arm':arm,'files':[]};checks=result['checks'];owner=read(root/'processes/service.json')
 hist=read(root/'logs'/f'{run}_history.json');job=read(root/'logs'/f'{run}_job.json')
 checks['actual_completed_graph']=(hist['status']['completed'] is True and hist['status']['status_str']=='success' and hist['prompt'][2]==graph and hist['prompt'][1]==job['prompt_id'])
 checks['actual_owner']=(job['status']=='success' and job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'] and job['graph_sha256']==row['graph_sha256'])
 c=read(root/'audit'/f'{run}_conditioning.json');n=read(root/'audit'/f'{run}_noise.json');oldc=read(root/'parent_evidence/full_6to14_conditioning.json');oldn=read(root/'parent_evidence/full_6to14_noise.json')
 shared=root/'audit'/f"{graph['5']['inputs']['run_id']}_conditioning.json"
 checks['actual_shared_condition']=(c['run_id']==run and c['pair_snapshot']['verified'] is True and c['pair_snapshot']['source_manifest_sha256']==digest(shared))
 checks['historical_clean_inputs']=(c['pair_snapshot']['actual']==oldc['pair_snapshot']['actual'] and c['input_video']==oldc['input_video'] and len(c['native_vae_calls'])==len(oldc['native_vae_calls'])==2 and all({k:a[key][k] for k in ('shape','dtype','sha256')}=={k:b[key][k] for k in ('shape','dtype','sha256')} for a,b in zip(c['native_vae_calls'],oldc['native_vae_calls']) for key in ('prepared_frames','latent')))
 seen=set();condition_files=[]
 def visit(value):
  if isinstance(value,dict):
   if 'tensor_file' in value and {'shape','dtype','sha256'}<=set(value) and value['tensor_file'] not in seen:
    seen.add(value['tensor_file']);condition_files.append(inspect_blob(root/'audit',value))
   for v in value.values():visit(v)
  elif isinstance(value,list):
   for v in value:visit(v)
 visit(read(shared));result['actual_condition_files']=condition_files
 pair=graph['6']['inputs']['pair_id'];cache=root/'audit'/f'{pair}_noise.pt';saved=torch.load(cache,map_location='cpu',weights_only=True);actual=[{k:signature(t)[k] for k in ('shape','dtype','sha256')} for t in saved['tensors']]
 checks['actual_old_noise']=(n['run_id']==run and n['pair_id']==pair and saved['signature']==n['signature']==oldn['signature'] and saved['hashes']==actual==n['actual_noise_streams']==oldn['actual_noise_streams'])
 router=read(root/'audit/router'/f'{run}.json');expect={'run_id':run,'status':'complete','mode':arm,'alpha':1.,'radius':0,'time_offset':0,'block_interval_half_open':[0,50],'step_interval_half_open':[6,15],'pixel_interval_inclusive':[50,65],'started_calls':1000,'completed_calls':1000,'completed_forward_calls':20,'native_override_calls':1000,'routed_calls':450,'direct_native_calls':550,'calls_by_forward':[50]*20,'calls_by_block':[20]*50,'routed_by_forward':[0]*6+[50]*9+[0]*5,'routed_by_block':[9]*50,'sample_sigmas':grid,'expected_sampling_steps':20,'callback_count':20,'aux_attention_calls':900 if arm=='reverse_block' else 1350}
 checks['actual20_forwards_counts']=all(router.get(k)==v for k,v in expect.items())
 plan=router['validated_layout'];seq=c['packed_layout']['seq_len'];checks['actual_packed_layout']=(router['first_attention']['qkv_shape']==[1,56,seq,128] and plan['seq_len']==seq and [list(x) for x in plan['segments']]==c['packed_layout']['segments'] and plan['reference_video_segment']==[7910,47516] and plan['target_video_segment']==[47986,87592] and plan['key_interval_half_open']==[21112,26770] and plan['frame_rows']==943 and plan['latent_interval_half_open']==[14,20])
 first=router['first_active_call'];checks['first_reference_only']=(first['forward_index']==6 and first['block']==0 and all(first[k] is True for k in ('nonselected_rows_bitwise','target_video_bitwise','target_audio_bitwise','input_values_bitwise','finite')) and first['reference_query_interval']==[21112,26770] and first['target_key_interval']==[47986,87592] and first['nonzero_correction_required'] is False)
 recon=first['native_group_reconstruction'];checks['group_reconstruction_tolerance']=(recon['sample_relative_rms']<=.025 and recon['sample_maxabs_scaled']<=.035)
 summaries=router['forward_summaries'];checks['complete_layer_statistics']=(len(summaries)==20 and all(x['forward_index']==i and x['completed_blocks']==50 and x['routed_blocks']==(50 if 6<=i<15 else 0) and len(x['layer_stats'])==(50 if 6<=i<15 else 0) and x['sampled_finite'] is True and all(z['finite'] is True and 0<=z['target_mass_min']<=z['target_mass_max']<=1 for z in x['layer_stats']) for i,x in enumerate(summaries)))
 gate=router['sampler_gate'];checks['sampler_callback_causality']=(gate['status']=='complete' and gate['condition_noise_rng_unchanged'] is True and gate['sigmas']==grid and gate['seed']==2026101311 and len(gate['callback_records'])==20 and all(x['index']==i and x['completed_NFE']==i+1 and x['completed_blocks']==50*(i+1) for i,x in enumerate(gate['callback_records'])))
 # Independent postrun prefix proof: load both actual files, bind parent manifest,
 # and compare both normalized AV tensors. Runtime boolean alone is insufficient.
 m,files,prefix=inspect_capture(root/'audit/x0'/run,run,grid,2026101311);result['files']+=files
 parent_manifest=read(root/'parent_evidence/full_x0_manifest.json');parent_run=parent_manifest['run_id'];parent_folder=parent_root/'audit/x0'/parent_run
 if read(parent_folder/'manifest.json')!=parent_manifest:raise ValueError('actual archived parent manifest differs from sealed copy')
 p_record=next(x for x in parent_manifest['captures'] if x['step_zero_based']==5)
 parent,inventory=checked_snapshot(parent_folder,p_record,parent_run);result['parent_prefix_file']=inventory
 checks['independent_actual_native005_AV']=all(torch.equal(prefix[k],parent[k]) for k in ('video','audio'))
 expected={k:p_record[k] for k in ('video','audio')};checks['runtime_prefix_guard_binding']=(gate['prefix005']['passed'] is True and gate['prefix005']['actual']==gate['prefix005']['expected']==expected)
 native005=next(x for x in read(root/'parent_evidence/native_replay_actual_tensors.json')['rows'] if x['stem']=='x0_step005')
 checks['parent_Full005_native_equivalence']=all(native005['tensors'][k]['equal'] is True and native005['tensors'][k]['actual_sha256'][1]==p_record[k]['sha256'] for k in ('video','audio'))
 feature_files=[];captures=router['native_feature_captures'];feature_dir=root/'audit/native_features'/run
 checks['feature_capture_inventory']=(len(captures)==3 and sorted(p.name for p in feature_dir.glob('*.pt'))==[f'block25_step{i:03d}.pt' for i in (6,10,14)])
 for item,index in zip(captures,(6,10,14)):
  path=feature_dir/f'block25_step{index:03d}.pt'
  if digest(path)!=item['sha256'] or path.stat().st_size!=item['bytes']:raise ValueError('feature file SHA mismatch')
  value=torch.load(path,map_location='cpu',weights_only=True);meta=value['metadata']
  if (meta!=item['metadata'] or meta['run_id']!=run or meta['mode']!=arm or meta['forward_index']!=index or meta['block_index']!=25 or meta['sampler_sigma_video']!=grid[index] or meta['head_indices']!=[0,14,28,42] or meta['grid']!=[42,23,41] or meta['layout']!=plan):raise ValueError('feature provenance mismatch')
  for name in ('reference','target'):
   if value[name].shape!=(1,4,42,23,41,128) or value[name].dtype!=torch.bfloat16 or signature(value[name])!=meta['tensors'][name]:raise ValueError('feature tensor mismatch')
  feature_files.append({'file':str(path),'sha256':digest(path),'bytes':path.stat().st_size})
 result['contextual_feature_files']=feature_files
 provenance=read(root/'configs/runtime_provenance.json');checks['actual_backend_core_models']=(all(provenance['core_matches'].values()) and all(v['size_mtime_match'] and v['prior_full_sha256']==read(root/'configs/model_hashes_host9.json')[k]['sha256'] for k,v in provenance['models'].items()) and all(digest(root/p)==h for p,h in provenance['code'].items()))
 controller=read(root/'logs/controller_state.json');checks['queue_completed']=controller.get('completed')==[run] and controller.get('current') is None and controller['status'] in ('resident_hold','final_close','bounded_idle_expired')
 cleanup_path=root/'processes/cleanup.json'
 if cleanup_path.exists():
  cleanup=read(cleanup_path);checks['exact_cleanup']=cleanup['service_record']==owner and cleanup['process_absent'] is True and cleanup['own_compute_absent'] is True;result['service_state']='cleanup recorded; live ownership confirmation is root responsibility'
 else:
  checks['deliberate_resident_hold']=controller['status']=='resident_hold' and controller['residency']['service']['pid']==owner['pid'] and controller['residency']['service']['identity']==owner['identity'];result['service_state']='bounded retained service, not cleanup claim'
 result.update(passed=all(checks.values()),NFE=20,Euler_updates=20,callbacks=20,efficiency={'job_wall_seconds':job['observed_unix']-job['submitted_unix'],'sampler_seconds':gate['sampler_wall_seconds'],'first_attention_plus_audit_seconds':first['attention_plus_full_audit_seconds'],'first_audit_snapshot_bytes':first['snapshot_tensor_bytes'],'capture_seconds':sum(x['capture_seconds'] for x in m['captures']),'peak_allocated_bytes':gate.get('memory_peak_allocated_bytes'),'peak_reserved_bytes':gate.get('memory_peak_reserved_bytes')},limitations=['Mechanism diagnostic only; no quality or novelty claim.','Historical processed/postaugmentation condition tree unavailable: clean condition/noise/code/seed and independent actual005 AV prefix are the evidence.','First attention row preservation is same-call numerical evidence; block25 snapshots are contextual, not an extra next-layer native replay.','SAME mass preservation is the ideal algebra; native SDPA versus Flash group reconstruction has bounded numeric tolerance.','Target audio remains in BLOCK; this does not isolate all generated information.','No wrong-time matched sparse control.'])
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--parent-root',type=Path,default=Path('/data5/researcher/h3_runs/timing_spatial_r3_20261016'));p.add_argument('--output',required=True,type=Path);a=p.parse_args();r=verify(a.root,a.output,a.parent_root);print(json.dumps({'passed':r['passed'],'checks':r['checks']}));raise SystemExit(0 if r['passed'] else 1)
