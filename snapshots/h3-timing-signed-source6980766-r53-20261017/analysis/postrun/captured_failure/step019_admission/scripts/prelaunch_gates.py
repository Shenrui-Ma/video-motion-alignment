"""Require this case's 87366-token GPU gate; inherit only frozen numerical code."""
import json,hashlib
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def require(ok,message):
    if not ok:raise ValueError(message)

def check_layout_case(k,condition):
    actual=[v for v in k['cases'] if v['actual_shape']]
    require(len(actual)==1,'exactly one actual layout gate required')
    a=actual[0];segments=condition['packed_layout']['segments'];n=condition['packed_layout']['seq_len']
    target=[s for s in segments if s[2]=='video'];ref=[s for s in segments if s[2]=='ref_img' and s[1]-s[0]==42*943]
    require(len(target)==len(ref)==1,'ambiguous actual reference/target layout')
    expected={'seq_len':n,'frame_rows':943,'latent_interval_half_open':[0,42],'query_interval_half_open':target[0][:2],'reference_video_segment':ref[0][:2]}
    require(a['shape']==[1,56,n,128] and a['plan']==expected,'new actual kernel layout differs')
    require(all(v['passed'] and all(v['checks'].values()) for v in k['cases']),'partial kernel failure')

def inherited_bridge(root):
    spec=read(root/'configs/r27_inheritance.json');parent=Path(spec['parent_root'])
    require(sha(parent/'deploy_manifest.json')==spec['parent_deploy_manifest_sha256'],'R27 sealed parent differs')
    require(sha(parent/'configs/protocol.json')==spec['parent_protocol_sha256'],'R27 protocol differs')
    for name,digest in spec['exact_numerical_files'].items():
        require(sha(root/name)==sha(parent/name)==digest,'inherited numerical source changed: '+name)
    bp=parent/'audit/known_endpoint_bridge.json';b=read(bp);kp=parent/'audit/gpu_dynamic_union_gate.json';k=read(kp)
    require(b['schema']=='r27-known-endpoint-gate-v1' and b['passed'] is True and b['NFE']==0 and b['model_forward_calls']==0,'R27 actual endpoint bridge absent/failed')
    require(k['schema']=='h3-r27-kernel-gate-v1' and k['passed'] is True and k['NFE']==0,'R27 actual kernel gate absent/failed')
    require(b['protocol_sha256']==k['protocol_sha256']==spec['parent_protocol_sha256'],'R27 GPU evidence protocol differs')
    for evidence in (b,k):
        for name,digest in evidence['source_sha256'].items():require(sha(parent/name)==digest,'parent GPU evidence source changed: '+name)
    require(all(b['checks'].values()) and all(v['passed'] and all(v['checks'].values()) for v in k['cases']),'partial R27 GPU gate failure')
    return {'known_endpoint_file':str(bp),'known_endpoint_gate_sha256':sha(bp),'parent_kernel_gate_sha256':sha(kp),'inheritance_sha256':sha(root/'configs/r27_inheritance.json'),'scope':spec['inherited_scope']}

def check(root):
    root=Path(root);protocol=sha(root/'configs/protocol.json')
    spec=read(root/'configs/kernel_inheritance.json');parent=Path(spec['parent_root'])
    require(sha(parent/'deploy_manifest.json')==spec['parent_deploy_manifest_sha256'],'R40 parent seal changed')
    require(sha(parent/'configs/protocol.json')==spec['parent_protocol_sha256'],'R40 parent protocol changed')
    for name,digest in spec['exact_numerical_files'].items():require(sha(root/name)==sha(parent/name)==digest,'R40 inherited numerical bytes changed: '+name)
    kp=root/'audit/gpu_dynamic_union_gate.json';rp=root/'audit/resource_admission.json';k=read(kp)
    require(k['schema']=='h3-r27-kernel-gate-v1' and k['passed'] is True and k['NFE']==0,'R53 actual kernel absent/failed')
    require(k['protocol_sha256']==protocol,'current kernel protocol differs')
    for name,digest in k['source_sha256'].items():require(sha(root/name)==digest,'current actual kernel evidence changed: '+name)
    check_layout_case(k,read(root/'configs/parent_conditioning.json'))
    inherited=inherited_bridge(root);r=read(rp)
    require(r['schema']=='r53-root-resource-admission-v1' and r['root_approved'] is True,'root resource review missing')
    require(r['gpu_uuid']=='GPU-REDACTED','resource GPU differs')
    require(r['kernel_gate_sha256']==sha(kp) and r['known_endpoint_gate_sha256']==inherited['known_endpoint_gate_sha256'] and r['inheritance_sha256']==inherited['inheritance_sha256'] and r['kernel_inheritance_sha256']==sha(root/'configs/kernel_inheritance.json') and r['protocol_sha256']==protocol,'resource review unbound to gates')
    for key in ('model_resident_measured_bytes','routing_increment_bound_bytes','decoder_peak_reserved_bytes','total_memory_bytes','estimated_combined_bytes'):
        require(type(r[key]) is int and r[key]>0,'invalid resource estimate '+key)
    require(r['estimated_combined_bytes']>=sum(r[key] for key in ('model_resident_measured_bytes','routing_increment_bound_bytes','decoder_peak_reserved_bytes')),'resource total omits component')
    require(r['estimated_combined_bytes']<=r['total_memory_bytes'],'resource estimate exceeds device')
    require(r['required_free_before_decoder_mib']>=12288,'decoder headroom relaxed')
    require(r['total_memory_bytes']-r['model_resident_measured_bytes']-r['routing_increment_bound_bytes']>=r['required_free_before_decoder_mib']*1024*1024,'predicted decoder admission headroom insufficient')
    require(r['scope']=='single GPU isolated exec; runtime exact-parent admission remains mandatory','resource scope differs')
    require(isinstance(r['evidence'],list) and len(r['evidence'])>=2,'missing residence/free-memory evidence')
    for row in r['evidence']:require(sha(Path(row['file']))==row['sha256'],'resource evidence changed')
    return {'kernel_gate_sha256':sha(kp),'inherited_bridge':inherited,'resource_admission_sha256':sha(rp)}
