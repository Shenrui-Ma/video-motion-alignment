"""Root-only, zero-DiT measurement of actual R50 attention allocator retention.

Measures Native/Full/Native without simultaneous oracle outputs. It does not
certify model co-residency, replace the 12 GiB admission, or alter inference.
"""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

UUID = 'GPU-REDACTED'
PROTOCOL_SHA = '9eabab0ea6ad9533711ac640a13ba0bfaacd806c1792516c2b8d289165760e5d'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--root-admitted', action='store_true')
    parser.add_argument('--all-cases', action='store_true', help='Default selects actual largest sequence; all cases preserves production order.')
    args = parser.parse_args()
    root = args.root.resolve()
    if not args.root_admitted or os.environ.get('CUDA_VISIBLE_DEVICES') != UUID:
        raise RuntimeError('requires root admission and exact GPU3 UUID')
    if args.output.exists():
        raise FileExistsError(args.output)
    if sha(root/'configs/protocol.json') != PROTOCOL_SHA:
        raise RuntimeError('actual parent protocol changed')
    pending = subprocess.check_output(['nvidia-smi', '--id='+UUID, '--query-compute-apps=pid', '--format=csv,noheader,nounits'], text=True).strip()
    if pending:
        raise RuntimeError('selected GPU has compute processes: '+pending)
    protocol = json.loads((root/'configs/protocol.json').read_text())
    plans = []
    for case in protocol['cases']:
        metadata_path = root/case['parent_conditioning']
        metadata = json.loads(metadata_path.read_text())
        segments = metadata['packed_layout']['segments']
        refs = [s for s in segments if s[2]=='ref_img' and s[1]-s[0]==47*864]
        target = [s for s in segments if s[2]=='video']
        if len(refs)!=1 or len(target)!=1 or target[0][1]-target[0][0]!=47*864:
            raise ValueError('ambiguous actual 158-frame layout')
        plans.append({'run_id':case['run_id'], 'parent_conditioning_sha256':sha(metadata_path),
                      'plan':{'seq_len':metadata['packed_layout']['seq_len'], 'frame_rows':864,
                              'latent_interval_half_open':[0,47], 'query_interval_half_open':target[0][:2],
                              'reference_video_segment':refs[0][:2]}})
    selected = plans if args.all_cases else [max(plans, key=lambda p:p['plan']['seq_len'])]
    import torch
    torch.set_num_threads(1)
    if not torch.cuda.is_available() or torch.cuda.device_count()!=1:
        raise RuntimeError('requires one visible CUDA device')
    sys.path.insert(0,str(root/'extensions'))
    from H3TemporalRouter import core
    from H3TemporalRouter.mask import QueryGain
    def memory():
        torch.cuda.synchronize()
        csv = subprocess.check_output(['nvidia-smi','--id='+UUID,'--query-gpu=uuid,memory.total,memory.free','--format=csv,noheader,nounits'],text=True).strip()
        fields = [v.strip() for v in csv.split(',')]
        return {'allocated_bytes':torch.cuda.memory_allocated(), 'reserved_bytes':torch.cuda.memory_reserved(),
                'nvml_total_bytes':int(fields[1])*1048576, 'nvml_free_bytes':int(fields[2])*1048576,
                'gpu_csv':csv}
    records=[]
    for item in selected:
        plan=item['plan']; n=plan['seq_len']
        generator=torch.Generator(device='cuda').manual_seed(26101616)
        packed=torch.randn(1,n,3,56,128,device='cuda',dtype=torch.bfloat16,generator=generator)
        q,k,v=packed.permute(2,0,3,1,4).unbind(0)
        gain=QueryGain(torch.ones((47,24,36)),(47,24,36))
        def digest():
            h=hashlib.sha256()
            for start in range(0,n,512):
                h.update(packed[:,start:start+512].cpu().view(torch.uint8).numpy().tobytes())
            return h.hexdigest()
        before_hash=digest(); rng=torch.cuda.get_rng_state().clone(); version=packed._version
        stages=[]
        for mode in ['native','mass_preserve','native','mass_preserve','native']:
            before=memory(); torch.cuda.reset_peak_memory_stats(); started=time.monotonic()
            out=core.route_attention(q,k,v,56,plan,mode=mode,query_gain=gain)
            torch.cuda.synchronize()
            peak={'allocated_bytes':torch.cuda.max_memory_allocated(),'reserved_bytes':torch.cuda.max_memory_reserved()}
            during=memory()
            del out
            gc.collect()
            stages.append({'mode':mode,'before':before,'peak':peak,'output_alive':during,
                           'after_release':memory(),'seconds':time.monotonic()-started})
        after_hash=digest()
        checks={'QKV_exact':before_hash==after_hash,'tensor_version_unchanged':version==packed._version,
                'CUDA_RNG_exact':torch.equal(rng,torch.cuda.get_rng_state())}
        native=stages[0]['after_release']
        reserved_delta=max(x['peak']['reserved_bytes'] for x in stages)-native['reserved_bytes']
        nvml_delta=native['nvml_free_bytes']-min(x['after_release']['nvml_free_bytes'] for x in stages)
        del q,k,v,packed,gain,rng,generator
        gc.collect()
        records.append({**item,'checks':checks,'passed':all(checks.values()),'shape':[1,56,n,128],
                        'stages':stages,'input_sha256':before_hash,'idle_after_input_release':memory(),
                        'native_to_full_reserved_increment_bytes':reserved_delta,
                        'native_to_full_nvml_retained_increment_bytes':nvml_delta})
    record={'schema':'r50-root-allocator-profile-158-v1','passed':all(c['passed'] for c in records),
            'pid':os.getpid(),'protocol_sha256':PROTOCOL_SHA,'all_actual_plans':plans,'cases':records,
            'selection':'all_actual_cases' if args.all_cases else 'largest_actual_sequence',
            'NFE':0,'model_weights_loaded':False,'no_empty_cache_called':True,'no_simultaneous_oracle_output':True,
            'operator_sha256':sha(Path(core.__file__)),'script_sha256':sha(Path(__file__)),
            'torch':torch.__version__,'cuda':torch.version.cuda,
            'scope':'Attention allocator retention only. Real model callback residency remains unmeasured; mandatory per-decoder 12 GiB admission is unchanged. A sampled GPU peak is not a proven upper bound.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as handle:
        handle.write(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record))
    if not record['passed']:
        raise SystemExit(1)

if __name__=='__main__':
    main()
