import sys,os,json
from common import *
verify_seal()
for key in read(ROOT/'configs/PLAN.json')['groups']:
 for role in ['source']+[x['role']for x in read(case(key)/'INPUTS.json')['targets']]:validate_case(case(key),role)
sys.path.insert(0,str(ROOT/'runtime/ive/metric_runtime'))
from ive_mf_adapter import verify_vendor,sha as vs
verify_vendor();rt=read(ROOT/'configs/RUNTIME.json');assert vs(rt['checkpoint'])==rt['checkpoint_sha256']
import torch
assert not torch.cuda.is_initialized()
print(json.dumps({'passed':True,'CUDA_initialized':False,'torch':torch.__version__,'seal_sha256':sha(ROOT/'SEAL.json'),'cases':read(ROOT/'configs/PLAN.json')['groups'],'new_trackers':6,'source_trackers':0}))
