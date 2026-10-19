"""Reuse exact input conversion; privately wrap the three frozen observer versions."""
import sys
from pathlib import Path
import importlib.util
import numpy as np
BASE=Path(__file__).resolve().parents[1]
KERNEL=BASE/'phase_shape_profile_candidate_v3/profile_v3.py'
sys.path.append(str(KERNEL.parent))
sys.path.append(str(BASE/'phase_shape_profile_candidate_v2'))
def module_at(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
INPUT_ADAPTER=module_at(BASE/'phase_shape_profile_execution_v1/adapter.py','sealed_v1_input_adapter')
THRESHOLDS=INPUT_ADAPTER.THRESHOLDS
ARMS=INPUT_ADAPTER.ARMS
CONVERTER=INPUT_ADAPTER.CONVERTER
load=INPUT_ADAPTER.load
from_features=INPUT_ADAPTER.from_features
blank=INPUT_ADAPTER.blank

def analyze(source,target,method='v3'):
    if method=='v1':return INPUT_ADAPTER.analyze(source,target)
    if method=='v2':
        core=module_at(BASE/'phase_shape_profile_candidate_v2/profile_v2.py','sealed_v2_private_adapter')
        inner=core
    elif method=='v3':
        core=module_at(KERNEL,'sealed_v3_private_adapter');inner=core.PRIVATE
    else:raise ValueError('Unknown method')
    original=inner.base
    extra={}
    class ThresholdProxy:
        def __getattr__(self,name):return getattr(original,name)
        def grid(self,a,b,part,threshold):
            result=original.grid(a[threshold],b[threshold],part,threshold)
            for key in ('raw_zero','mask','weight'):extra[f'{part}__h{threshold}__{key}']=result[key]
            return result
    inner.base=ThresholdProxy()
    result,evidence=core.analyze(source,target);evidence.update(extra)
    return result,evidence

def analyze_all(source,target):
    methods={};evidence={}
    for name in ('v1','v2','v3'):
        methods[name],arrays=analyze(source,target,name)
        evidence.update({name+'__'+k:v for k,v in arrays.items()})
    for key in [k for k in evidence if k.startswith('v2__')]:
        if not np.array_equal(evidence[key],evidence['v3__'+key[4:]],equal_nan=True):
            raise ValueError('v2/v3 candidate evidence changed: '+key)
    for part in methods['v2']['parts']:
        if methods['v2']['parts'][part]['counts']!=methods['v3']['parts'][part]['counts']:
            raise ValueError('v2/v3 candidate counts changed')
    return methods,evidence
