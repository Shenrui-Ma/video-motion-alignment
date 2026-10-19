"""Independent, zero-DiT admission measurement; sealed operator stays unchanged."""
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/data5/researcher/h3_runs/timing_auto_fresh_r28_20261017')
UUID = 'GPU-REDACTED'
assert os.environ.get('CUDA_VISIBLE_DEVICES') == UUID
assert not subprocess.check_output(['nvidia-smi', '--id='+UUID, '--query-compute-apps=pid', '--format=csv,noheader,nounits'], text=True).strip()
import torch
torch.set_num_threads(1)
sys.path.insert(0, str(ROOT/'extensions'))
from H3TemporalRouter import core
from H3TemporalRouter.mask import QueryGain

output_path = ROOT/'audit/root_allocator_profile.json'
assert not output_path.exists()
metadata = json.loads((ROOT/'configs/parent_conditioning.json').read_text())
segments = metadata['packed_layout']['segments']
ref = [s for s in segments if s[2]=='ref_img' and s[1]-s[0]==42*943]
target = [s for s in segments if s[2]=='video']
assert len(ref)==len(target)==1
n = metadata['packed_layout']['seq_len']
plan = {'seq_len':n, 'frame_rows':943, 'latent_interval_half_open':[0,42],
        'query_interval_half_open':target[0][:2], 'reference_video_segment':ref[0][:2]}
generator = torch.Generator(device='cuda').manual_seed(26101616)
packed = torch.randn(1,n,3,56,128,device='cuda',dtype=torch.bfloat16,generator=generator)
q,k,v = packed.permute(2,0,3,1,4).unbind(0)
gain = QueryGain(torch.ones((42,23,41)), (42,23,41))

def digest():
    h=hashlib.sha256()
    for start in range(0,n,512):
        h.update(packed[:,start:start+512].cpu().view(torch.uint8).numpy().tobytes())
    return h.hexdigest()

def memory():
    torch.cuda.synchronize()
    return {'allocated_bytes':torch.cuda.memory_allocated(), 'reserved_bytes':torch.cuda.memory_reserved(),
            'gpu_csv':subprocess.check_output(['nvidia-smi','--id='+UUID,'--query-gpu=uuid,memory.total,memory.free','--format=csv,noheader,nounits'],text=True).strip()}

before_hash=digest(); rng=torch.cuda.get_rng_state().clone(); version=packed._version
stages=[]
for mode in ['native','mass_preserve','native','mass_preserve','native']:
    before=memory(); torch.cuda.reset_peak_memory_stats(); started=time.monotonic()
    out=core.route_attention(q,k,v,56,plan,mode=mode,query_gain=gain)
    torch.cuda.synchronize()
    peak={'allocated_bytes':torch.cuda.max_memory_allocated(),'reserved_bytes':torch.cuda.max_memory_reserved()}
    del out
    gc.collect()
    stages.append({'mode':mode,'before':before,'peak':peak,'after_release':memory(),'seconds':time.monotonic()-started})
after_hash=digest()
checks={'QKV_exact':before_hash==after_hash,'tensor_version_unchanged':version==packed._version,
        'CUDA_RNG_exact':torch.equal(rng,torch.cuda.get_rng_state())}
del q,k,v,packed,gain
gc.collect()
record={'schema':'r28-root-allocator-profile-v1','passed':all(checks.values()),'checks':checks,
        'NFE':0,'model_weights_loaded':False,'shape':[1,56,n,128],'plan':plan,
        'stages':stages,'idle_after_input_release':memory(),'input_sha256':before_hash,
        'native_to_full_reserved_increment_bytes':max(x['peak']['reserved_bytes'] for x in stages)-stages[0]['after_release']['reserved_bytes'],
        'no_empty_cache_called':True,'no_simultaneous_oracle_output':True,
        'operator_sha256':hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest(),
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope':'Same actual QKV layout through Native/Full/Native allocator lifecycle. Combined real model occupancy remains guarded at every decoder admission.'}
output_path.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
assert record['passed']
