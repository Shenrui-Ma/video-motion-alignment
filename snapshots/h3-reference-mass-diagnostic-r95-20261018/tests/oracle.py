"""Small, dense, CPU-only reference calculations for independent validation."""
import math
import torch

def dense_attention(q,k,v):
    assert all(x.device.type=='cpu' for x in (q,k,v))
    logits=q.double()@k.double().transpose(-1,-2)/math.sqrt(q.shape[-1])
    lse=torch.logsumexp(logits,-1)
    out=logits.softmax(-1)@v.double()
    return out.to(q.dtype),lse.to(torch.float32)

def fixture(dtype=torch.float64,bias=None):
    g=torch.Generator(device='cpu').manual_seed(94095)
    q,k,v=[torch.randn((1,2,32,8),generator=g,dtype=torch.float64).to(dtype) for _ in range(3)]
    plan={'query_interval_half_open':(24,32),'reference_video_segment':(6,18),
          'latent_interval_half_open':(1,3),'frame_rows':4}
    if bias is not None:
        q.zero_();q[...,0]=1;k.zero_();k[:,:,6:18,0]=float(bias)*math.sqrt(8)
    return q,k,v,plan

def dense_oracle(q,k,v,plan,*,gain,mode,alpha=1,radius=0,time_offset=0,naive_samebin_bias=False):
    logits=q.double()@k.double().transpose(-1,-2)/math.sqrt(q.shape[-1])
    native=logits.softmax(-1)@v.double();changed=logits.clone()
    qa,qb=plan['query_interval_half_open'];ra,rb=plan['reference_video_segment'];rows=plan['frame_rows']
    if mode=='reference_group_gain':changed[:,:,qa:qb,ra:rb]+=math.log(gain)
    else:
        total=(rb-ra)//rows
        for j in range(qa,qb):
            t=plan['latent_interval_half_open'][0]+(j-qa)//rows
            center=max(0,min(total-1,t+time_offset));lo=max(0,center-radius);hi=min(total,center+radius+1)
            ka,kb=ra+lo*rows,ra+hi*rows
            ref_lse=torch.logsumexp(logits[:,:,j,ra:rb],-1)
            same_lse=torch.logsumexp(logits[:,:,j,ka:kb],-1)
            changed[:,:,j,ra:rb]=-torch.inf
            normalization=0 if naive_samebin_bias else ref_lse-same_lse
            changed[:,:,j,ka:kb]=logits[:,:,j,ka:kb]+math.log(gain)+(normalization.unsqueeze(-1) if isinstance(normalization,torch.Tensor) else normalization)
    target=changed.softmax(-1)@v.double()
    out=native+alpha*(target-native)
    return out.transpose(1,2).reshape(1,q.shape[-2],q.shape[1]*q.shape[-1]).to(q.dtype)
