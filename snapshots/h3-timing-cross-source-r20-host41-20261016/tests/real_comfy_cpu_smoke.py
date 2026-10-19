"""Real H3 module/ModelPatcher/attention wrapper CPU gate, no weights/sampler/CUDA."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

def main():
    p=argparse.ArgumentParser();p.add_argument('--core',required=True,type=Path);a=p.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES']='';root=Path(__file__).resolve().parents[1]
    sys.path[:0]=[str(root/'extensions'),str(root/'scripts'),str(a.core),str(a.core.parent/'runtime_deps')]
    sys.argv=['r20-real-cpu']
    from compatibility_bootstrap import install
    install()
    import torch
    torch.set_num_threads(1)
    import comfy.cli_args
    comfy.cli_args.args.cpu=True;comfy.cli_args.args.disable_xformers=True;comfy.cli_args.args.use_pytorch_cross_attention=True
    import comfy.ldm.minimax.model as h3
    from comfy.ldm.modules.attention import attention_pytorch,AttentionTensorContainer
    from comfy.model_patcher import ModelPatcher
    import H3TemporalRouter as node
    from H3TemporalRouter import core
    from H3EventAudit import H3EventAuditNoise,audit_root
    from preflight import check,ARMS,read
    check(root)
    model=h3.MiniMaxH3Model(num_attention_heads=56,device='meta',dtype=torch.float32,operations=torch.nn)
    container=torch.nn.Module();container.diffusion_model=model
    patcher=ModelPatcher(container,torch.device('cpu'),torch.device('cpu'))
    # Shapes are from actual source07 records; tensors are meta, not claimed actual encodings.
    c=read(root/'configs/source07_host9_conditioning.json');refs=[]
    for i,item in enumerate(c['native_vae_calls']):
        shape=item['latent']['shape'];z=torch.empty(shape,device='meta')
        refs.append(dict(kind='image' if i==0 else 'video',latent=z,latent_t=shape[2],latent_h=shape[3],latent_w=shape[4],ref_audio_t=0))
    positive=[[torch.empty(c['conditioning_embedding']['shape'],device='meta'),{'minimax_refs':refs}]]
    gen=torch.Generator().manual_seed(20);q,k,v=[torch.randn(1,56,29,128,generator=gen) for _ in range(3)]
    before=[x.clone() for x in (q,k,v)];rng=torch.get_rng_state().clone()
    plan={'reference_video_segment':[3,15],'query_interval_half_open':[20,26],'latent_interval_half_open':[1,3],'frame_rows':3,'seq_len':29}
    route=core.route_attention
    def dense(q,k,v):
        z=q@k.transpose(-1,-2)/(q.shape[-1]**.5);return z.softmax(-1)@v,z.logsumexp(-1)
    def cpu_route(*a,**kw):return route(*a,**kw,attention=dense)
    native=cpu_route(q,k,v,56,plan,mode='native');full=cpu_route(q,k,v,56,plan,mode='mass_preserve')
    reports=[]
    for run_id in ARMS:
        g=read(root/'configs'/f'{run_id}.json')
        # Actual auxiliary path guards run before any temporary state redirection.
        H3EventAuditNoise().get_noise(**g['6']['inputs']);audit_root(g['5']['inputs']['audit_dir'])
        with tempfile.TemporaryDirectory(prefix='cpu-',dir=root/'audit') as folder:
            ctor=node.RouterState
            def temp_state(*a,**kw):
                a=list(a);a[12]=folder;return ctor(*a,**kw)
            args={k:v for k,v in g['50']['inputs'].items() if k not in ('model','positive')}
            with patch.object(node,'RouterState',side_effect=temp_state):
                cloned=node.H3TemporalRouter().apply(patcher,positive,**args)[0]
            patches=cloned.model_options['transformer_options']['patches_replace']['dit'];state=patches[('double_block',0)].state
            state.plan_for=lambda _:plan;layout=object()
            def original(values):return attention_pytorch(*(AttentionTensorContainer(x) for x in (q,k,v)),56,mask=None,skip_reshape=True,transformer_options=values['transformer_options'])
            with patch.object(core,'route_attention',side_effect=cpu_route),patch.object(core,'temporal_readout',return_value={}):
                for index in range(20):
                    for b in range(50):
                        options={'block_index':b,'minimax_h3_layout':layout,'sample_sigmas':torch.linspace(1,0,21)}
                        out=patches[('double_block',b)]({'layout':layout,'transformer_options':options},{'original_block':original})
                        expected=full if run_id==ARMS[1] and 6<=index<15 else native
                        if not torch.equal(out,expected):raise ValueError('real wrapper output/schedule mismatch')
                        if 'optimized_attention_override' in options:raise ValueError('mutated original options')
            if state.audit['completed_calls']!=1000 or state.audit['completed_forward_calls']!=20 or state.audit['routed_calls']!=(450 if run_id==ARMS[1] else 0):raise ValueError('actual counter mismatch')
            reports.append({'run_id':run_id,'block_calls':1000,'routed_calls':state.audit['routed_calls']})
    if not all(torch.equal(a,b) for a,b in zip(before,(q,k,v))) or not torch.equal(rng,torch.get_rng_state()):raise ValueError('input/RNG mutation')
    if patcher.model_options.get('transformer_options',{}).get('patches_replace',{}).get('dit'):raise ValueError('parent model patched')
    if torch.cuda.is_initialized():raise ValueError('CUDA initialized')
    print('R20_REAL_CPU_SMOKE='+json.dumps({'passed':True,'CUDA_initialized':False,'loaded_model_weights':False,'arms':reports,'heads':56,
        'actual_H3_module':True,'actual_ModelPatcher':True,'actual_attention_wrapper':True,
        'scope':'Meta H3 + production nodes/guards/clone + manual20x50 tiny dense CPU calls; not real sampler or neural inference',
        'h3_source_sha256':hashlib.sha256(Path(h3.__file__).read_bytes()).hexdigest()}))
if __name__=='__main__':main()
