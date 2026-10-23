"""Observe the original Euler sampler via its callback; never call the model ourselves."""
import json,math,sys,time
from pathlib import Path
import torch
try:
    from .capture import ProbeLayout,PassiveQKCapture
    from .reconstruct import file_sha,tensor_info,sigma_grid,unpack
except ImportError:
    from capture import ProbeLayout,PassiveQKCapture
    from reconstruct import file_sha,tensor_info,sigma_grid,unpack

def atomic(path,value):
    path=Path(path);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');tmp.replace(path)

class LiveObservation:
    """SAMPLER_SAMPLE wrapper. callback8 arms9, callback18 arms19.

    Original sample_euler runs unchanged and calls its original model exactly20
    times. Hook installation after callback8 precedes only the pure Euler update,
    then observes the next actual model call. All callback arguments and the
    executor's final result are returned untouched.
    """
    def __init__(self,spec,spec_sha):
        self.spec=dict(spec);self.spec_sha=spec_sha;self.used=False

    def __call__(self,executor,model_wrap,sigmas,extra_args,callback,noise,latent_image=None,denoise_mask=None,disable_pbar=False):
        if self.used:raise RuntimeError('live observation is single-trajectory')
        self.used=True;s=self.spec
        root=Path(s['output_dir'])/s['trajectory_id'];root.mkdir(parents=True,exist_ok=False)
        path=root/'OBSERVATION.json'
        manifest={'schema':'h3-live-phase-observation-v1','status':'running','trajectory_id':s['trajectory_id'],'case':s['case'],'method':s['method'],
            'science_contract_sha256':self.spec_sha,'callback_count':0,'actual_model_forward_count':0,'completed_blocks':0,'extra_model_forward_calls':0,
            'captures':[],'new_final_video_binding_pending':True,'sampling_seconds':None}
        atomic(path,manifest);active=None;counter_handle=None;seen=[];model_count=0
        start=time.perf_counter()
        try:
            base=model_wrap.inner_model;model=base.diffusion_model
            sampler=getattr(executor,'class_obj',None)
            if getattr(getattr(sampler,'sampler_function',None),'__name__',None)!='sample_euler':raise ValueError('original sample_euler required')
            if getattr(sampler,'extra_options',{}).get('s_churn',0)!=0:raise ValueError('Euler churn not allowed')
            if denoise_mask is not None or model_wrap.cfg!=1 or float(base.audio_scale())!=4 or float(base.model_sampling.noise_scale)!=1:raise ValueError('frozen CFG/AV/mask contract differs')
            if extra_args.get('seed')!=s['seed']:raise ValueError('seed differs')
            exact=sigma_grid(s['sigmas_video'])
            if not torch.equal(sigmas.cpu(),exact):raise ValueError('complete original21sigma grid differs')
            shapes=[list(x) for x in base.latent_shapes]
            if shapes!=s['target_shapes']:raise ValueError('complete AV geometry differs')
            if tensor_info(noise)['sha256']!=s['noise_tensor_sha256']:raise ValueError('actual initial noise differs')
            if len(model.blocks)!=50 or (model.blocks[25].attn.heads,model.blocks[25].attn.head_dim)!=(56,128):raise ValueError('H3 block/head geometry differs')
            dit=extra_args['model_options']['transformer_options']['patches_replace']['dit']
            states=[dit[('double_block',i)].state for i in range(50)]
            if len({id(x) for x in states})!=1:raise ValueError('one coherent original router state required')
            state=states[0]
            if state.forward_index!=-1 or state.next_block!=0 or state.audit['started_calls']!=0:raise ValueError('fresh router state required')
            if state.mode!=s['router']['mode'] or state.alpha!=s['router']['alpha'] or tuple(state.active_steps)!=tuple(s['router']['active_steps']):raise ValueError('method schedule differs')
            for key in ('radius','time_offset','start_frame','end_frame','block_start','block_end'):
                if getattr(state,key)!=s['router'][key]:raise ValueError('router parameter differs: '+key)
            conditions=model_wrap.conds.get('positive',[])
            if len(conditions)!=1 or model_wrap.conds.get('negative'):raise ValueError('one BasicGuider positive required')
            payload=conditions[0]['model_conds']['minimax_payload'].cond
            if int(payload['seed'])!=s['seed'] or float(payload['audio_scale'])!=4:raise ValueError('prepared model payload differs')
            probes=ProbeLayout.from_actual(payload['layout'],shapes[0],s['valid_frames'])
            manifest.update(sample_sigmas_video=exact.double().tolist(),noise=tensor_info(noise),target_shapes=shapes,router={'mode':state.mode,'alpha':state.alpha,'active_steps':list(state.active_steps)})
            def count_forward(module,args,kwargs,out):
                nonlocal model_count
                if out is not None:model_count+=1
                # None preserves the actual model output object.
            counter_handle=model.register_forward_hook(count_forward,with_kwargs=True,always_call=True)

            def record(step,x0,x,total):
                nonlocal active
                if type(step)is not int or step!=len(seen) or total!=20 or step>=20:raise ValueError('callback order/count differs')
                if model_count!=step+1 or state.forward_index!=step or state.next_block!=0 or state.audit['completed_forward_calls']!=step+1 or state.audit['completed_calls']!=50*(step+1):raise ValueError('actual model/router count differs')
                seen.append(step);manifest.update(callback_count=len(seen),actual_model_forward_count=model_count,completed_blocks=state.audit['completed_calls'])
                if step in (9,19):
                    if active is None:raise ValueError('capture not armed at preceding callback')
                    cap=active;active=None;cap.__exit__(None,None,None)
                    expected=(1,1,sum(math.prod(z[1:]) for z in shapes))
                    if tuple(x.shape)!=expected or tuple(x0.shape)!=expected or x.dtype!=torch.float32 or x0.dtype!=torch.float32:raise ValueError('full raw AV state/x0 contract differs')
                    sx=x.detach().to('cpu',copy=True).contiguous();sd=x0.detach().to('cpu',copy=True).contiguous()
                    xi,di=tensor_info(sx),tensor_info(sd)
                    if not xi['finite'] or not di['finite']:raise ValueError('nonfinite actual state/x0')
                    statefile=root/f'state_step{step:03d}.pt'
                    torch.save({'schema':'h3-live-phase-state-v1','packed_x':sx,'raw_packed_x0':sd,'target_shapes':shapes,'step_zero_based':step,'sample_sigmas_video':exact.double().tolist()},statefile)
                    identity={'trajectory_id':s['trajectory_id'],'case':s['case'],'method':s['method'],'step_zero_based':step,'layer_zero_based':25,'science_contract_sha256':self.spec_sha,'state_file_sha256':file_sha(statefile),'packed_x':xi,'raw_packed_x0':di,'sample_sigmas_video':exact.double().tolist(),'noise_sha256':manifest['noise']['sha256']}
                    cap.data.update(case=s['case'],method=s['method'],trajectory_id=s['trajectory_id'],forward_identity=identity,sample_sigmas_video=exact.double().tolist(),sigma_video=float(sigmas[step]))
                    qkfile=root/f'qk_step{step:03d}.pt';cap.save(qkfile)
                    manifest['captures'].append({'step_zero_based':step,'layer_zero_based':25,'state_file':str(statefile),'state_file_sha256':file_sha(statefile),'qk_file':str(qkfile),'qk_sha256':file_sha(qkfile),'forward_identity':identity})
                if step in (8,18):
                    if active is not None:raise ValueError('previous capture still active')
                    active=PassiveQKCapture(model.blocks[25].attn,probes,step=step+1,layer=25,in_training=__import__('comfy.model_management',fromlist=['in_training']).in_training)
                    active.__enter__()
                atomic(path,manifest)
                if callback is not None:return callback(step,x0,x,total)

            result=executor(model_wrap,sigmas,extra_args,record,noise,latent_image,denoise_mask,disable_pbar)
            if seen!=list(range(20)) or model_count!=20 or state.audit['completed_calls']!=1000 or [r['step_zero_based'] for r in manifest['captures']]!=[9,19]:raise ValueError('incomplete actual20step trajectory')
            if active is not None:raise ValueError('unclosed capture')
            manifest.update(status='complete',sampling_seconds=time.perf_counter()-start,final_raw_result=tensor_info(result),original_result_returned_without_copy=True)
            if not manifest['final_raw_result']['finite']:raise ValueError('nonfinite final raw AV result')
            atomic(path,manifest)
            return result
        except BaseException as error:
            manifest.update(status='failed',error=type(error).__name__+': '+str(error),sampling_seconds=time.perf_counter()-start)
            try:atomic(path,manifest)
            except BaseException:pass  # The original model/storage exception wins.
            raise
        finally:
            original_exception=sys.exc_info()
            try:
                if active is not None:
                    try:active.__exit__(*original_exception)
                    except BaseException:
                        if original_exception[0] is None:raise
            finally:
                if counter_handle is not None:counter_handle.remove()
