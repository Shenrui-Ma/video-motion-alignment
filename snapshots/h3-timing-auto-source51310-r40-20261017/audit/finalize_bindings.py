from pathlib import Path
import json,hashlib
r=Path(__file__).resolve().parents[1];o=r.parent/'h3-timing-auto-bedside-r35-20261017'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
b=read(o/'configs/observer_bindings.json');b['schema']='r40-frozen-auto-window-bindings-v1'
b['local_files']={name:sha(r/name) for name in b['local_files'] if (r/name).exists()}
for name in ('configs/kernel_inheritance.json','configs/inherited_actual87361_kernel.json','configs/parent_history.json','configs/parent_router.json','configs/parent_runtime_gate.json','configs/r28_parent_manifest.json'):
 b['local_files'][name]=sha(r/name)
write(r/'configs/observer_bindings.json',b)
copies=read(r/'audit/raw_evidence_copy.json');write(r/'configs/parent_evidence_bindings.json',{name:{'source':v['source'],'sha256':v['sha256']} for name,v in copies.items()})
spec=read(r/'configs/r27_inheritance.json');assert len(spec['exact_numerical_files'])==17
for name,digest in spec['exact_numerical_files'].items():assert sha(r/name)==digest,name
write(r/'audit/resource_admission.TEMPLATE.json',{'schema':'r40-root-resource-admission-v1','root_approved':False,'gpu_uuid':'GPU-REDACTED','kernel_gate_sha256':sha(r/'configs/inherited_actual87361_kernel.json'),'known_endpoint_gate_sha256':'ROOT_COPY_ACTUAL_R27_KNOWN_GATE_SHA','inheritance_sha256':sha(r/'configs/r27_inheritance.json'),'kernel_inheritance_sha256':sha(r/'configs/kernel_inheritance.json'),'protocol_sha256':sha(r/'configs/protocol.json'),'model_resident_measured_bytes':None,'routing_increment_bound_bytes':None,'decoder_peak_reserved_bytes':None,'total_memory_bytes':None,'estimated_combined_bytes':None,'required_free_before_decoder_mib':12288,'scope':'single GPU isolated exec; runtime exact-parent admission remains mandatory','evidence':[]})
print('17 numerical exact; bindings',sha(r/'configs/observer_bindings.json'))
