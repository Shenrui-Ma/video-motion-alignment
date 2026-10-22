"""Two-source single-seed Native-screen integrity gate; CPU only. Motion quality is separate."""
import argparse,json,os,sys
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extensions'))
from H3X0Readout.core import tensor_signature,SCHEMA
from r54_contract import read,sha as digest,registry,validate_job,SOURCES,GEOMETRY,SHAPES
from preflight import check
CAPTURES=tuple(range(20))

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

def inspect_capture(folder, run_id, grid, seed):
    m=read(folder/'manifest.json')
    if (m.get('schema')!=SCHEMA or m['status']!='complete' or m['callback_count']!=20 or m['expected_callback_count']!=20 or
            m['run_id']!=run_id or m['capture_steps_zero_based']!=list(CAPTURES) or
            [r['step_zero_based'] for r in m['captures']]!=list(CAPTURES) or
            m['sigmas_video']!=grid or m['seed']!=seed or m['sampler']!='sample_euler' or
            m['audio_scale']!=4 or m['video_latent_scale_factor']!=1 or
            m['normalization_stage']!='after_process_latent_out' or
            m['geometry']!=GEOMETRY or
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
        if r.get('schema')!=SCHEMA or any(r.get(k)!=m[k] for k in ('seed','geometry','normalization_stage','audio_scale','video_latent_scale_factor')) or r.get('total_steps')!=20:
            raise ValueError('snapshot semantic metadata differs from frozen manifest')
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

def condition_files(value):
    # Each source has its own manifest; content-addressed blobs may be shared.
    found=set()
    def visit(v):
        if isinstance(v,dict):
            if 'tensor_file' in v:
                if not {'shape','dtype','sha256'}<=set(v):raise ValueError('incomplete condition signature')
                found.add(v['tensor_file'])
            for z in v.values():visit(z)
        elif isinstance(v,list):
            for z in v:visit(z)
    visit(value)
    if len(found)!=6:raise ValueError('expected6 actual single-video condition blobs per source')
    return sorted(found)

def verify(root,output):
 torch.set_num_threads(1);root=Path(root).resolve();jobs,order=registry(root)
 result={'static':check(root),'checks':{},'runs':{},'condition_tensor_files':[]};checks=result['checks'];owner=read(root/'processes/service.json');prefixes={};conds={};noises={};cached={};grids={};seen=set()
 for run in order:
  row=validate_job(run,root);case=row['case'];seed=row['seed'];full=False;g=read(root/'configs/graphs'/f'{run}.json');grid=torch.tensor([float(x) for x in g['9']['inputs']['sigmas'].split(',')],dtype=torch.float32).tolist();grids[run]=grid
  hist=read(root/'logs'/f'{run}_history.json');job=read(root/'logs'/f'{run}_job.json')
  checks[run+'_history']=(hist['status']['completed'] is True and hist['status']['status_str']=='success' and hist['prompt'][2]==g and hist['prompt'][1]==job['prompt_id'] and job['status']=='success' and job['name']==run)
  checks[run+'_service']=(job['status']=='success' and job['service_pid']==owner['pid'] and job['service_identity']==owner['identity'] and job['graph_sha256']==row['graph_sha256'])
  c=read(root/'audit'/f'{run}_conditioning.json');n=read(root/'audit'/f'{run}_noise.json');conds[run]=c;noises[run]=n
  shared=root/'audit'/('r54_'+case['source_id']+'_shared_conditioning.json')
  checks[run+'_actual_shared_cond']=(c['run_id']==run and c['pair_snapshot']['verified'] is True and c['pair_snapshot']['source_manifest_sha256']==digest(shared))
  def visit(value):
   if isinstance(value,dict):
    if 'tensor_file' in value and {'shape','dtype','sha256'}<=set(value) and value['tensor_file'] not in seen:
     seen.add(value['tensor_file']);result['condition_tensor_files'].append(inspect_blob(root/'audit',value))
    for v in value.values():visit(v)
   elif isinstance(value,list):
    for v in value:visit(v)
  shared_value=read(shared)
  checks[run+'_actual_embedding_stored']='tensor_file' in shared_value['conditioning_embedding']
  visit(shared_value)
  router=read(root/'audit/router'/f'{run}.json');expect={'run_id':run,'mode':'mass_preserve' if full else 'native','alpha':1.,'radius':0,'time_offset':0,'block_interval_half_open':[0,50],'step_interval_half_open':[0,20],'pixel_interval_inclusive':[0,89],'started_calls':1000,'completed_calls':1000,'completed_forward_calls':20,'native_override_calls':1000,'routed_calls':450 if full else 0,'calls_by_forward':[50]*20,'calls_by_block':[20]*50,'routed_by_forward':expected_routing(full),'routed_by_block':[9 if full else 0]*50,'sample_sigmas':grid,'expected_sampling_steps':20}
  checks[run+'_20_actual_forwards']=all(router.get(k)==v for k,v in expect.items())
  seq=c['packed_layout']['seq_len'];plan=router['validated_layout']
  checks[run+'_actual_layout']=(router['first_attention']['qkv_shape']==[1,56,seq,128] and router['first_attention']['heads']==56 and plan['seq_len']==seq and [list(x) for x in plan['segments']]==c['packed_layout']['segments'] and plan['pixel_interval_inclusive']==[0,89] and plan['frame_rows']==943 and plan['latent_interval_half_open']==[0,27] and plan['query_interval_half_open']==plan['target_video_segment'] and plan['key_interval_half_open']==plan['reference_video_segment'])
  checks[run+'_finite']=all(x.get('sampled_finite',True) for x in router['forward_summaries'])
  m,files,prefix=inspect_capture(root/'audit/x0'/run,run,grid,seed);prefixes[run]=prefix
  pair=('r54_'+case['source_id']+'_seed'+str(seed));cache=root/'audit'/f'{pair}_noise.pt';saved=torch.load(cache,map_location='cpu',weights_only=True);actual=[{k:signature(t)[k] for k in ('shape','dtype','sha256')} for t in saved['tensors']];cached[run]=saved
  checks[run+'_actual_noise']=(n['run_id']==run and n['pair_id']==pair and n['signature']['seed']==seed and len(actual)==2 and saved['signature']==n['signature'] and saved['hashes']==actual==n['actual_noise_streams'])
  events=hist['status'].get('messages',[]);cache_events=[x for x in events if x[0]=='execution_cached']
  result['runs'][run]={'historical_prefix_bridges':'not available for new source; current all21 AV tensors retained','snapshots':files,'NFE':20,'callback_count':20,'Euler_updates':20,'actual_20Euler_evidence':'success of frozen Euler20 graph plus callbacks and actual block counters','job_wall_seconds':job['observed_unix']-job['submitted_unix'],'capture_seconds_20_intermediates':sum(x['capture_seconds'] for x in m['captures']),'additional_16_captures_vs_R24_seconds':sum(x['capture_seconds'] for x in m['captures'] if x['step_zero_based'] not in (5,10,15,19)),'final_capture_cost':'included in total job time; inherited recorder does not separately time final','capture_file_bytes':sum(x['bytes'] for x in files),'execution_cached_events':cache_events,'loaded_model_residency':'see resources/residency; cache events alone do not prove all tensors stayed on GPU'}
 checks['five_predeclared_sources']=[jobs[x]['case']['source_id'] for x in order]==list(SOURCES)
 checks['one_fixed_seed']=[jobs[x]['seed'] for x in order]==[2026101701]*len(SOURCES)
 checks['actual_frozen_prompts']=all(conds[x]['prompt']==jobs[x]['case']['prompt'] for x in order)
 checks['actual_per_source_condition_storage']=all(condition_files(conds[x]) for x in order)
 checks['same_shape_seed_actual_AV_noise']=all(torch.equal(a,b) for run in order[1:] for a,b in zip(cached[order[0]]['tensors'],cached[run]['tensors']))
 controller=read(root/'logs/controller_state.json');checks['queue_completed']=controller.get('completed')==order and controller.get('current') is None and controller['status'] in ('resident_hold','final_close','bounded_idle_expired')
 cleanup_path=root/'processes/cleanup.json'
 if cleanup_path.exists():
  cleanup=read(cleanup_path);checks['exact_cleanup']=(cleanup['pid']==owner['pid'] and cleanup['service_record']==owner and cleanup['process_absent'] is True and cleanup['own_compute_absent'] is True);result['service_state']='cleanup recorded; live root confirmation still required'
 else:
  checks['deliberate_resident_hold']=controller['status']=='resident_hold' and controller['residency']['service']['pid']==owner['pid'] and controller['residency']['service']['identity']==owner['identity'];result['service_state']='retained after batch per user request; not a cleanup claim'
 result.update(passed=all(checks.values()),limitations=['No quality conclusion. Source-only pose and generated pose remain separate.','New source has no old actual prefix. Current clean conditioning tensors and both noise streams are archived; the full processed/postaugmentation condition tree is not archived. Future controls require same seed/input/core and actual available prefix AV bridges.','20 Euler updates supported by executed frozen graph+20 callbacks+1000blocks, not CPU manual loop.','No old source07 timing/seq_len/source tensor comparison.'])
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',required=True,type=Path);a=p.parse_args();r=verify(a.root,a.output);print(json.dumps({'passed':r['passed'],'checks':r['checks']}));raise SystemExit(0 if r['passed'] else 1)
