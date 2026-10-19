"""Sparse passive FP32 readouts of actual Q/K/V; never edits model tensors.

These are dense FP32 estimates on selected queries/heads, not measurements of
the BF16 kernel's exact correction. No model call, random sampling, or full N²
attention matrix is used. Install only in a new isolated runtime.
"""
import math


def component_probe(q, k, v, plan, *, max_heads=8, max_spatial=8, chunk_size=4096):
    import torch

    ra, rb = plan['reference_video_segment']
    qa, qb = plan['query_interval_half_open']
    lo, hi = plan['latent_interval_half_open']
    spatial_count = plan['frame_rows']
    times = (rb - ra) // spatial_count
    if q.shape != k.shape or q.shape != v.shape or q.shape[0] != 1:
        raise ValueError('Expected matching single-batch self-attention Q/K/V')
    if (rb-ra) % spatial_count or qb-qa != (hi-lo)*spatial_count:
        raise ValueError('Complete matching temporal bins required')
    if not 0 <= lo < hi <= times or not 0 <= ra < rb <= q.shape[-2]:
        raise ValueError('Invalid packed reference interval')
    if not 0 <= qa < qb <= q.shape[-2] or min(max_heads, max_spatial, chunk_size) < 1:
        raise ValueError('Invalid query interval or probe bound')
    heads = list(range(0, q.shape[1], max(1, math.ceil(q.shape[1]/max_heads))))[:max_heads]
    signature = plan.get('signature')
    if signature is not None:
        rows, cols = signature[2]//2, signature[3]//2
        if rows*cols != spatial_count:
            raise ValueError('Spatial grid disagrees with packed frame size')
        points = sorted({max(0,min(rows-1,rows//2+dr))*cols + max(0,min(cols-1,cols//2+dc))
                         for dr,dc in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1))})[:max_spatial]
    else:
        points = list(range(min(max_spatial,spatial_count)))
    query_ids = [qa+(t-lo)*spatial_count+s for t in range(lo,hi) for s in points]
    with torch.no_grad():
        hidx = torch.tensor(heads,device=q.device)
        qidx = torch.tensor(query_ids,device=q.device)
        qs = q.index_select(1,hidx).index_select(2,qidx).float()
        kr = k[:,:,ra:rb].index_select(1,hidx).float()
        vr = v[:,:,ra:rb].index_select(1,hidx).float()
        scores = (qs @ kr.transpose(-1,-2)) / math.sqrt(q.shape[-1])
        ref_lse = scores.logsumexp(-1)
        probability = scores.softmax(-1)
        score_grid = scores.reshape(1,len(heads),len(query_ids),times,spatial_count)
        same_probability = torch.empty_like(probability[...,:spatial_count])
        for local,t in enumerate(range(lo,hi)):
            sl = slice(local*len(points),(local+1)*len(points))
            same_probability[:,:,sl] = score_grid[:,:,sl,t].softmax(-1)
        del score_grid
        del scores, kr
        total_lse = torch.full_like(ref_lse,-float('inf'))
        for start in range(0,k.shape[-2],chunk_size):
            ks = k[:,:,start:start+chunk_size].index_select(1,hidx).float()
            logits = (qs @ ks.transpose(-1,-2)) / math.sqrt(q.shape[-1])
            total_lse = torch.logaddexp(total_lse,logits.logsumexp(-1))
        del ks, logits, qs
        mass = (ref_lse-total_lse).exp()
        if not bool(torch.isfinite(mass).all()) or bool((mass > 1.0001).any()):
            raise ValueError('Invalid group mass')
        pgrid = probability.reshape(1,len(heads),len(query_ids),times,spatial_count)
        c_native = pgrid.sum(-2)
        vgrid = vr.reshape(1,len(heads),times,spatial_count,q.shape[-1])
        mean = vgrid.mean(2)
        native = probability @ vr
        same = torch.empty_like(native)
        static_same = torch.empty_like(native)
        spatial = torch.empty_like(native)
        tv = torch.empty_like(mass)
        for local,t in enumerate(range(lo,hi)):
            sl = slice(local*len(points),(local+1)*len(points))
            c_same = same_probability[:,:,sl]
            same[:,:,sl] = c_same @ vgrid[:,:,t]
            static_same[:,:,sl] = c_same @ mean
            spatial[:,:,sl] = c_native[:,:,sl] @ vgrid[:,:,t]
            tv[:,:,sl] = .5*(c_same-c_native[:,:,sl]).abs().sum(-1)
        static_native = c_native @ mean
        weight = mass.unsqueeze(-1)
        full = weight*(same-native)
        static = weight*(static_same-static_native)
        dynamic = full-static
        sp = weight*(spatial-native)
        branches = {'full':full,'dynamic':dynamic,'static':static,'spatial':sp}
        def rms(x): return x.square().mean().sqrt()
        def cosine(a,b):
            denom = a.norm()*b.norm()
            return None if float(denom)<1e-15 else float((a*b).sum()/denom)
        base = rms(weight*native).clamp_min(1e-12)
        result = {
            'scope':'FP32 dense analytic readout at actual QKV; sparse heads/center queries; not exact BF16 route nor motion ground truth',
            'head_indices':heads,'spatial_indices':points,'query_ids':query_ids,
            'reference_bins':times,'reference_mass_mean':float(mass.mean()),
            'reference_mass_max':float(mass.max()),
            'weighted_native_reference_rms':float(base),
            'corrections':{name:{'rms':float(rms(x)),'relative_to_native_reference_rms':float(rms(x)/base)} for name,x in branches.items()},
            'cosines':{a+'_vs_'+b:cosine(branches[a],branches[b]) for a,b in [('dynamic','full'),('static','full'),('dynamic','static'),('spatial','dynamic'),('spatial','full')]},
            'spatial_total_variation_mean':float(tv.mean()),
            'spatial_total_variation_max':float(tv.max()),
            'dc_negative_weight_mean':float(((1-1/times)*tv).mean()),
            'dc_effective_l1_mean':float((1+2*(1-1/times)*tv).mean()),
            'spatial_minus_dynamic_rms':float(rms(sp-dynamic)),
            'full_minus_dynamic_minus_static_max_abs':float((full-dynamic-static).abs().max()),
            'finite':all(bool(torch.isfinite(x).all()) for x in branches.values()),
        }
        if not result['finite']: raise ValueError('Nonfinite component readout')
        return result
