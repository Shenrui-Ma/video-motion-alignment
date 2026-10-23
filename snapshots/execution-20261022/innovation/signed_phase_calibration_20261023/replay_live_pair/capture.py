"""Scoped passive H3 Q/K snapshots. No attention replacement or output rewrite."""
from __future__ import annotations
from dataclasses import dataclass
import math
from pathlib import Path
import torch
try:
    from .reconstruct import tensor_info
except ImportError:
    from reconstruct import tensor_info

def _frame_spans(n):
    start=0
    for i in range(n):
        length=(1,4,4,4,4)[i%5]
        yield start,start+length-1
        start+=length

@dataclass(frozen=True)
class ProbeLayout:
    sequence_length: int
    latent_bins: int
    frame_rows: int
    canvas_start: int
    reference_start: int
    spatial_ids: tuple[int,...]
    valid_bins: tuple[bool,...]
    position_canvas: torch.Tensor
    position_reference: torch.Tensor

    @classmethod
    def from_actual(cls,layout,reference_shape,valid_frames,*,probes=8):
        # Use the actual model payload's PackedLayout, not reconstructed text length.
        _,t,h,w,_=layout.signature
        if tuple(reference_shape)!=(1,24,t,h,w): raise ValueError('reference/target geometry differs')
        if probes!=8: raise ValueError('frozen observation uses8 probes')
        s=(h//2)*(w//2)
        refs=[(a,b) for a,b,k in layout.segments if k=='ref_img']
        targets=[(a,b) for a,b,k in layout.segments if k=='video']
        if len(refs)!=1 or len(targets)!=1: raise ValueError('exactly one reference video and target required')
        (ra,rb),(ta,tb)=refs[0],targets[0]
        if rb-ra!=t*s or tb-ta!=t*s or not 0<=ra<rb<=ta<tb<=layout.seq_len: raise ValueError('video layout mismatch')
        ids=tuple(torch.linspace(0,s-1,probes).round().long().tolist())
        if len(set(ids))!=probes: raise ValueError('spatial grid too small')
        idx=(torch.arange(t)[:,None]*s+torch.tensor(ids)[None,:]).flatten()
        end=0;valid=[]
        for i in range(t):
            end+=(1,4,4,4,4)[i%5];valid.append(end<=valid_frames)
        if not any(valid): raise ValueError('no valid physical bin')
        pc=layout.position_ids.index_select(0,idx+ta).clone()
        pr=layout.position_ids.index_select(0,idx+ra).clone()
        return cls(layout.seq_len,t,s,ta,ra,ids,tuple(valid),pc,pr)

    def indices(self,device):
        local=(torch.arange(self.latent_bins,device=device)[:,None]*self.frame_rows+torch.tensor(self.spatial_ids,device=device)[None,:]).flatten()
        return local+self.canvas_start,local+self.reference_start

class PassiveQKCapture:
    """One call at an explicitly selected layer/step; snapshots are detached copies.

    Requires actual inference in-place RMS+RoPE branch. Raw pre-RoPE Q/K are copied
    by qkv_proj's forward hook before the parent mutates its returned buffer.
    Actual post-RoPE Q/K are copied after Attention.forward from that same buffer.
    Handles are removed even on failure; repeated/reentrant use fails closed.
    """
    def __init__(self,attention,layout,*,step,layer=25,in_training=False):
        if step not in (9,19) or layer!=25: raise ValueError('only frozen layer25 steps9/19')
        if in_training: raise ValueError('inference in-place path required')
        self.attention=attention;self.layout=layout;self.step=step;self.layer=layer
        self.handles=[];self.entered=False;self.started=False;self.done=False;self.failed=False
        self.buffer=None;self.data={};self.rope=None

    @staticmethod
    def _cpu_copy(t): return t.detach().to(device='cpu',copy=True).contiguous()

    def _before(self,module,args,kwargs):
        if self.started or self.done: raise RuntimeError('capture is single-call; duplicate or reentrant forward')
        self.started=True
        x=kwargs.get('x',args[0] if args else None)
        rope=kwargs.get('rope_freqs',args[1] if len(args)>1 else None)
        if x is None or x.ndim!=2 or x.shape[0]!=self.layout.sequence_length: raise ValueError('unexpected packed input')
        if rope is None or rope.ndim!=6 or rope.shape[0]!=1 or rope.shape[1]!=x.shape[0] or tuple(rope.shape[-2:])!=(2,2): raise ValueError('actual full split-half RoPE table required')
        if 2*rope.shape[-3]>module.head_dim: raise ValueError('rotary prefix exceeds head')
        self.rope=rope
        self.ci,self.ri=self.layout.indices(x.device)
        self.data.update(step_zero_based=self.step,layer_zero_based=self.layer,
                         spatial_ids=list(self.layout.spatial_ids),valid_bins=list(self.layout.valid_bins),
                         time_role=[i%5 for i in range(self.layout.latent_bins)],
                         physical_frame_spans_inclusive=[list(x) for x in _frame_spans(self.layout.latent_bins)],
                         raw_stage='qkv_projection_before_per_head_RMSNorm_and_RoPE',
                         actual_stage='same_qkv_buffer_after_inplace_RMSNorm_and_partial_RoPE',
                         heads=module.heads,head_dim=module.head_dim,rot_dim=2*rope.shape[-3],
                         q_norm_eps=float(module.q_norm.eps),k_norm_eps=float(module.k_norm.eps))
        if module.q_norm.eps!=module.k_norm.eps: raise ValueError('actual fused path expects shared epsilon')
        self.data['q_norm_weight']=self._cpu_copy(module.q_norm.weight)
        self.data['k_norm_weight']=self._cpu_copy(module.k_norm.weight)
        self.data['position_canvas']=self._cpu_copy(self.layout.position_canvas)
        self.data['position_reference']=self._cpu_copy(self.layout.position_reference)
        self.data['rope_canvas']=self._cpu_copy(rope.index_select(1,self.ci))
        self.data['rope_reference']=self._cpu_copy(rope.index_select(1,self.ri))
        # Explicitly return None: preserve original positional/keyword arguments.

    def _projected(self,module,args,output):
        if not self.started or self.buffer is not None: raise RuntimeError('unexpected qkv callback')
        a=self.attention;n=self.layout.sequence_length
        if not isinstance(output,torch.Tensor) or output.shape!=(n,3*a.heads*a.head_dim): raise ValueError('actual packed QKV shape differs')
        self.buffer=output
        self._snapshot('raw')
        # Return None, never replace the qkv tensor consumed by the actual parent.

    def _snapshot(self,stage):
        a=self.attention;inner=a.heads*a.head_dim
        q,k,_=self.buffer.split(inner,dim=-1)
        for name,value,ids in [('Q_C',q,self.ci),('Q_R',q,self.ri),('K_R',k,self.ri)]:
            selected=value.index_select(0,ids).reshape(self.layout.latent_bins,len(self.layout.spatial_ids),a.heads,a.head_dim)
            self.data[stage+'_'+name]=self._cpu_copy(selected)

    def _after(self,module,args,kwargs,output):
        if output is None: self.failed=True;return
        if self.buffer is None: raise RuntimeError('qkv hook not reached')
        self._snapshot('actual');self.done=True;self.buffer=None;self.rope=None
        for name,v in self.data.items():
            if isinstance(v,torch.Tensor) and not bool(torch.isfinite(v).all()): raise ValueError('nonfinite captured '+name)
        # Preserve output object identity and values.

    def __enter__(self):
        if self.entered: raise RuntimeError('capture instance cannot be reused')
        self.entered=True
        try:
            self.handles.append(self.attention.register_forward_pre_hook(self._before,with_kwargs=True))
            self.handles.append(self.attention.qkv_proj.register_forward_hook(self._projected))
            self.handles.append(self.attention.register_forward_hook(self._after,with_kwargs=True,always_call=True))
        except BaseException:
            for h in self.handles:h.remove()
            self.handles=[];self.failed=True
            raise
        return self

    def __exit__(self,typ,value,tb):
        for h in self.handles:h.remove()
        self.handles=[];self.buffer=None;self.rope=None
        if typ is not None:self.failed=True
        if typ is None and (not self.done or self.failed): raise RuntimeError('capture did not complete exactly once')
        return False

    def save(self,path):
        if self.handles or not self.done or self.failed: raise RuntimeError('save requires successfully closed context')
        p=Path(path)
        if p.exists(): raise FileExistsError(p)
        payload={'schema':'h3-passive-qk-capture-v1',**self.data}
        torch.save(payload,p)
        return {k:tensor_info(v) for k,v in payload.items() if isinstance(v,torch.Tensor)}

def content_rms(raw,weight,epsilon):
    """Offline eager RMS oracle; actual fused numerical agreement still measured separately."""
    return torch.nn.functional.rms_norm(raw,(raw.shape[-1],),weight.to(raw.dtype),epsilon)

def inverse_actual_rope(actual,table,rot_dim):
    """Undo the actual stored 2x2 table (incl BF16 determinant drift), FP64 diagnostic.

    Quantization of the already-rotated Q/K is irreversible. This diagnostic must
    not be called an exact recovery of pre-RoPE activations.
    """
    d=actual.shape[-1];t,p,h,_=actual.shape
    matrix=table.reshape(t,p,1,rot_dim//2,2,2).double()
    v=actual[...,:rot_dim].double().reshape(t,p,h,2,rot_dim//2).movedim(-2,-1)
    result=torch.linalg.solve(matrix,v.unsqueeze(-1)).squeeze(-1).movedim(-1,-2).reshape(t,p,h,rot_dim)
    return torch.cat([result,actual[...,rot_dim:].double()],dim=-1)
