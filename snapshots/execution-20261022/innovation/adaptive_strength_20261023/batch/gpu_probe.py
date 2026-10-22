"""Bounded Flash Attention integration probe; never loads H3 weights."""
import json
import time
import torch
from feature_guidance.attention import FeatureConfig, feature_attention
from feature_guidance.frozen import load_frozen

torch.cuda.set_per_process_memory_fraction(.025)
core = load_frozen().core
plan = {'reference_video_segment': (2,104), 'target_video_segment': (106,208),
        'query_interval_half_open': (106,191), 'latent_interval_half_open': (0,5),
        'frame_rows': 17, 'seq_len': 212}
rows = []
for dtype in (torch.float16, torch.bfloat16):
    q,k,v=[torch.randn(1,8,212,128,device='cuda',dtype=dtype) for _ in range(3)]
    for mode in ('fixed','dynamic_strength_dof','heads_budget'):
        audit = {}
        start=time.monotonic()
        out=feature_attention(q,k,v,8,plan,attention=core.flash_attention_lse,
            aligned_attention=core._aligned_attention,config=FeatureConfig(mode=mode),diagnostics=audit)
        torch.cuda.synchronize()
        assert torch.isfinite(out).all()
        if mode == 'fixed':
            oracle=core.route_attention(q,k,v,8,plan,mode='mass_preserve',alpha=.25)
            assert torch.equal(out,oracle), 'fixed path differs from frozen Flash path'
        if mode == 'heads_budget':
            torch.testing.assert_close(audit['applied_energy'], .25**2*audit['correction_energy'],
                                       atol=1e-6,rtol=5e-6)
        alpha=audit['alpha']
        assert (alpha>=0).all() and (alpha<=.5).all()
        rows.append({'mode':mode,'dtype':str(dtype),'alpha_mean':float(alpha.mean()),
                     'alpha_min':float(alpha.min()),'alpha_max':float(alpha.max()),
                     'attention_calls':audit['attention_calls'],
                     'seconds':time.monotonic()-start, 'finite':True})
print(json.dumps({'passed':True,'probe_only':True,'model_loaded':False,'torch':torch.__version__,
                  'gpu':torch.cuda.get_device_name(),'peak_bytes':torch.cuda.max_memory_allocated(),
                  'rows':rows}))
