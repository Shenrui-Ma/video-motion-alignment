"""Physical intervals to unique H3 nominal time bins, with full spatial support."""
import importlib
from .dependencies import router, layout
QueryGain = importlib.import_module(router.__package__+'.mask').QueryGain

def bins_for(intervals):
    bins=set();mapping=[]
    for value in intervals:
        if not isinstance(value,(list,tuple)) or len(value)!=2 or any(type(x) is not int for x in value):
            raise ValueError('physical intervals require integer inclusive bounds')
        a,b=value
        if not 0<=a<=b<141:raise ValueError('physical interval outside141frames')
        lo,hi=layout.event_latent_range(a,b,42)
        bins.update(range(lo,hi));mapping.append({'physical_interval':[a,b],'latent_interval_half_open':[lo,hi]})
    return sorted(bins),mapping

def make_gain(bins,spatial_shape=(23,41)):
    import torch
    if list(bins)!=sorted(set(bins)) or any(type(i) is not int or not 0<=i<42 for i in bins):
        raise ValueError('bins require sorted unique integers0..41')
    values=torch.zeros((42,*spatial_shape),dtype=torch.float32,device='cpu')
    if bins:values[bins]=1
    return QueryGain(values,expected_shape=values.shape)
