"""Actual H3 head geometry and noncontiguous QKV Flash compatibility."""
from pathlib import Path
import sys,json,socket
import torch
import torch.nn.functional as F
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extensions'))
from H3TemporalRouter.core import flash_attention_lse,route_attention
torch.manual_seed(261016)
packed=torch.randn(1,97,3,56,128,device='cuda',dtype=torch.bfloat16)
q,k,v=[packed[:,:,i].transpose(1,2) for i in range(3)]
out,lse=flash_attention_lse(q,k,v)
with torch.nn.attention.sdpa_kernel(torch.nn.attention.SDPBackend.FLASH_ATTENTION):
    expected=F.scaled_dot_product_attention(q,k,v)
assert torch.equal(out,expected),'native Flash differs from forced SDPA Flash'
plan={'reference_video_segment':[5,37],'query_interval_half_open':[53,69],
      'latent_interval_half_open':[1,3],'frame_rows':8}
for mode in ['mass_preserve','hard_route']:
    changed=route_attention(q,k,v,56,plan,mode=mode)
    native=out.transpose(1,2).reshape(1,97,56*128)
    assert torch.equal(changed[:,:53],native[:,:53])
    assert torch.equal(changed[:,69:],native[:,69:])
    assert torch.isfinite(changed).all()
report={'host':socket.gethostname(),'torch':torch.__version__,'device':torch.cuda.get_device_name(),
        'q_shape':list(q.shape),'q_stride':list(q.stride()),'q_contiguous':q.is_contiguous(),
        'flash_equals_sdpa_bitwise':True,'lse_shape':list(lse.shape),'finite_and_outside_query_identity':True}
print(json.dumps(report,indent=2))
