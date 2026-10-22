"""Registered source-clip single-seed integrity gate; CPU only. Motion quality is separate."""
import argparse,json,os,sys
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
import torch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'extensions'))
from H3X0Readout.core import tensor_signature,SCHEMA
from r122_contract import read,sha as digest,registry,validate_job,SOURCES,geometry,latent_shapes
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

def checked_snapshot(folder, record, run_id, shapes):
    path=safe_file(folder,record['file'])
    if Path(record['file']).name != record['file']:
        raise ValueError('snapshot filename must be one component')
    value=torch.load(path,map_location='cpu',weights_only=True)
    if set(value) != {'video','audio','metadata'}:
        raise ValueError('unexpected snapshot schema')
    metadata={k:v for k,v in record.items() if k not in ('file','capture_seconds')}
    if value['metadata'] != metadata or metadata['run_id'] != run_id:
        raise ValueError('snapshot metadata/manifest/run mismatch')
    for key,shape in shapes.items():
        if tuple(value[key].shape) != shape or value[key].dtype != torch.float32 or signature(value[key]) != record[key]:
            raise ValueError('snapshot actual tensor signature mismatch: '+key)
    return value, {'file':str(path), 'bytes':path.stat().st_size,'sha256':digest(path)}

def expected_routing(full):
    return [0]*6+[50 if full else 0]*9+[0]*5

def inspect_capture(folder, run_id, grid, seed, case):
    shapes=latent_shapes(case)
    m=read(folder/'manifest.json')
    if (m.get('schema')!=SCHEMA or m['status']!='complete' or m['callback_count']!=20 or m['expected_callback_count']!=20 or
            m['run_id']!=run_id or m['capture_steps_zero_based']!=list(CAPTURES) or
            [r['step_zero_based'] for r in m['captures']]!=list(CAPTURES) or
            m['sigmas_video']!=grid or m['seed']!=seed or m['sampler']!='sample_euler' or
            m['audio_scale']!=4 or m['video_latent_scale_factor']!=1 or
            m['normalization_stage']!='after_process_latent_out' or
            m['geometry']!=geometry(case) or
            m['target_latent_shapes'] != [list(shapes[k]) for k in ('video','audio')]):
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
        value,inventory=checked_snapshot(folder,r,run_id,shapes);files.append(inventory)
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
