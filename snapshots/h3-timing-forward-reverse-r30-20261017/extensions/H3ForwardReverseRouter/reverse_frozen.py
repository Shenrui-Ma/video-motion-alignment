"""Two frozen reverse-edge diagnostics. Reference rows only, before W_O."""
import math
import time

import torch

from .base_router import RouterState, flash_attention_lse, _aligned_attention
from .native_features import save_native_features

MODES = ('native', 'reverse_block', 'reverse_same')


def reverse_plan(plan):
    n = plan['seq_len']; r0, r1 = plan['reference_video_segment']
    t0, t1 = plan['target_video_segment']; lo, hi = plan['latent_interval_half_open']
    rows = plan['frame_rows']
    if any(type(x) is not int for x in (n, r0, r1, t0, t1, lo, hi, rows)):
        raise ValueError('integer packed indices required')
    if not (rows > 0 and 0 <= r0 < r1 <= t0 < t1 <= n and
            r1-r0 == t1-t0 and (r1-r0) % rows == 0 and
            0 <= lo < hi <= (r1-r0)//rows):
        raise ValueError('invalid disjoint equal-geometry reference/target segments')
    qa, qb = r0+lo*rows, r0+hi*rows
    if plan.get('key_interval_half_open') != [qa, qb]:
        raise ValueError('reference event interval disagrees with actual layout')
    if plan.get('query_interval_half_open') != [t0+lo*rows, t0+hi*rows]:
        raise ValueError('target time interval disagrees with actual layout')
    return qa, qb, t0, t1


def _versions(tensors):
    values=[]
    for x in tensors:
        try:values.append(x._version)
        except RuntimeError:
            if not torch.is_inference(x):raise
            values.append(None)
    return values


def reverse_attention(native, q, k, v, heads, plan, *, mode, alpha=1.,
                      attention=None, diagnostics=None, first_audit=None,
                      native_kwargs=None):
    """Native full output is authoritative; only R-event rows are overwritten."""
    if mode not in MODES or isinstance(alpha, bool) or not math.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ValueError('invalid reverse mode/alpha')
    if (q.ndim != 4 or q.shape != k.shape or k.shape != v.shape or q.shape[0] != 1 or
            q.shape[1] != heads or q.shape[-2] != plan['seq_len'] or
            any(x.dtype != q.dtype or x.device != q.device for x in (k, v))):
        raise ValueError('invalid single-batch packed QKV')
    qa, qb, ta, tb = reverse_plan(plan)
    audit_start=time.perf_counter() if first_audit is not None else None
    memory_before=(torch.cuda.memory_allocated(q.device),torch.cuda.max_memory_allocated(q.device)) if first_audit is not None and q.device.type=='cuda' else None
    before_versions = _versions((q,k,v))
    input_copies=[x.clone() for x in (q,k,v)] if first_audit is not None else None
    kwargs = dict(native_kwargs or {})
    out = native(q,k,v,heads,**kwargs)
    if tuple(out.shape) != (1,q.shape[-2],heads*q.shape[-1]):
        raise ValueError('unexpected original attention output layout')
    if mode == 'native' or alpha == 0:
        if before_versions != _versions((q,k,v)):raise ValueError('native attention changed QKV')
        return out
    attention = flash_attention_lse if attention is None else attention
    # Full native output stays allocated and remains the source of all untouched rows.
    # Only the first active call clones it, for an actual complete row equality gate.
    baseline = out.clone() if first_audit is not None else None
    old = out[:,qa:qb].reshape(1,qb-qa,heads,q.shape[-1]).transpose(1,2)
    query = q[:,:,qa:qb]
    target, lse_t = attention(query,k[:,:,ta:tb],v[:,:,ta:tb])
    # In frozen Ref2VA target video is the final segment; the generic complement
    # handles a non-final segment in bounded CPU oracle tests without dense masks.
    ck = k[:,:,:ta] if tb == k.shape[-2] else torch.cat((k[:,:,:ta],k[:,:,tb:]),dim=-2)
    cv = v[:,:,:ta] if tb == v.shape[-2] else torch.cat((v[:,:,:ta],v[:,:,tb:]),dim=-2)
    complement, lse_c = attention(query,ck,cv)
    work_dtype = torch.float64 if q.dtype == torch.float64 else torch.float32
    log_mass = lse_t.to(work_dtype)-torch.logaddexp(lse_t.to(work_dtype),lse_c.to(work_dtype))
    mass = log_mass.exp()
    if mode == 'reverse_block':
        changed = complement if alpha == 1 else (old.to(work_dtype)+alpha*(complement.to(work_dtype)-old.to(work_dtype))).to(out.dtype)
        extra_calls = 2
    else:
        def aligned_backend(a,b,c):
            output,lse=attention(a,b,c)
            # Byte-reused grouping helper allocates the Flash-contract LSE in
            # float32. This LSE is unused; keep float64 oracle output unchanged.
            return output,lse.float()
        aligned, _ = _aligned_attention(query,k[:,:,ta:tb],v[:,:,ta:tb],
            latent_lo=plan['latent_interval_half_open'][0],frame_rows=plan['frame_rows'],
            radius=0,time_offset=0,attention=aligned_backend)
        changed = (old.to(work_dtype)+alpha*mass.unsqueeze(-1)*(aligned.to(work_dtype)-target.to(work_dtype))).to(out.dtype)
        extra_calls = 3
    # Statistics contain every selected value for finite/mass bounds; RMS uses a
    # fixed bounded sample so its definition is independent of discovered effects.
    hs=max(1,math.ceil(heads/8)); qs=max(1,math.ceil((qb-qa)/128)); ds=max(1,math.ceil(q.shape[-1]/16))
    old_s=old[:,::hs,::qs,::ds].float(); new_s=changed[:,::hs,::qs,::ds].float()
    delta=new_s-old_s
    finite=torch.isfinite(changed).all() & torch.isfinite(mass).all() & (mass>=0).all() & (mass<=1).all()
    stats=torch.stack((mass.mean(),mass.min(),mass.max(),delta.square().mean().sqrt(),
        old_s.square().mean().sqrt(),finite.to(work_dtype),delta.abs().max())).to(torch.float64)
    if diagnostics is not None:diagnostics.append((stats,extra_calls))
    out[:,qa:qb].copy_(changed.transpose(1,2).reshape(1,qb-qa,heads*q.shape[-1]))
    if before_versions != _versions((q,k,v)):raise ValueError('reverse attention changed QKV input versions')
    if first_audit is not None:
        inputs_equal=all(torch.equal(a,b) for a,b in zip(input_copies,(q,k,v)))
        unchanged=(torch.equal(out[:,:qa],baseline[:,:qa]) and torch.equal(out[:,qb:],baseline[:,qb:]))
        target_equal=torch.equal(out[:,ta:tb],baseline[:,ta:tb])
        audio_segments=[(a,b) for a,b,kind in plan['segments'] if kind=='audio']
        audio_equal=all(torch.equal(out[:,a:b],baseline[:,a:b]) for a,b in audio_segments)
        if not unchanged or not target_equal or not audio_equal or not inputs_equal:
            raise ValueError('nonselected/native target rows changed at first active call')
        first_audit.update(nonselected_rows_bitwise=unchanged,target_video_bitwise=target_equal,
            target_audio_bitwise=audio_equal,input_versions_before=before_versions,
            input_versions_after=_versions((q,k,v)),reference_query_interval=[qa,qb],
            input_values_bitwise=inputs_equal,version_counter_scope='null for actual inference tensors; first-call full QKV copies establish value invariance',
            target_key_interval=[ta,tb],selected_rows_equal=torch.equal(out[:,qa:qb],baseline[:,qa:qb]),
            selected_difference_sample_rms=float(stats[3]),selected_difference_sample_max_abs=float(stats[6]),
            finite=bool(finite),target_mass_mean=float(stats[0]),target_mass_min=float(stats[1]),
            target_mass_max=float(stats[2]),nonzero_correction_required=False,
            scope='same input, same attention call before W_O; no next-layer native replay')
        # Independent native full kernel versus grouped Flash decomposition.
        # These are the same preregistered sampled locations as correction RMS.
        native_original=baseline[:,qa:qb].reshape(1,qb-qa,heads,q.shape[-1]).transpose(1,2)
        native_sample=native_original[:,::hs,::qs,::ds].to(work_dtype)
        mt=mass[:,::hs,::qs].unsqueeze(-1)
        reconstructed=mt*target[:,::hs,::qs,::ds].to(work_dtype)+(1-mt)*complement[:,::hs,::qs,::ds].to(work_dtype)
        error=reconstructed-native_sample
        denom=native_sample.square().mean().sqrt().clamp_min(1e-6)
        rel=float(error.square().mean().sqrt()/denom)
        scaled=float(error.abs().max()/native_sample.abs().max().clamp_min(1e-6))
        first_audit['native_group_reconstruction']={'sample_relative_rms':rel,'sample_maxabs_scaled':scaled,
            'scope':'sampled native SDPA vs mT*FlashT+(1-mT)*FlashComplement; ideal mass algebra is not bitwise native probability equality',
            'bf16_limits':{'relative_rms':.025,'maxabs_scaled':.035}}
        if q.dtype==torch.bfloat16 and (rel>.025 or scaled>.035):
            raise ValueError('first-call grouped/native reconstruction exceeds frozen bf16 tolerance')
        if q.device.type=='cuda':torch.cuda.synchronize(q.device)
        first_audit['attention_plus_full_audit_seconds']=time.perf_counter()-audit_start
        first_audit['snapshot_tensor_bytes']=sum(x.numel()*x.element_size() for x in input_copies)+baseline.numel()*baseline.element_size()
        first_audit['audit_peak_scope']='extra first-call QKV/output copies; this time/peak is not pure reverse-kernel overhead'
        if memory_before is not None:
            first_audit.update(allocated_before_bytes=memory_before[0],global_peak_allocated_before_bytes=memory_before[1],
                allocated_with_audit_bytes=torch.cuda.memory_allocated(q.device),global_peak_allocated_after_bytes=torch.cuda.max_memory_allocated(q.device))
    return out


class ReverseState(RouterState):
    def __init__(self,metadata,mode,run_id,audit_dir,*,capture_features=True):
        if mode not in MODES:raise ValueError('invalid mode')
        super().__init__(metadata,'native',1.,0,0,50,65,0,50,6,15,run_id,audit_dir)
        self.mode=mode; self.capture_features=capture_features
        self.sampling_started=False;self.prefix_passed=False;self.callback_count=0
        self.audit.update(schema='h3-reverse-reference-r25-v1',mode=mode,
            mechanism='reference-event Q reads target-video KV; portrait/audio retained',
            backend='original attention_pytorch full output + Flash group outputs/LSE',
            metric_scope='all selected values finite; bounded8heads/128queries/16channels correction sample',
            direct_native_calls=0,aux_attention_calls=0,native_feature_captures=[],
            first_active_call=None,callback_count=0,condition_scope='actual current guider original+processed tree; historical R3 postaug tree unavailable')
        self.write()

    def finish_forward(self):
        rows=[]
        if self.pending_stats:
            values=torch.stack([x[1] for x in self.pending_stats]).cpu().tolist()
            for (block,_,calls),value in zip(self.pending_stats,values):
                rows.append(dict(block=block,target_mass_mean=value[0],target_mass_min=value[1],
                    target_mass_max=value[2],correction_sample_rms=value[3],native_sample_rms=value[4],
                    finite=value[5]==1.,correction_sample_max_abs=value[6],aux_attention_calls=calls))
            if not all(r['finite'] for r in rows):raise FloatingPointError('invalid selected attention output/mass')
        self.pending_stats.clear()
        self.audit['forward_summaries'].append(dict(forward_index=self.forward_index,
            completed_blocks=50,routed_blocks=self.audit['routed_by_forward'][-1],layer_stats=rows,
            sampled_finite=all(x['finite'] for x in rows)))
        self.audit['completed_forward_calls']+=1
        self.write()


class ReverseAttentionOverride:
    def __init__(self,state,plan,block):self.state,self.plan,self.block,self.calls=state,plan,block,0

    def __call__(self,native,q,k,v,heads,**kwargs):
        if (getattr(native,'__name__',None)!='attention_pytorch' or kwargs.get('mask') is not None or
                not kwargs.get('skip_reshape') or kwargs.get('skip_output_reshape',False) or
                kwargs.get('enable_gqa',False) or kwargs.get('scale') not in (None,128**-.5)):
            raise ValueError('requires unchanged native dense attention interface')
        if q.shape[1]!=56 or q.shape[-1]!=128:raise ValueError('actual H3 requires56heads×128')
        self.calls+=1
        if self.calls!=1:raise ValueError('one attention call required per block')
        s=self.state; active=s.selected(self.block) and s.mode!='native'
        first={} if active and s.forward_index==6 and self.block==0 else None
        stats=[]
        result=reverse_attention(native,q,k,v,heads,self.plan,mode=s.mode if active else 'native',
            native_kwargs=kwargs,diagnostics=stats,first_audit=first)
        s.audit['native_override_calls']+=1
        if active:
            s.audit['routed_calls']+=1;s.audit['routed_by_block'][self.block]+=1
            s.audit['routed_by_forward'][s.forward_index]+=1
            for values,calls in stats:
                s.pending_stats.append((self.block,values,calls));s.audit['aux_attention_calls']+=calls
        else:s.audit['direct_native_calls']+=1
        if first is not None:s.audit['first_active_call']=dict(forward_index=s.forward_index,block=self.block,**first)
        if s.capture_features and self.block==25 and s.forward_index in (6,10,14):
            rec=save_native_features(result,self.plan,output_dir=s.path.parent.parent/'native_features',
                run_id=s.audit['run_id'],step=s.forward_index,block=25,
                sigma_video=s.audit['sample_sigmas'][s.forward_index],capture_mode=s.mode)
            rec['actual_arm']=s.mode;rec['scope']='same native_features hook; reverse-arm contextual output, not native baseline'
            s.audit['native_feature_captures'].append(rec)
        if 'first_attention' not in s.audit:
            s.audit['first_attention']=dict(qkv_shape=list(q.shape),heads=heads,dtype=str(q.dtype),device=str(q.device),returned_shape=list(result.shape))
        return result


class ReverseBlockPatch:
    def __init__(self,state,block_index):self.state,self.block_index=state,block_index

    def __call__(self,args,extra_args):
        s=self.state;b=self.block_index
        try:
            if not s.sampling_started:raise ValueError('sampler gate must run before blocks')
            if b!=s.next_block:raise ValueError('unexpected block order/interleaved forward')
            if b==0:
                if s.forward_index+1!=s.callback_count or s.forward_index>=19:raise ValueError('one forward per actual Euler callback required')
                s.forward_index+=1
                if s.forward_index>=6 and not s.prefix_passed:raise ValueError('parent native005 bridge must pass before intervention')
                s.audit['calls_by_forward'].append(0);s.audit['routed_by_forward'].append(0)
            plan=s.plan_for(args['layout']);reverse_plan(plan)
            options=args['transformer_options']
            if options.get('block_index')!=b or options.get('minimax_h3_layout') is not args['layout'] or options.get('optimized_attention_override') is not None:
                raise ValueError('block/layout/override conflict')
            schedule=options.get('sample_sigmas')
            if schedule is None or schedule.detach().cpu().tolist()!=s.audit['sample_sigmas']:
                raise ValueError('actual transformer full sigma grid changed')
            s.audit['started_calls']+=1
            override=ReverseAttentionOverride(s,plan,b)
            local=dict(args);local['transformer_options']=dict(options,optimized_attention_override=override)
            result=extra_args['original_block'](local)
            if override.calls!=1:raise ValueError('missing actual attention override')
            s.audit['completed_calls']+=1;s.audit['calls_by_block'][b]+=1;s.audit['calls_by_forward'][s.forward_index]+=1
            s.next_block=(b+1)%50;s.audit['last_completed_block']=b;s.audit['last_completed_forward_index']=s.forward_index;s.audit['status']='sampling'
            if s.next_block==0:s.finish_forward()
            return result
        except BaseException as error:
            s.audit.update(status='failed',error=repr(error));s.write();raise
