"""Root-only readout smoke on one admitted idle CUDA GPU; no model load."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import torch
from torch.nn.attention import SDPBackend,sdpa_kernel
from component_probe import component_probe

parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
assert not args.output.exists()
assert torch.cuda.is_available() and torch.cuda.device_count()==1
gen=torch.Generator(device='cuda').manual_seed(26101604)
packed=torch.randn(1,87592,3,56,128,generator=gen,device='cuda',dtype=torch.bfloat16)
q,k,v=packed.permute(2,0,3,1,4).unbind(0)
saved=packed.clone()
plan={'reference_video_segment':[7910,47516],'query_interval_half_open':[61188,66846],
      'latent_interval_half_open':[14,20],'frame_rows':943,'seq_len':87592,
      'signature':[1,42,46,82]}
with sdpa_kernel(SDPBackend.FLASH_ATTENTION):before=torch.nn.functional.scaled_dot_product_attention(q,k,v)
cpu_rng=torch.get_rng_state().clone();gpu_rng=torch.cuda.get_rng_state().clone()
torch.cuda.synchronize();torch.cuda.reset_peak_memory_stats();start=time.monotonic()
r=component_probe(q,k,v,plan)
torch.cuda.synchronize();elapsed=time.monotonic()-start
checks={'input_unchanged':torch.equal(saved.view(torch.uint8),packed.view(torch.uint8)),
        'cpu_rng_unchanged':torch.equal(cpu_rng,torch.get_rng_state()),
        'cuda_rng_unchanged':torch.equal(gpu_rng,torch.cuda.get_rng_state()),'finite':r['finite']}
with sdpa_kernel(SDPBackend.FLASH_ATTENTION):after=torch.nn.functional.scaled_dot_product_attention(q,k,v)
checks['output_bitwise_unchanged']=torch.equal(before.contiguous().view(torch.uint8),after.contiguous().view(torch.uint8))
report={'schema':'actual-shape-passive-component-probe-smoke-v1','torch':torch.__version__,
        'device':torch.cuda.get_device_name(0),'seconds':elapsed,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
        'probe_sha256':hashlib.sha256(Path(__file__).with_name('component_probe.py').read_bytes()).hexdigest(),
        'checks':checks,'passed':all(checks.values()),'probe':r}
args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
raise SystemExit(0 if report['passed'] else 1)
