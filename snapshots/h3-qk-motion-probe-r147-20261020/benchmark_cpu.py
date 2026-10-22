"""Synthetic production grid, CPU-only measured cost; never loads H3 weights."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import time
import torch
from test_probe import fixture
from qk_motion_probe import QKMotionProbe

torch.set_num_threads(4)
q,k,plan,pos=fixture(bins=32,rows=23,cols=41,heads=1,dtype=torch.float32)
q=q.expand(1,32,-1,-1); k=k.expand(1,32,-1,-1)
with tempfile.TemporaryDirectory() as out:
    probe=QKMotionProbe(out,inv_freq=torch.linspace(.001,1,16),valid_frames=105)
    rows=[]
    for step in range(2):
        start=time.perf_counter()
        result=probe.observe(q,k,plan,pos,physical_step=step,pass_kind='ordinary',block_index=25)
        rows.append(dict(step=step,wall_seconds=time.perf_counter()-start,
                         payload_bytes=(Path(out)/f'step{step:03d}_block025.json').stat().st_size,
                         compute=result['timing'],bounds=result['tensor_bounds']))
    summary={'device':'CPU','torch':torch.__version__,'threads':torch.get_num_threads(),
             'cuda_initialized':torch.cuda.is_initialized(),'synthetic_only':True,
             'model_forward_count':0,'vae_forward_count':0,'geometry':[32,23,41],
             'actual_head_count':32,'selected_head_indices':result['head_indices'],'synthetic_head_storage':'one head expanded for CPU allocation bound','selected_heads':4,'head_dim':128,'rows':rows}
    print(json.dumps(summary,indent=2))
