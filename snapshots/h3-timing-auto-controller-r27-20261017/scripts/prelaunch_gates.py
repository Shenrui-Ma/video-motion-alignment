"""Require actual root-run evidence; never fabricate or infer GPU approval."""
import json,hashlib
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def require(ok,message):
    if not ok:raise ValueError(message)

def check(root):
    root=Path(root);protocol=sha(root/'configs/protocol.json')
    kp=root/'audit/gpu_dynamic_union_gate.json';bp=root/'audit/known_endpoint_bridge.json';rp=root/'audit/resource_admission.json'
    k=read(kp);b=read(bp);r=read(rp)
    require(k['schema']=='h3-r27-kernel-gate-v1' and k['passed'] is True and k['NFE']==0,'actual kernel gate absent/failed')
    require(b['schema']=='r27-known-endpoint-gate-v1' and b['passed'] is True and b['NFE']==0 and b['model_forward_calls']==0,'known endpoint gate absent/failed')
    require(k['protocol_sha256']==b['protocol_sha256']==protocol,'GPU evidence protocol differs')
    for evidence in (k,b):
        for name,digest in evidence['source_sha256'].items():require(sha(root/name)==digest,'GPU evidence source changed: '+name)
    actual=[v for v in k['cases'] if v['actual_shape']]
    require(len(actual)==1 and actual[0]['shape'][1]==56 and actual[0]['plan']['latent_interval_half_open']==[0,42],'kernel worst-mask geometry missing')
    require(all(v['passed'] and all(v['checks'].values()) for v in k['cases']),'partial kernel failure')
    require(all(b['checks'].values()),'partial endpoint bridge failure')
    require(r['schema']=='r27-root-resource-admission-v1' and r['root_approved'] is True,'root resource review missing')
    require(r['gpu_uuid']=='GPU-REDACTED','resource GPU differs')
    require(r['kernel_gate_sha256']==sha(kp) and r['known_endpoint_gate_sha256']==sha(bp),'resource review unbound to gates')
    for key in ('model_resident_measured_bytes','routing_increment_bound_bytes','decoder_peak_reserved_bytes','total_memory_bytes','estimated_combined_bytes'):
        require(type(r[key]) is int and r[key]>0,'invalid resource estimate '+key)
    require(r['estimated_combined_bytes']>=sum(r[key] for key in ('model_resident_measured_bytes','routing_increment_bound_bytes','decoder_peak_reserved_bytes')),'resource total omits component')
    require(r['estimated_combined_bytes']<=r['total_memory_bytes'],'resource estimate exceeds device')
    require(r['required_free_before_decoder_mib']>=12288,'decoder headroom relaxed')
    require(r['total_memory_bytes']-r['model_resident_measured_bytes']-r['routing_increment_bound_bytes']>=r['required_free_before_decoder_mib']*1024*1024,'predicted decoder admission headroom insufficient')
    require(r['scope']=='single GPU isolated exec; runtime exact-parent admission remains mandatory','resource scope differs')
    require(isinstance(r['evidence'],list) and len(r['evidence'])>=2,'missing residence/free-memory evidence')
    for row in r['evidence']:require(sha(Path(row['file']))==row['sha256'],'resource evidence changed')
    return {'kernel_gate_sha256':sha(kp),'known_endpoint_gate_sha256':sha(bp),'resource_admission_sha256':sha(rp)}
