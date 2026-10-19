"""Root-admitted known Native010 -> exact live VAE -> CPU pose/scan gate; 0 DiT."""
import argparse,json,os,sys,time
from pathlib import Path
from observer_import import t,ROOT
from bridge_values import pose_values,scan_values,digest
from gpu_release_gate import wait_after_child

def main():
    p=argparse.ArgumentParser();p.add_argument('--root-admitted',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    t.require(a.root_admitted and ROOT==t.REMOTE_ROOT,'root-admitted formal remote bridge only')
    t.require(not a.output.exists(),'refusing to overwrite gate evidence')
    b=t.bindings(external=True);prior=t.read_json(ROOT/'configs/bridge_decode.json')
    import decode_live_child as live
    admission=live.assert_idle_gpu(t.DECODER_UUID)
    import torch
    torch.set_num_threads(1)
    t.require(not torch.cuda.is_initialized(),'bridge parent must remain CPU-only')
    sys.path.insert(0,str(ROOT/'extensions'))
    from H3X0Readout import core as reader
    from decode_x0 import load_snapshot
    source=Path(prior['snapshot']);t.require(t.sha(source)==prior['snapshot_sha256'],'archived endpoint changed')
    payload=load_snapshot(source,reader)
    normal=t.read_json(ROOT/'configs/normal_captures.json');n=10;grid=normal['sigmas_video'];owner=t.identity(os.getpid())
    t.require(owner is not None,'bridge parent identity unavailable')
    directory=ROOT/'audit/observations/known_endpoint_bridge';directory.mkdir(parents=True,exist_ok=False)
    endpoint=ROOT/'audit/counterfactual/known_endpoint_bridge/native010.pt';endpoint.parent.mkdir(parents=True,exist_ok=False)
    norm=[reader.tensor_signature(payload[k]) for k in ('video','audio')]
    raw=[reader.tensor_signature(payload['video']),reader.tensor_signature(payload['audio']*4)]
    # No claim of an archived full processed conditioning tree: it was not saved.
    condition=t.sha(ROOT/'configs/normal_conditioning.json')
    clean=t.read_json(ROOT/'configs/normal_conditioning.json')['native_vae_calls'][1]['latent']['sha256']
    meta={'physical_index':n,'branch':'native','nfe_index':n,'seed':2026101313,'sigma':grid[n],'sigma_next':grid[n+1],
          'condition_sha256':condition,'reference_sha256':clean,'raw_stream_signatures':raw,
          'bridge_archived_snapshot_sha256':prior['snapshot_sha256'],
          'bridge_condition_scope':'historical clean producer manifest only; not post-augmentation tree'}
    torch.save({'video':payload['video'],'audio':payload['audio'],'metadata':meta},endpoint)
    r={'schema':'r27-observer-request-v1','request_id':directory.name,'run_id':'r27_s05_normal1313_auto','parent':owner,
       'protocol_sha256':t.PROTOCOL_SHA,'bindings_sha256':t.sha(ROOT/'configs/observer_bindings.json'),
       **{k:meta[k] for k in ('physical_index','branch','nfe_index','seed','sigma','sigma_next','condition_sha256','reference_sha256')},
       'full_grid':grid,'endpoint_file':str(endpoint),'endpoint_file_sha256':t.sha(endpoint),
       'normalized_stream_signatures':norm,'raw_stream_signatures':raw,'created_unix':time.time()}
    request=directory/'request.json';t.write_new(request,r);start=time.monotonic()
    record={'schema':'r27-known-endpoint-gate-v1','passed':False,'NFE':0,'model_forward_calls':0,
            'protocol_sha256':t.PROTOCOL_SHA,'archived_endpoint':{'file':str(source),'sha256':t.sha(source),'normalized_stream_signatures':norm},
            'request_sha256':t.sha(request),'GPU_admission':admission,
            'scope':'exact live decoder request/normalization/VAE/writer and pose child; idle admission substituted only; residency not tested'}
    env=dict(os.environ,CUDA_VISIBLE_DEVICES=t.DECODER_UUID,OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')
    try:
        args=[sys.executable,str(ROOT/'scripts/known_endpoint_decode_bridge.py'),str(endpoint),'--request',str(request),'--parent-json',json.dumps(owner),'--core',b['comfy'],'--runtime-deps',b['runtime_deps'],'--vae',b['vae'],'--expected-vae-sha256',b['vae_sha256'],'--gpu-uuid',t.DECODER_UUID,'--output',str(directory/'native.mp4')]
        record['decoder']=t.run_child(args,env,directory,'decoder',180,owner)
        record['GPU_after_decoder']=wait_after_child(t.DECODER_UUID,record['decoder'],live.assert_idle_gpu,t.identity)
        env['CUDA_VISIBLE_DEVICES']=''
        record['pose_process']=t.run_child([sys.executable,str(ROOT/'scripts/pose_live_child.py'),'--request',str(request),'--parent-json',json.dumps(owner)],env,directory,'pose',840,owner)
        decoded=t.read_json(directory/'native.json');pose=t.read_json(directory/'pose/native.pose.json');scan=t.read_json(directory/'observer.json')
        keys=('decoded_shape','decoded_dtype','decoded_tensor_sha256','preencode_rgb24_sha256','preencode_rgb24_frame_sha256','output_sha256')
        checks={k:decoded[k]==prior[k] for k in keys}
        checks.update(fallback_forbidden=decoded['fallback_guard']['calls']==0 and bool(decoded['fallback_guard']['installed']),
            exact_pose_values=pose_values(pose)==pose_values(t.read_json(ROOT/'configs/bridge_pose.json')),
            exact_scan_values=scan_values(scan)==t.read_json(ROOT/'configs/bridge_expected_scan_values.json'),
            endpoint_unchanged=t.sha(endpoint)==r['endpoint_file_sha256'],request_unchanged=t.sha(request)==record['request_sha256'],
            parent_cuda_uninitialized=not torch.cuda.is_initialized())
        record.update(checks=checks,passed=all(checks.values()),numeric={'decode':{k:decoded[k] for k in keys},
            'pose_values_sha256':digest(pose_values(pose)),'scan_values_sha256':digest(scan_values(scan))},
            artifacts={k:{'file':str(v),'sha256':t.sha(v)} for k,v in {'decode':directory/'native.json','pose':directory/'pose/native.pose.json','scan':directory/'observer.json'}.items()})
        t.require(record['passed'],'known endpoint exact bridge failed')
    except BaseException as error:
        record['error']=type(error).__name__+': '+str(error);raise
    finally:
        record['wall_seconds']=time.monotonic()-start
        record['source_sha256']={str(q.relative_to(ROOT)):t.sha(q) for q in (ROOT/'scripts').glob('*.py')}
        t.write_new(a.output,record)
    print(json.dumps(record))
if __name__=='__main__':main()
