"""Load bounded real-source definitions for CPU tests, without importing Comfy runtime."""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import torch

ROOT=Path(__file__).parent/'sources'

def actual_euler():
    doc=json.loads((ROOT/'HOST41_AV_SOURCE.json').read_text())
    nodes=next(f['nodes'] for f in doc['files'] if f['relative_path']=='comfy/k_diffusion/sampling.py')
    scope={'torch':torch,'utils':SimpleNamespace(append_dims=lambda x,n:x[(...,)+(None,)*(n-x.ndim)]),'trange':lambda n,disable=None:range(n)}
    for name in ('to_d','sample_euler'):
        code=next(x['source'] for x in nodes if x['name']==name)
        exec(compile(code,'actual_Comfy_'+name,'exec'),scope)
    return scope['sample_euler']

def _definitions(path,names,scope):
    tree=ast.parse(path.read_text());found=set()
    for node in tree.body:
        if getattr(node,'name',None) in names:
            exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),scope);found.add(node.name)
    if found!=set(names):raise ValueError('source definitions missing: '+str(set(names)-found))

def actual_attention_and_layout():
    import math
    source=ROOT/'host41_model.py'
    if hashlib.sha256(source.read_bytes()).hexdigest()!='0d5edcf32b4b98d704eaa51de60ed71f507d0c7d9845947f566647dc76fb8dfe':raise ValueError('frozen model source changed')
    rope={ 'torch':torch,'check_rope_inplace':lambda *a,**k:None }
    _definitions(ROOT/'host9_kitchen_eager_rope.py',['apply_rope1','apply_rope_split_half1','_rms_rope1','rms_rope_split_half','rms_rope_split_half_'],rope)
    def attention(q,k,v,heads,**kwargs):
        y=torch.nn.functional.scaled_dot_product_attention(q,k,v)
        return y.transpose(1,2).reshape(1,q.shape[2],-1)
    scope={'torch':torch,'nn':torch.nn,'math':math,'FRAME_PER_TOKEN':(1,4,4,4,4),'FRAME_RESCALE':5/3,
           'AttentionTensorContainer':lambda x:x,'optimized_attention':attention,
           'comfy':SimpleNamespace(model_management=SimpleNamespace(cast_to=lambda x,device:x.to(device),in_training=False),quant_ops=SimpleNamespace(ck=SimpleNamespace(**{k:rope[k] for k in ('rms_rope_split_half','rms_rope_split_half_')})))}
    names=['_axis_from_sqrt_area','_frame_grid','_video_t_spans','_video_t_grid','_ref_t_span','_audio_grid','_video_grid','rope_rotation_table','Attention','PackedLayout']
    _definitions(source,names,scope)
    return scope

def actual_sampler_classes():
    doc=json.loads((ROOT/'HOST41_GUIDER_SOURCE.json').read_text())
    nodes={n['name']:n['source'] for f in doc['files'] for n in f.get('nodes',[])}
    class Sampler:
        def max_denoise(self,*a):return True
    class Executor:
        @classmethod
        def new_class_executor(cls,fn,*a):return SimpleNamespace(execute=fn)
    comfy=SimpleNamespace(patcher_extension=SimpleNamespace(WrapperExecutor=Executor,get_all_wrappers=lambda *a,**k:[],WrappersMP=SimpleNamespace(PREDICT_NOISE='predict')))
    scope={'torch':torch,'Sampler':Sampler,'detail':lambda *a,**k:None,'ModelPatcher':object,'comfy':comfy,
           'sampling_function':lambda model,x,sigma,negative,positive,cfg,model_options,seed:model.predict(x,sigma,model_options,seed)}
    for name in ('KSamplerX0Inpaint','KSAMPLER','CFGGuider'):exec(compile(nodes[name],'actual_'+name,'exec'),scope)
    aux=json.loads((ROOT/'HOST41_AV_AUX_SOURCE.json').read_text())
    for name in ('reshape_sigma','CONST'):
        code=next(n['source'] for f in aux['files'] for n in f.get('nodes',[]) if n['name']==name)
        exec(compile(code,'actual_'+name,'exec'),scope)
    return scope
