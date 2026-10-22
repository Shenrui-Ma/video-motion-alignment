"""Four native VAE decodes for known codec-residual controls. Root launches CUDA."""
import argparse
import gc
import json
import os
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parent
PARENT = ROOT.parents[1]
sys.path.insert(0, str(PARENT / 'scripts'))
from common import sha, write, require, tensor_signature, write_frames
import run_operator as runtime
import compensation


def verify_file(path, expected):
    require(sha(path) == expected, 'bound file SHA ' + str(path))


def inputs():
    import torch
    config = json.loads((ROOT / 'contract.json').read_text())
    for name, digest in config['parent_files_sha256'].items():
        verify_file(PARENT / name, digest)
    for item in json.loads((ROOT / 'FREEZE.json').read_text())['files']:
        verify_file(ROOT / item['file'], item['sha256'])
    result = json.loads((PARENT / 'outputs/attempt1/RESULT.json').read_text())
    receipt = json.loads((PARENT / 'audit/root_control_attempt1/ROOT_EXIT_RECEIPT.json').read_text())
    require(result['status'] == 'complete' and result['vae_encode_calls'] == 3 and result['vae_decode_calls'] == 6
        and result['fallback_guard']['calls'] == 0, 'actual parent VAE operations complete')
    require(receipt['passed'] and receipt['process_absent'] and receipt['CUDA_allocation_absent']
        and receipt['pid'] == result['pid'], 'actual parent root release')
    import frozen_x0_reader as reader
    import frozen_capture_core as capture
    payload = reader.load_snapshot(PARENT / 'inputs/x0_step006.pt', capture)
    require(payload['metadata']['step_zero_based'] == 6 and payload['metadata']['normalization_stage'] == 'after_process_latent_out'
        and payload['metadata']['video']['sha256'] == config['input_x0_raw_sha256'], 'same original normalized x0')
    z = payload['video']
    encoded = {}
    for name, signature in config['encoded_signatures'].items():
        encoded[name] = torch.load(PARENT / 'outputs/attempt1' / (name + '_encoded.pt'), map_location='cpu', weights_only=True)
        require(tensor_signature(encoded[name]) == signature, 'actual encoded latent signature ' + name)
    compensation.check_latents(z, *encoded.values())
    import operators
    mapping = json.loads((PARENT / 'inputs/OFFLINE_DEVELOPMENT_MAPPING.json').read_text())
    maps = operators.make_maps([x['native_index'] for x in mapping['mapping']])
    coordinates = {}
    for name, phi in maps.items():
        coordinates[name] = json.loads((PARENT / 'outputs/attempt1' / (name + '_coordinates.json')).read_text())
        require(coordinates[name] == operators.coordinates(phi), 'same frozen coordinates ' + name)
    return config, z, encoded, coordinates


def root_gate(control, gpu, config, output):
    require(control is not None, 'root ready/go directory required')
    control.mkdir(parents=True, exist_ok=False)
    ready = {'schema': 'r70-codec-residual-preCUDA-v1', 'identity': runtime.process_identity(),
        'gpu_uuid': gpu, 'CUDA_started': False, 'output': str(output),
        'freeze_sha256': sha(ROOT / 'FREEZE.json'), 'parent_freeze_sha256': sha(PARENT / 'FREEZE.json'),
        'contract_sha256': sha(ROOT / 'contract.json'), 'parent_files_sha256': config['parent_files_sha256'],
        'required_free_mib': config['required_free_mib']}
    write(control / 'ready.json', ready)
    print(json.dumps({'ready': str(control / 'ready.json'), 'identity': ready['identity']}), flush=True)
    deadline = time.monotonic() + 600
    while not (control / 'go.json').exists():
        require(runtime.process_identity() == ready['identity'], 'process identity changed')
        require(time.monotonic() < deadline, 'root registration timed out')
        time.sleep(.2)
    require(json.loads((control / 'go.json').read_text()) == ready, 'exact ready/go match')
    require(runtime.process_identity() == ready['identity'] and sha(ROOT / 'FREEZE.json') == ready['freeze_sha256'], 'identity/freeze changed')
    return ready


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--gpu-uuid')
    parser.add_argument('--control', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    require(args.validate_only != args.execute, 'choose CPU validate or root execute')
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    import torch
    torch.set_num_threads(2)
    require(not torch.cuda.is_initialized(), 'CUDA not initialized before registration')
    config, z, encoded, coordinates = inputs()
    parent_config, validated_z, _ = runtime.validate()
    require(torch.equal(z, validated_z), 'same parent input x0')
    del validated_z
    plans = []
    for mapping, mode in config['order']:
        value = compensation.apply(z, encoded['identity'], encoded[mapping], coordinates[mapping], mode)
        plans.append((mapping, mode, value, tensor_signature(value)))
    if args.validate_only:
        runtime.install_runtime(parent_config, cpu=True)
        require(not torch.cuda.is_initialized(), 'CPU actual runtime startup')
        print(json.dumps({'status': 'CPU_VALIDATED', 'CUDA_initialized': False,
            'freeze_sha256': sha(ROOT / 'FREEZE.json'), 'torch': torch.__version__,
            'input_x0_signature': tensor_signature(z), 'plans': [{'mapping':m,'mode':a,'signature':s} for m,a,v,s in plans]}))
        return
    require(args.gpu_uuid == config['gpu_uuid'], 'exact approved UUID')
    require(args.output is not None and not args.output.exists(), 'new output directory')
    args.output.mkdir(parents=True)
    record = {'schema':'r70-known-codec-residual-result-v1','status':'waiting_for_root',
        'pid':os.getpid(),'uid':os.getuid(),'started_unix':time.time(),
        'contract_sha256':sha(ROOT/'contract.json'),'input_x0_signature':tensor_signature(z),
        'scope':config['scope'],'model_forward_calls':0,'vae_encode_calls':0,'vae_decode_calls':0,
        'operations':[],'products':{},'ancestry':config['ancestry']}
    write(args.output/'RESULT.json',record)
    vae = state = frames = manager = None
    try:
        record['root_gate'] = root_gate(args.control,args.gpu_uuid,config,args.output)
        record['gpu_admission'] = [runtime.admission(args.gpu_uuid,config['required_free_mib'])]
        os.environ['CUDA_VISIBLE_DEVICES']=args.gpu_uuid
        sd, utils, manager = runtime.install_runtime(parent_config,cpu=False)
        record['gpu_admission'].append(runtime.admission(args.gpu_uuid,config['required_free_mib']))
        guard=runtime.install_fallback_guard(sd.VAE)
        record['fallback_guard']=guard
        require(torch.cuda.device_count()==1,'one exact visible GPU')
        torch.cuda.reset_peak_memory_stats()
        state, metadata=utils.load_torch_file(parent_config['vae'],return_metadata=True)
        vae=sd.VAE(sd=state,metadata=metadata,dtype=torch.float16);vae.throw_exception_if_invalid()
        require(type(vae.first_stage_model).__name__=='MiniMaxH3VideoVAE' and vae.latent_channels==24,'native H3 VAE')
        state=None;record['status']='running'
        for mapping, mode, value, signature in plans:
            name=mapping+'_'+mode
            latent_path=args.output/(name+'.pt');torch.save(value,latent_path)
            torch.cuda.synchronize();started=time.monotonic()
            with torch.inference_mode():frames=vae.decode(value)
            torch.cuda.synchronize()
            if frames.ndim==5:frames=frames.flatten(0,1)
            frames=frames.detach().cpu().contiguous()
            require(tuple(frames.shape)==tuple(config['geometry']) and frames.dtype==torch.float32,'decoded RGB shape/dtype')
            record['vae_decode_calls']+=1
            record['operations'].append({'name':name,'kind':'decode','seconds':time.monotonic()-started,
                'input_signature':signature,'input_file_sha256':sha(latent_path),'decoded_signature':tensor_signature(frames),
                'max_memory_allocated_bytes':torch.cuda.max_memory_allocated(),
                'max_memory_reserved_bytes':torch.cuda.max_memory_reserved()})
            write(args.output/'RESULT.json',record)
            record['products'][name]=write_frames(frames,range(158),24,args.output/(name+'.mp4'))
            frames=None;gc.collect();write(args.output/'RESULT.json',record)
        require(record['vae_decode_calls']==4 and guard['calls']==0,'four native decodes without fallback')
        record['status']='complete'
    except BaseException as error:
        record['status']='failed';record['error']=f'{type(error).__name__}: {error}';raise
    finally:
        if torch.cuda.is_initialized():
            record['max_memory_allocated_bytes']=torch.cuda.max_memory_allocated()
            record['max_memory_reserved_bytes']=torch.cuda.max_memory_reserved()
        vae=state=frames=None
        try:
            if manager is not None:manager.unload_all_models();gc.collect();manager.soft_empty_cache()
        except BaseException as error:
            record['cleanup_error']=f'{type(error).__name__}: {error}'
            if record['status']=='complete':record['status']='failed_cleanup'
        record['finished_unix']=time.time();record['wall_seconds']=record['finished_unix']-record['started_unix']
        write(args.output/'RESULT.json',record)
    require(record['status']=='complete','failure retained')
    print(json.dumps({'status':'complete','result':str(args.output/'RESULT.json')}))

if __name__=='__main__':main()
