"""CPU-only original-noise reader; never regenerate a historical trajectory."""
from pathlib import Path
import torch
try:
    from .reconstruct import file_sha,pack,tensor_info
except ImportError:
    from reconstruct import file_sha,pack,tensor_info

class HistoricalNoise:
    def __init__(self,path,expected_sha,seed):
        path=Path(path)
        if path.is_symlink() or file_sha(path)!=expected_sha:raise ValueError('original noise file identity mismatch')
        payload=torch.load(path,map_location='cpu',weights_only=True)
        if payload['signature'].get('nested') is not True or payload['signature'].get('seed')!=seed:raise ValueError('original AV noise/seed mismatch')
        self.seed=seed;self.tensors=payload['tensors']
        if len(self.tensors)!=2 or any(t.device.type!='cpu' or t.dtype!=torch.float32 or not bool(torch.isfinite(t).all()) for t in self.tensors):raise ValueError('finite FP32 complete AV noise required')
        self.signature=tensor_info(pack(self.tensors))
    def generate_noise(self,input_latent):
        from comfy.nested_tensor import NestedTensor
        target=input_latent['samples']
        if not getattr(target,'is_nested',False):raise ValueError('complete AV target required')
        ts=target.unbind()
        if len(ts)!=2 or any(t.shape!=n.shape or t.dtype!=torch.float32 for t,n in zip(ts,self.tensors)):raise ValueError('noise/target geometry or dtype differs')
        if any(bool(torch.count_nonzero(t)) for t in ts):raise ValueError('original target must be zero')
        return NestedTensor([t.clone() for t in self.tensors])

class H3HistoricalNoise:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'noise_file':('STRING',),'noise_sha256':('STRING',),'seed':('INT',{'default':2026101701,'min':0,'max':0xffffffffffffffff})}}
    RETURN_TYPES=('NOISE',);FUNCTION='load';CATEGORY='research/H3PassiveReplay'
    def load(self,noise_file,noise_sha256,seed):return (HistoricalNoise(noise_file,noise_sha256,seed),)
