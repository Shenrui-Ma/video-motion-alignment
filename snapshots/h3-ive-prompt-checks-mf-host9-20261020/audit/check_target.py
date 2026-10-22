from pathlib import Path
import sys,os,json
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from common import *
verify_seal()
for j in read(R/'configs/PLAN.json')['jobs']:validate_case(case(j['case']),j['role'])
sys.path.insert(0,str(R/'runtime/ive/metric_runtime'))
from ive_mf_adapter import verify_vendor
vendor=verify_vendor();rt=read(R/'configs/RUNTIME.json')
assert sha(rt['checkpoint'])==rt['checkpoint_sha256']
actual=R/'runtime/ive/weights/baseline_offline.pth'
assert actual.exists() and sha(actual)==rt['checkpoint_sha256']
assert not Path('/proc/17140').exists()
import torch
assert not torch.cuda.is_initialized()
value=dict(passed=True,seal=bound(R/'SEAL.json'),CUDA_initialized=False,checkpoint_actual=bound(actual),jobs=read(R/'configs/PLAN.json')['jobs'],torch=torch.__version__)
save(R/'audit/TARGET_CPU_VERIFIED.json',value)
os.environ['CUDA_VISIBLE_DEVICES']=rt['gpu_uuid']
fresh=resource_check(rt['gpu_uuid']);save(R/'audit/FRESH_ADMISSION.json',fresh)
print(json.dumps({'passed':True,'seal_sha256':sha(R/'SEAL.json'),'gpu_free_mib':fresh['memory_free_mib'],'capacity':fresh['capacity']}))
