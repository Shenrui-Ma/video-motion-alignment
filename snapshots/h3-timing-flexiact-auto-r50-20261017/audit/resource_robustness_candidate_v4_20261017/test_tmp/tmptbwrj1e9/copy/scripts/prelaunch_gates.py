"""Require the five actual47-bin GPU layout gates; inherit only frozen numerical code."""
import json,hashlib
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def require(ok,message):
    if not ok:raise ValueError(message)

def check_layout_cases(k, root):
    actual=[v for v in k['cases'] if v['actual_shape']]
    cases=read(root/'configs/protocol.json')['cases']
    require([v.get('case_run') for v in actual]==[c['run_id'] for c in cases],'all five actual layout gates required')
    for a,case in zip(actual,cases):
        condition=read(root/case['parent_conditioning'])
        segments=condition['packed_layout']['segments'];n=condition['packed_layout']['seq_len']
        target=[s for s in segments if s[2]=='video'];ref=[s for s in segments if s[2]=='ref_img' and s[1]-s[0]==47*864]
        require(len(target)==len(ref)==1,'ambiguous actual reference/target layout')
        expected={'seq_len':n,'frame_rows':864,'latent_interval_half_open':[0,47],'query_interval_half_open':target[0][:2],'reference_video_segment':ref[0][:2]}
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

def check_engineering_revision(root):
    root=Path(root);spec=read(root/'configs/engineering_revision_v2.json')
    oldp=root/spec['previous_protocol_file'];old=read(oldp);current=read(root/'configs/protocol.json')
    require(sha(oldp)==spec['previous_protocol_sha256'],'previous protocol changed')
    require({k:v for k,v in old.items() if k!='resources'}=={k:v for k,v in current.items() if k!='resources'},'engineering revision changed scientific protocol')
    from retry_inheritance import inherited_file,check as check_retry
    check_retry(root,inputs=False)
    for rel,digest in spec['unchanged_scientific_files'].items():inherited_file(root,rel,digest)
    require(current['resources']['main_uuid']=='GPU-REDACTED' and current['resources']['decoder_uuid']=='GPU-REDACTED','engineering device placement changed')
    require(current['resources']['single_gpu_isolated_decoder'] is False and current['resources']['maximum_own_GPUs']==2,'engineering resource mode changed')
    from observer_import import t
    profile=t.decoder_memory_profile()
    require(current['resources']['decoder_memory_profile_sha256']==profile['profile_sha256'] and current['resources']['decoder_required_free_MiB']*1024**2>=profile['required_free_bytes'],'decoder measured memory admission differs')
    return spec

def check(root):
    root=Path(root);protocol=sha(root/'configs/protocol.json');revision=check_engineering_revision(root)
    spec=read(root/'configs/kernel_inheritance.json');parent=Path(spec['parent_root'])
    require(sha(parent/'deploy_manifest.json')==spec['parent_deploy_manifest_sha256'],'R40 parent seal changed')
    require(sha(parent/'configs/protocol.json')==spec['parent_protocol_sha256'],'R40 parent protocol changed')
    for name,digest in spec['exact_numerical_files'].items():require(sha(root/name)==sha(parent/name)==digest,'R40 inherited numerical bytes changed: '+name)
    kp=root/'configs/engineering_v2/previous_kernel_gate.json';rp=root/'audit/resource_admission_v2.json';k=read(kp)
    require(sha(kp)==revision['previous_kernel_gate_sha256'],'previous actual kernel gate changed')
    require(k['schema']=='h3-r27-kernel-gate-v1' and k['passed'] is True and k['NFE']==0,'R50 actual kernel absent/failed')
    require(k['protocol_sha256']==revision['previous_protocol_sha256'],'prior actual kernel protocol differs')
    for name,digest in k['source_sha256'].items():require(sha(root/name)==digest,'actual kernel numerical source changed: '+name)
    check_layout_cases(k,root)
    inherited=inherited_bridge(root);r=read(rp)
    dp=root/'audit/known_endpoint_158_split_gate.json';decoded=read(dp)
    require(decoded['schema']=='r50-full158-decoder-gate-v1' and decoded['passed'] is True and decoded['NFE']==0 and decoded['model_forward_calls']==0,'actual dedicated full158 decoder gate missing')
    require(decoded['protocol_sha256']==protocol and all(decoded['checks'].values()),'dedicated decoder gate protocol/check differs')
    require(decoded['GPU_admission']['uuid']=='GPU-REDACTED' and decoded['checks']['revision1_RGB_exact'] and decoded['checks']['revision1_tensor_exact'],'dedicated decode differs from prior numerical result')
    for name,digest in decoded['source_sha256'].items():require(sha(root/name)==digest,'full158 decoder gate source changed: '+name)
    require(sha(Path(decoded['decode_file']))==decoded['decode_sha256'],'full158 decode artifact changed')
    require(r['schema']=='r50-root-two-GPU-resource-admission-v2' and r['root_approved'] is True,'root two-GPU resource review missing')
    require(r['main_gpu_uuid']=='GPU-REDACTED' and r['decoder_gpu_uuid']=='GPU-REDACTED','resource devices differ')
    require(r['protocol_sha256']==protocol and r['engineering_revision_sha256']==sha(root/'configs/engineering_revision_v2.json') and r['kernel_gate_sha256']==sha(kp) and r['decoder_gate_sha256']==sha(dp),'resource review unbound to gates')
    for key in ('main_native_peak_sampled_bytes','routing_increment_bound_bytes','main_margin_bytes','main_total_memory_bytes','main_estimated_peak_bytes','decoder_peak_reserved_bytes','decoder_total_memory_bytes'):
        require(type(r[key]) is int and r[key]>0,'invalid resource estimate '+key)
    require(r['main_margin_bytes']>=1024**3,'main safety margin below1GiB')
    require(r['main_estimated_peak_bytes']>=r['main_native_peak_sampled_bytes']+r['routing_increment_bound_bytes']+r['main_margin_bytes'] and r['main_estimated_peak_bytes']<=r['main_total_memory_bytes'],'main device capacity estimate failed')
    require(r['decoder_peak_reserved_bytes']>=decoded['decode']['max_memory_reserved_bytes'] and r['decoder_peak_reserved_bytes']<=r['decoder_total_memory_bytes'],'dedicated decoder capacity estimate failed')
    from observer_import import t
    profile=t.decoder_memory_profile()
    require(r['decoder_memory_profile_sha256']==profile['profile_sha256'] and r['required_free_before_decoder_mib']*1024**2>=profile['required_free_bytes'],'dedicated decoder measured headroom differs')
    require(r['scope']=='GPU3 main model; GPU2 isolated full158 decoder; maximum2 owned GPUs','resource scope differs')
    require(isinstance(r['evidence'],list) and len(r['evidence'])>=3,'missing actual memory evidence')
    for row in r['evidence']:require(sha(Path(row['file']))==row['sha256'],'resource evidence changed')
    return {'kernel_gate_sha256':sha(kp),'inherited_bridge':inherited,'decoder_gate_sha256':sha(dp),'engineering_revision_sha256':sha(root/'configs/engineering_revision_v2.json'),'resource_admission_sha256':sha(rp)}
