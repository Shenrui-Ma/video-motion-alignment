"""Cap this worker's CUDA allocator before normal Comfy startup."""
import json,runpy,sys
from pathlib import Path
import torch
root=Path(__file__).resolve().parents[1]
policy=json.loads((root/'shared_gpu_authorization.json').read_text())
cap=int(policy['torch_allocator_cap_gib']*1024**3)
free,total=torch.cuda.mem_get_info(0)
assert free >= cap + 6*1024**3, 'GPU memory changed below bounded shared admission'
torch.cuda.set_per_process_memory_fraction(cap/total,0)
print(json.dumps({'torch_allocator_cap_bytes':cap,'free_at_start':free,'total_bytes':total,'mode':'cpu_weight_offload'}),flush=True)
from allocator_memory_budget import install as install_allocator_budget
install_allocator_budget(torch,cap)
print("H3_ALLOCATOR_AWARE_MEMORY=enabled",flush=True)
sys.argv=sys.argv[1:]
runpy.run_path(sys.argv[0],run_name='__main__')
