"""Actual Comfy H3 loader/ModelPatcher/native wrap CPU interface gate.

Tiny dense CPU attention, meta model weights; no DiT numerical forward/sampler,
no CUDA. Redirect only audit storage after production node guards pass.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--core',type=Path,required=True)
    parser.add_argument('--parent-audit',type=Path,required=True)
    args=parser.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES']=''
    root=Path(__file__).resolve().parents[1]
    sys.path[:0]=[str(root/'extensions'),str(root/'scripts'),str(args.core),str(args.core.parent/'runtime_deps')]
    sys.argv=['r18-real-cpu']
    from compatibility_bootstrap import install
    install()
    import torch
    torch.set_num_threads(2)
    import comfy.cli_args
    comfy.cli_args.args.cpu=True
    comfy.cli_args.args.disable_xformers=True
    comfy.cli_args.args.use_pytorch_cross_attention=True
    import comfy.ldm.minimax.model as h3
    from comfy.ldm.modules.attention import attention_pytorch, AttentionTensorContainer
    from comfy.model_patcher import ModelPatcher
    import H3TemporalRouter as node
    from H3TemporalRouter import core
    from H3EventAudit import H3EventAuditNoise, audit_root
    from preflight import check
    check(root)
    graph=json.loads((root/'configs/r18_s05_full_6to11.json').read_text())
    # Execute the actual auxiliary validation that failed in past copied runtimes.
    H3EventAuditNoise().get_noise(**graph['6']['inputs'])
    audit_root(graph['5']['inputs']['audit_dir'])
    assert h3.optimized_attention.__name__=='attention_pytorch'
    heads=56
    model=h3.MiniMaxH3Model(num_attention_heads=heads,device='meta',dtype=torch.float32,operations=torch.nn)
    container=torch.nn.Module();container.diffusion_model=model
    patcher=ModelPatcher(container,torch.device('cpu'),torch.device('cpu'))
    reference=json.loads((root/'configs/parent_full_conditioning.json').read_text())
    refs=[]
    for i,record in enumerate(reference['native_vae_calls']):
        z=torch.load(args.parent_audit/record['latent']['tensor_file'],map_location='cpu',weights_only=True)
        from H3EventAudit import tensor_info
        if tensor_info(z)[0]['sha256']!=record['latent']['sha256']:
            raise ValueError('actual parent reference differs from pinned audit')
        refs.append(dict(kind='image' if i==0 else 'video',latent=z,latent_t=z.shape[2],
                         latent_h=z.shape[3],latent_w=z.shape[4],ref_audio_t=0))
    positive=[[torch.empty(1,6960,5120,device='meta'),{'minimax_refs':refs}]]
    gen=torch.Generator().manual_seed(18)
    q,k,v=[torch.randn(1,heads,29,128,generator=gen) for _ in range(3)]
    originals=[x.clone() for x in (q,k,v)]
    plan={'reference_video_segment':[3,15],'query_interval_half_open':[20,26],
          'latent_interval_half_open':[1,3],'frame_rows':3,'seq_len':29}
    def dense(q,k,v):
        z=q@k.transpose(-1,-2)/(128**.5)
        return z.softmax(-1)@v,z.logsumexp(-1)
    route=core.route_attention
    def cpu_route(*a,**kw):return route(*a,**kw,attention=dense)
    with tempfile.TemporaryDirectory(prefix='r18-cpu-',dir=root/'audit') as temporary:
        state_constructor=node.RouterState
        def temporary_state(*a,**kw):
            a=list(a);a[12]=temporary
            return state_constructor(*a,**kw)
        inputs={k:v for k,v in graph['50']['inputs'].items() if k not in ('model','positive')}
        with patch.object(node,'RouterState',side_effect=temporary_state):
            cloned=node.H3TemporalRouter().apply(patcher,positive,**inputs)[0]
        patches=cloned.model_options['transformer_options']['patches_replace']['dit']
        state=patches[('double_block',0)].state
        state.plan_for=lambda _:plan
        layout=object();rng=torch.get_rng_state().clone()
        native=cpu_route(q,k,v,heads,plan,mode='native')
        full=cpu_route(q,k,v,heads,plan,mode='mass_preserve')
        def original(values):
            return attention_pytorch(*(AttentionTensorContainer(x) for x in (q,k,v)),heads,
                mask=None,skip_reshape=True,transformer_options=values['transformer_options'])
        with patch.object(core,'route_attention',side_effect=cpu_route), \
             patch.object(core,'component_probe',return_value={}), \
             patch.object(core,'temporal_readout',return_value={}):
            for step in range(20):
                for block in range(50):
                    options={'block_index':block,'minimax_h3_layout':layout,
                             'sample_sigmas':torch.linspace(1,0,21)}
                    result=patches[('double_block',block)]({'layout':layout,'transformer_options':options},
                                                         {'original_block':original})
                    assert torch.equal(result,full if 6<=step<12 else native)
                    assert 'optimized_attention_override' not in options
        assert state.audit['completed_calls']==1000
        assert state.audit['completed_forward_calls']==20
        assert state.audit['routed_calls']==300
        assert state.audit['routed_by_forward']==[0]*6+[50]*6+[0]*8
        assert all(torch.equal(a,b) for a,b in zip(originals,(q,k,v)))
        assert torch.equal(rng,torch.get_rng_state())
        assert not patcher.model_options.get('transformer_options',{}).get('patches_replace',{}).get('dit')
    assert not torch.cuda.is_initialized()
    print('R18_REAL_CPU_SMOKE='+json.dumps({'passed':True,'CUDA_initialized':False,
        'actual_H3_meta_model':True,'actual_ModelPatcher_clone':True,'actual_attention_wrapper':True,
        'heads':heads,'block_calls':1000,'routed_calls':300,
        'scope':'actual module/node path guard/clone/wrap + tiny dense CPU operator; not real sampler, DiT weights or GPU',
        'h3_source_sha256':hashlib.sha256(Path(h3.__file__).read_bytes()).hexdigest()}))


if __name__=='__main__':main()
