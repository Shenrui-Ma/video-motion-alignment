"""Root resource evidence plus exact same87592 inherited numerical kernel; no model launch."""
from pathlib import Path
from r37_contract import read,sha

def require(ok,message):
 if not ok:raise ValueError(message)
def check_kernel(k,condition):
 require(k['schema']=='h3-r27-kernel-gate-v1' and k['passed'] is True and k['NFE']==0,'inherited kernel gate not pass')
 require(all(v['passed'] and all(v['checks'].values()) for v in k['cases']),'partial inherited kernel failure')
 actual=[v for v in k['cases'] if v['actual_shape']];require(len(actual)==1,'actual kernel case missing')
 a=actual[0];segs=condition['packed_layout']['segments'];target=[s for s in segs if s[2]=='video'];ref=[s for s in segs if s[2]=='ref_img' and s[1]-s[0]==42*943]
 require(len(target)==len(ref)==1 and condition['packed_layout']['seq_len']==87592,'actual packed geometry')
 expected={'seq_len':87592,'frame_rows':943,'latent_interval_half_open':[0,42],'query_interval_half_open':target[0][:2],'reference_video_segment':ref[0][:2]}
 require(a['shape']==[1,56,87592,128] and a['plan']==expected,'kernel plan differs from parent condition')
def check(root):
 root=Path(root);spec=read(root/'configs/kernel_inheritance.json');parent=Path(spec['parent_root']);kp=parent/'audit/gpu_dynamic_union_gate.json';k=read(kp)
 require(sha(parent/'deploy_manifest.json')==spec['parent_manifest_sha256'],'parent manifest changed')
 require(sha(parent/'configs/protocol.json')==spec['parent_protocol_sha256']==k['protocol_sha256'],'kernel protocol differs')
 require(sha(kp)==spec['kernel_gate_sha256'],'kernel evidence changed')
 for name,d in read(root/'configs/kernel_provenance.json').items():require(sha(root/name)==sha(Path(d['remote_parent_file']))==d['sha256'],'numerical source inheritance differs '+name)
 for name,d in k['source_sha256'].items():require(sha(parent/name)==d,'source of inherited gate changed '+name)
 check_kernel(k,read(root/'configs/parent_conditioning.json'));a=read(root/'audit/resource_admission.json')
 require(a['schema']=='r37-root-resource-admission-v1' and a['root_approved'] is True,'root admission pending')
 require(a['protocol_sha256']==sha(root/'PROTOCOL.json') and a['gpu_uuid']=='GPU-REDACTED','root protocol/GPU differs')
 require(a['kernel_gate_sha256']==sha(kp) and a['kernel_inheritance_sha256']==sha(root/'configs/kernel_inheritance.json'),'resource source unbound')
 for key in ('model_resident_measured_bytes','routing_increment_bound_bytes','total_memory_bytes','estimated_combined_bytes'):require(type(a[key]) is int and a[key]>0,'invalid measured resource '+key)
 require(a['estimated_combined_bytes']>=a['model_resident_measured_bytes']+a['routing_increment_bound_bytes'] and a['estimated_combined_bytes']<=a['total_memory_bytes'],'routing resource estimate invalid')
 require(a['single_CUDA_process'] is True and a['online_observers']==0,'unexpected extra process')
 require(len(a['evidence'])>=2,'resource measurements absent')
 for item in a['evidence']:require(sha(Path(item['file']))==item['sha256'],'resource evidence changed')
 return {'passed':True,'inherited_kernel_gate_sha256':sha(kp),'resource_admission_sha256':sha(root/'audit/resource_admission.json'),'scope':spec['scope']}
