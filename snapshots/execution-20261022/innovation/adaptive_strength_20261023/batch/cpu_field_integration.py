"""Replay the real state/block wrappers with dense CPU attention, then audit independently."""
import json
import tempfile
from pathlib import Path
from unittest import mock
import torch
from feature_gain_field.attention import FeatureConfig,make_classes
from feature_gain_field.test_feature_attention import FeatureAttentionTests,dense
from feature_gain_field.frozen import load_frozen
from field_audit import check_field

torch.set_num_threads(1)
core=load_frozen().core
state_type,block_type=make_classes(core)
q,k,v,heads,plan=FeatureAttentionTests().data(frames=7,spatial=3,lo=0,hi=7,h=3,d=8)
layout=object();inputs={}
torch.manual_seed(2210);noise=torch.randn_like(v)
def attention_pytorch():pass
def original(args):
    return args['transformer_options']['optimized_attention_override'](
        attention_pytorch,q,k,inputs['v'],heads,skip_reshape=True)
with tempfile.TemporaryDirectory() as tmp,mock.patch.object(core,'flash_attention_lse',dense):
    state=state_type({},'mass_preserve',.25,0,0,0,24,0,50,0,20,
        'independent_replay',tmp,feature_config=FeatureConfig())
    with mock.patch.object(state,'plan_for',return_value=plan):
        for step in range(20):
            for block in range(50):
                inputs['v']=v*(1+.02*block)+noise*(.03*step)
                args={'layout':layout,'transformer_options':{'block_index':block,
                    'minimax_h3_layout':layout,'sample_sigmas':torch.linspace(1,0,21)}}
                block_type(state,block)(args,{'original_block':original})
    saved=json.loads((Path(tmp)/'independent_replay.json').read_text())
    result=check_field(saved)
    assert result['alpha_max']-result['alpha_min'] > .05, result
    result['fixture']='actual state/block factory, dense CPU attention, changing Value features'
    result['model_or_gpu_inference']=False
    print(json.dumps(result))
