"""Root-admitted standalone full90 live-decoder resource gate; zero DiT."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from observer_import import t, ROOT
from gpu_release_gate import wait_after_child

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root-admitted',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    t.require(args.root_admitted and ROOT==t.REMOTE_ROOT,'root-admitted remote gate required')
    t.require(not args.output.exists(),'refuse to overwrite gate')
    bindings=t.bindings(external=True)
    import decode_live_child as live
    admission=live.assert_idle_gpu(t.DECODER_UUID)
    import torch
    torch.set_num_threads(1)
    t.require(not torch.cuda.is_initialized(),'parent must remain CPU-only')
    sys.path.insert(0,str(ROOT/'extensions'))
    from H3X0Readout import core as reader
    case=t.read_json(ROOT/'configs/protocol.json')['cases'][0]
    geometry=t.geometry_for(case['run_id'])
    cap=t.read_json(ROOT/case['parent_captures'])
    old=cap['final_sampler_result']
    source=Path(case['parent_root'])/'audit/x0'/case['parent_run']/old['file']
    inventory=t.read_json(ROOT/case['parent_file_inventory'])
    relative=str(source.relative_to(case['parent_root']))
    t.require(t.sha(source)==inventory[relative]['sha256'],'actual Native final changed')
    payload=torch.load(source,map_location='cpu',weights_only=True)
    for key,shape in zip(('video','audio'),geometry.stream_shapes):
        t.require(tuple(payload[key].shape)==shape and reader.tensor_signature(payload[key])==old[key],'actual Native endpoint schema differs')
    owner=t.identity(os.getpid());t.require(owner is not None,'parent identity unavailable')
    directory=ROOT/'audit/observations/known_endpoint_90';directory.mkdir(parents=True,exist_ok=False)
    endpoint=ROOT/'audit/counterfactual/known_endpoint_90/native019.pt';endpoint.parent.mkdir(parents=True,exist_ok=False)
    norm=[reader.tensor_signature(payload[k]) for k in ('video','audio')]
    raw=[reader.tensor_signature(payload['video']),reader.tensor_signature(payload['audio']*4)]
    condition=t.read_json(ROOT/case['parent_conditioning']);grid=cap['sigmas_video'];n=19
    meta={'physical_index':n,'branch':'native','nfe_index':n,'seed':case['seed'],'sigma':grid[n],'sigma_next':grid[n+1],
          'condition_sha256':t.sha(ROOT/case['parent_conditioning']),
          'reference_sha256':condition['native_vae_calls'][0]['latent']['sha256'],'raw_stream_signatures':raw,
          'bridge_archived_snapshot_sha256':t.sha(source),
          'bridge_scope':'Standalone decode of final Native AV; sigma metadata only exercises request binding and makes no current forward claim'}
    torch.save({'video':payload['video'],'audio':payload['audio'],'metadata':meta},endpoint)
    request={'schema':'r27-observer-request-v1','request_id':directory.name,'run_id':case['run_id'],'parent':owner,
             'protocol_sha256':t.PROTOCOL_SHA,'bindings_sha256':t.sha(ROOT/'configs/observer_bindings.json'),
             **{k:meta[k] for k in ('physical_index','branch','nfe_index','seed','sigma','sigma_next','condition_sha256','reference_sha256')},
             'full_grid':grid,'endpoint_file':str(endpoint),'endpoint_file_sha256':t.sha(endpoint),
             'normalized_stream_signatures':norm,'raw_stream_signatures':raw,'created_unix':time.time(),
             'geometry':geometry.video_geometry,'observation_domain':geometry.domain_record}
    path=directory/'request.json';request_sha=t.write_new(path,request)
    record={'schema':'r55-full90-decoder-gate-v1','passed':False,'NFE':0,'model_forward_calls':0,
            'protocol_sha256':t.PROTOCOL_SHA,'archived_endpoint':{'file':str(source),'sha256':t.sha(source)},
            'request_sha256':request_sha,'GPU_admission':admission,
            'scope':'Exact live decoder, full90 shape and standalone peak; root separately evaluates main and isolated decoder capacity. Decode uses same90-frame Native endpoint and official VAE; no original encodedRGB equality claim.'}
    start=time.monotonic()
    env=dict(os.environ,CUDA_VISIBLE_DEVICES=t.DECODER_UUID,OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',TMPDIR=str(ROOT/'temp'),TMP=str(ROOT/'temp'),TEMP=str(ROOT/'temp'),R55_DECODER_APPROVAL_DIRECTORY=str(directory))
    try:
        command=[sys.executable,str(ROOT/'scripts/known_endpoint_decode_bridge.py'),str(endpoint),'--request',str(path),
                 '--parent-json',json.dumps(owner),'--core',bindings['comfy'],'--runtime-deps',bindings['runtime_deps'],
                 '--vae',bindings['vae'],'--expected-vae-sha256',bindings['vae_sha256'],'--gpu-uuid',t.DECODER_UUID,
                 '--output',str(directory/'native.mp4')]
        record['decoder']=t.run_child(command,env,directory,'decoder',840,owner)
        record['GPU_after_decoder']=wait_after_child(t.DECODER_UUID,record['decoder'],live.assert_idle_gpu,t.identity)
        decoded=t.read_json(directory/'native.json')
        checks={'complete':decoded['status']=='complete','shape':decoded['decoded_shape']==[90,736,1312,3],
                'full90_RGB':len(decoded['preencode_rgb24_frame_sha256'])==90,
                'fallback_forbidden':decoded['fallback_guard']['calls']==0 and bool(decoded['fallback_guard']['installed']),
                'endpoint_unchanged':t.sha(endpoint)==request['endpoint_file_sha256'],
                'request_unchanged':t.sha(path)==request_sha,'parent_CPU_only':not torch.cuda.is_initialized()}
        record.update(checks=checks,passed=all(checks.values()),decode_file=str(directory/'native.json'),decode_sha256=t.sha(directory/'native.json'),decode=decoded)
        t.require(record['passed'],'full90 decoder gate failed')
    except BaseException as error:
        record['error']=type(error).__name__+': '+str(error);raise
    finally:
        record['wall_seconds']=time.monotonic()-start
        record['source_sha256']={str(p.relative_to(ROOT)):t.sha(p) for p in (ROOT/'scripts').glob('*.py')}
        t.write_new(args.output,record)
    print(json.dumps({'passed':record['passed'],'decode_file':record['decode_file']}))

if __name__=='__main__':main()
