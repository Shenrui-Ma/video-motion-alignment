"""Frozen R3 forward rows plus frozen R25 reverse rows from the same QKV."""
import time
import torch
from .base_router import RouterState,route_attention,flash_attention_lse
from .reverse_frozen import reverse_attention,reverse_plan,_versions
from .native_features import save_native_features

MODES=('native','forward','reverse_block','joint')

def joint_attention(native,q,k,v,heads,plan,*,mode='joint',forward_alpha=1.,reverse_alpha=1.,attention=None,diagnostics=None,first_audit=None,native_kwargs=None):
    if mode not in MODES or any(isinstance(a,bool) or not isinstance(a,(float,int)) or not 0<=a<=1 for a in (forward_alpha,reverse_alpha)):
        raise ValueError('invalid joint component/mode')
    ra,rb,_,_=reverse_plan(plan);ta,tb=plan['query_interval_half_open']
    if not (rb<=ta or tb<=ra):raise ValueError('joint query intervals must be disjoint')
    if q.ndim!=4 or q.shape!=k.shape or k.shape!=v.shape or q.shape[0]!=1 or q.shape[1]!=heads or q.shape[-2]!=plan['seq_len'] or any(x.device!=q.device or x.dtype!=q.dtype for x in (k,v)):
        raise ValueError('invalid packed QKV')
    started=time.perf_counter();before=_versions((q,k,v));copies=[x.clone() for x in (q,k,v)] if first_audit is not None else None
    out=native(q,k,v,heads,**dict(native_kwargs or {}))
    if tuple(out.shape)!=(1,q.shape[-2],heads*q.shape[-1]):raise ValueError('native output layout')
    f=mode in ('forward','joint') and forward_alpha!=0;b=mode in ('reverse_block','joint') and reverse_alpha!=0
    if not f and not b:
        if before!=_versions((q,k,v)):raise ValueError('native changed QKV versions')
        return out
    baseline=out.clone() if first_audit is not None else None
    attention=flash_attention_lse if attention is None else attention
    fs=[];bs=[];calls=0;full_flash_calls=0;backend_equal=None
    def backend(a,c,d):
        nonlocal calls,full_flash_calls,backend_equal
        calls+=1;value,lse=attention(a,c,d)
        if a is q and c is k and d is v:
            full_flash_calls+=1
            if first_audit is not None:
                flat=value.transpose(1,2).reshape_as(out)
                backend_equal=torch.equal(flat,out)
                if not backend_equal:raise ValueError('actual native SDPA vs prewrite Flash full differ; pair attribution refused')
        return value,lse
    # This call is byte-preserved R3 arithmetic, including FP32 work even for
    # float64 test inputs. Retain only its selected target rows, not other rows.
    f_rows=None
    if f:
        full=route_attention(q,k,v,heads,plan,mode='mass_preserve',alpha=forward_alpha,radius=0,time_offset=0,attention=backend,diagnostics=fs)
        f_rows=full[:,ta:tb].clone();del full
    if b:
        out=reverse_attention(lambda *a,**kw:out,q,k,v,heads,plan,mode='reverse_block',alpha=reverse_alpha,attention=backend,diagnostics=bs)
    b_rows=out[:,ra:rb].clone() if first_audit is not None and b else None
    if f:out[:,ta:tb].copy_(f_rows)
    if before!=_versions((q,k,v)):raise ValueError('joint attention changed QKV versions')
    finite=torch.isfinite(out[:,ra:rb]).all() & torch.isfinite(out[:,ta:tb]).all()
    zero=out.new_zeros((),dtype=torch.float32)
    fv=fs[0] if fs else torch.stack([zero]*5)
    bv=bs[0][0] if bs else torch.stack([zero]*7)
    stats=torch.cat((fv.to(torch.float64),bv.to(torch.float64),finite.to(torch.float64).reshape(1)))
    if diagnostics is not None:diagnostics.append((stats,calls,full_flash_calls))
    if first_audit is not None:
        intervals=sorted([(ra,rb)] if b else []);intervals+=([(ta,tb)] if f else []);intervals=sorted(intervals)
        cursor=0;unchanged=True
        for lo,hi in intervals:
            unchanged &= torch.equal(out[:,cursor:lo],baseline[:,cursor:lo]);cursor=hi
        unchanged &= torch.equal(out[:,cursor:],baseline[:,cursor:])
        inputs_equal=all(torch.equal(x,y) for x,y in zip(copies,(q,k,v)))
        f_equal=not f or torch.equal(out[:,ta:tb],f_rows);b_equal=not b or torch.equal(out[:,ra:rb],b_rows)
        audio_equal=all(torch.equal(out[:,a:z],baseline[:,a:z]) for a,z,kind in plan['segments'] if kind=='audio')
        if not all((unchanged,inputs_equal,f_equal,b_equal,audio_equal,bool(finite))):raise ValueError('joint row/input/finite contract')
        if q.device.type=='cuda':torch.cuda.synchronize(q.device)
        first_audit.update(nonselected_rows_bitwise=unchanged,input_values_bitwise=inputs_equal,input_versions_before=before,input_versions_after=_versions((q,k,v)),forward_component_rows_bitwise=f_equal,reverse_component_rows_bitwise=b_equal,target_audio_bitwise=audio_equal,finite=bool(finite),native_vs_prewrite_full_Flash_bitwise=backend_equal,reference_query_interval=[ra,rb],target_query_interval=[ta,tb],selected_reference_rows_equal_native=torch.equal(out[:,ra:rb],baseline[:,ra:rb]),selected_target_rows_equal_native=torch.equal(out[:,ta:tb],baseline[:,ta:tb]),nonzero_correction_required=False,aux_attention_calls=calls,extra_full_Flash_calls=full_flash_calls,attention_plus_audit_seconds=time.perf_counter()-started,snapshot_tensor_bytes=sum(x.numel()*x.element_size() for x in copies)+baseline.numel()*baseline.element_size()+(b_rows.numel()*b_rows.element_size() if b_rows is not None else 0),snapshot_bytes_scope='audit-only input/baseline/B-row clones; excludes F-row working output',scope='same QKV, pre-W_O; component selected rows are copied from frozen paths, no extra model prediction; native SDPA backend exact gate is actual first call')
        if q.device.type=='cuda':first_audit.update(global_peak_allocated_bytes=torch.cuda.max_memory_allocated(q.device),global_peak_reserved_bytes=torch.cuda.max_memory_reserved(q.device))
    return out

class JointState(RouterState):
    def __init__(self,metadata,run_id,audit_dir,*,capture_features=True):
        super().__init__(metadata,'native',1.,0,0,50,65,0,50,6,15,run_id,audit_dir)
        self.mode='joint';self.capture_features=capture_features;self.sampling_started=False;self.prefix_passed=False;self.callback_count=0
        self.audit.update(schema='h3-forward-reverse-joint-r30-v1',mode='joint',direct_native_calls=0,aux_attention_calls=0,extra_full_Flash_calls=0,forward_component_calls=0,reverse_component_calls=0,native_feature_captures=[],first_active_call=None,callback_count=0,backend='original SDPA nonselected; exact R3 Full target rows + exact R25 BLOCK reference rows',condition_scope='actual B original/processed tree excluding two exact UUID leaves; R3 historical full postaug unavailable')
        self.write()
    def finish_forward(self):
        rows=[]
        if self.pending_stats:
            values=torch.stack([x[1] for x in self.pending_stats]).cpu().tolist()
            for (block,_,calls,full),v in zip(self.pending_stats,values):
                rows.append(dict(block=block,forward_ref_mass_mean=v[0],forward_ref_mass_max=v[1],forward_correction_ratio=v[2],forward_finite=v[3]==1.,forward_log_mass_max=v[4],reverse_target_mass_mean=v[5],reverse_target_mass_min=v[6],reverse_target_mass_max=v[7],reverse_correction_rms=v[8],reverse_native_rms=v[9],reverse_finite=v[10]==1.,reverse_max_abs=v[11],all_selected_finite=v[12]==1.,aux_attention_calls=calls,extra_full_Flash_calls=full))
            if not all(x['forward_finite'] and x['reverse_finite'] and x['all_selected_finite'] for x in rows):raise FloatingPointError('joint selected output nonfinite')
        self.pending_stats.clear();self.audit['forward_summaries'].append(dict(forward_index=self.forward_index,completed_blocks=50,routed_blocks=self.audit['routed_by_forward'][-1],layer_stats=rows,sampled_finite=True));self.audit['completed_forward_calls']+=1;self.write()

class JointAttentionOverride:
    def __init__(self,state,plan,block):self.state,self.plan,self.block,self.calls=state,plan,block,0
    def __call__(self,native,q,k,v,heads,**kwargs):
        if getattr(native,'__name__',None)!='attention_pytorch' or kwargs.get('mask') is not None or not kwargs.get('skip_reshape') or kwargs.get('skip_output_reshape',False) or kwargs.get('enable_gqa',False) or kwargs.get('scale') not in (None,128**-.5):raise ValueError('unchanged native dense interface required')
        if q.shape[1]!=56 or q.shape[-1]!=128:raise ValueError('actual56heads x128 required')
        self.calls+=1
        if self.calls!=1:raise ValueError('one attention invocation per block')
        s=self.state;active=s.selected(self.block) and s.mode!='native';first={} if active and s.forward_index==6 and self.block==0 else None;stats=[]
        out=joint_attention(native,q,k,v,heads,self.plan,mode=s.mode if active else 'native',native_kwargs=kwargs,diagnostics=stats,first_audit=first)
        s.audit['native_override_calls']+=1
        if active:
            s.audit['routed_calls']+=1;s.audit['routed_by_block'][self.block]+=1;s.audit['routed_by_forward'][s.forward_index]+=1
            for values,calls,full in stats:s.pending_stats.append((self.block,values,calls,full));s.audit['aux_attention_calls']+=calls;s.audit['extra_full_Flash_calls']+=full
            s.audit['forward_component_calls']+=1;s.audit['reverse_component_calls']+=1
        else:s.audit['direct_native_calls']+=1
        if first is not None:s.audit['first_active_call']=dict(forward_index=s.forward_index,block=self.block,**first)
        if s.capture_features and self.block==25 and s.forward_index in (6,10,14):
            rec=save_native_features(out,self.plan,output_dir=s.path.parent.parent/'native_features',run_id=s.audit['run_id'],step=s.forward_index,block=25,sigma_video=s.audit['sample_sigmas'][s.forward_index],capture_mode=s.mode);rec['scope']='contextual postattention pre-W_O; not matched next-layer counterfactual';s.audit['native_feature_captures'].append(rec)
        if 'first_attention' not in s.audit:s.audit['first_attention']=dict(qkv_shape=list(q.shape),heads=heads,dtype=str(q.dtype),device=str(q.device),returned_shape=list(out.shape))
        return out

class JointBlockPatch:
    def __init__(self,state,block_index):self.state,self.block_index=state,block_index
    def __call__(self,args,extra_args):
        s=self.state;b=self.block_index
        try:
            if not s.sampling_started or b!=s.next_block:raise ValueError('sampler gate/order violation')
            if b==0:
                if s.forward_index+1!=s.callback_count or s.forward_index>=19:raise ValueError('exactly one forward per Euler callback')
                s.forward_index+=1
                if s.forward_index>=6 and not s.prefix_passed:raise ValueError('eligible Native prefix must pass before routing')
                s.audit['calls_by_forward'].append(0);s.audit['routed_by_forward'].append(0)
            plan=s.plan_for(args['layout']);reverse_plan(plan);options=args['transformer_options']
            if options.get('block_index')!=b or options.get('minimax_h3_layout') is not args['layout'] or options.get('optimized_attention_override') is not None:raise ValueError('layout/block/override conflict')
            if options.get('sample_sigmas') is None or options['sample_sigmas'].detach().cpu().tolist()!=s.audit['sample_sigmas']:raise ValueError('model full sigma grid changed')
            s.audit['started_calls']+=1;override=JointAttentionOverride(s,plan,b);local=dict(args);local['transformer_options']=dict(options,optimized_attention_override=override);result=extra_args['original_block'](local)
            if override.calls!=1:raise ValueError('missing attention invocation')
            s.audit['completed_calls']+=1;s.audit['calls_by_block'][b]+=1;s.audit['calls_by_forward'][s.forward_index]+=1;s.next_block=(b+1)%50;s.audit['last_completed_block']=b;s.audit['last_completed_forward_index']=s.forward_index;s.audit['status']='sampling'
            if s.next_block==0:s.finish_forward()
            return result
        except BaseException as error:s.audit.update(status='failed',error=repr(error));s.write();raise
