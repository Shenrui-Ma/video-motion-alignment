"""Root-executed actual Comfy loader/clone/wrap_attn CPU interface smoke.

Actual H3 module attributes and ModelPatcher, meta weights (no DiT numerical
forward). Tiny CPU attention tensors replace packed image activations only.
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
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--parent-audit',type=Path,required=True)
    args=parser.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES']=''
    root=Path(__file__).resolve().parents[1]
    sys.path[:0]=[str(root/'extensions'),str(root/'scripts'),str(args.core),str(args.core.parent/'runtime_deps')]
    sys.argv=['r17-real-cpu']
    from compatibility_bootstrap import install
    install()
    import torch
    torch.set_num_threads(4)
    import comfy.cli_args
    comfy.cli_args.args.cpu=True
    comfy.cli_args.args.disable_xformers=True
    comfy.cli_args.args.use_pytorch_cross_attention=True
    import comfy.ldm.minimax.model as h3
    from comfy.ldm.modules.attention import attention_pytorch, AttentionTensorContainer
    from comfy.model_patcher import ModelPatcher
    from safetensors import safe_open
    from H3PhaseRoPE import H3PhaseRoPE
    from H3PhaseRoPE import core as phase
    from H3PhaseRoPE.architecture import architecture_contract
    assert h3.optimized_attention.__name__=='attention_pytorch'
    with safe_open(args.checkpoint,framework='pt',device='cpu') as handle:
        keys=[k for k in handle.keys() if k.endswith('rope.inv_freq')]
        assert len(keys)==1
        frequency=handle.get_tensor(keys[0])
    evidence=json.loads((root/'configs/parent_native_attention.json').read_text())
    heads=evidence['first_attention']['heads']
    model=h3.MiniMaxH3Model(num_attention_heads=heads,device='meta',dtype=torch.float32,operations=torch.nn)
    model.rope.inv_freq=frequency.clone()
    container=torch.nn.Module();container.diffusion_model=model
    patcher=ModelPatcher(container,torch.device('cpu'),torch.device('cpu'))
    reference=json.loads((root/'configs/parent_full_conditioning.json').read_text())
    refs=[]
    for i,record in enumerate(reference['native_vae_calls']):
        z=torch.load(args.parent_audit/record['latent']['tensor_file'],map_location='cpu',weights_only=True)
        if isinstance(z,dict): raise TypeError('expected actual raw archived reference tensor')
        refs.append(dict(kind='image' if i==0 else 'video',latent=z,latent_t=z.shape[2],
                         latent_h=z.shape[3],latent_w=z.shape[4],ref_audio_t=0))
    positive=[[torch.empty(1,6960,5120,device='meta'),{'minimax_refs':refs}]]
    # Tiny real native wrapper path: no huge CPU packed attention or DiT evaluation.
    gen=torch.Generator().manual_seed(991)
    q,k,v=[torch.randn(1,heads,11,128,generator=gen) for _ in range(3)]
    qkv_before=[x.clone() for x in (q,k,v)]
    def dense(q,k,v):
        z=q@k.transpose(-1,-2)/(128**.5)
        return z.softmax(-1)@v,z.logsumexp(-1)
    real_phase=phase.phase_attention
    def cpu_phase(*a,**kw): return real_phase(*a,**kw,attention=dense)
    rows=[]
    with tempfile.TemporaryDirectory(prefix='r17-cpu-',dir=root/'audit') as temporary:
        for delta in [0.,4.,-4.]:
            cloned=H3PhaseRoPE().apply(patcher,positive,delta,.5,50,65,0,50,6,15,
                                      ('cpu_zero' if delta==0 else 'cpu_plus4' if delta>0 else 'cpu_minus4'),temporary)[0]
            patches=cloned.model_options['transformer_options']['patches_replace']['dit']
            state=patches[('double_block',0)].state
            state.plan_for=lambda layout:{'seq_len':11,'query_interval_half_open':[7,9],
                                           'reference_video_segment':[1,5]}
            layout=object();rng=torch.get_rng_state().clone()
            def original(values):
                result=attention_pytorch(*(AttentionTensorContainer(x) for x in (q,k,v)),heads,
                    mask=None,skip_reshape=True,transformer_options=values['transformer_options'])
                return {'img':result}
            with patch.object(phase,'phase_attention',side_effect=cpu_phase):
                for step in range(20):
                    for block in range(50):
                        options={'block_index':block,'minimax_h3_layout':layout,'sample_sigmas':torch.linspace(1,0,21)}
                        result=patches[('double_block',block)]({'layout':layout,'transformer_options':options},
                                                             {'original_block':original})
                        assert result['img'].shape==(1,11,heads*128)
                        assert 'optimized_attention_override' not in options
            assert state.audit['completed_calls']==1000
            assert state.audit['phase_calls']==(0 if delta==0 else 450)
            assert state.audit['direct_native_calls']==(1000 if delta==0 else 550)
            assert torch.equal(rng,torch.get_rng_state())
            assert all(torch.equal(a,b) for a,b in zip(qkv_before,(q,k,v)))
            assert not patcher.model_options.get('transformer_options',{}).get('patches_replace',{}).get('dit')
            rows.append({'delta':delta,'calls':1000,'phase_calls':state.audit['phase_calls'],
                         'direct_native_calls':state.audit['direct_native_calls']})
    assert not torch.cuda.is_initialized()
    print('R17_REAL_CPU_SMOKE='+json.dumps({'passed':True,'CUDA_initialized':False,
          'scope':'actual H3 meta model + real ModelPatcher clone + real native wrap_attn; tiny attention, not DiT forward/sampler',
          'contract':architecture_contract(model),'rows':rows,
          'h3_source_sha256':hashlib.sha256(Path(h3.__file__).read_bytes()).hexdigest()}))


if __name__=='__main__':main()
