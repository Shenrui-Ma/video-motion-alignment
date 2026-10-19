"""Bind completed R50 shape gates to conservative measured resource bounds."""
import hashlib,json,subprocess,sys,time
from pathlib import Path
R=Path('/data5/researcher/h3_runs/timing_flexiact_auto_r50_20261017');S=Path('/data5/researcher/h3_runs/timing_signed_source6980766_r53_20261017');GPU='GPU-REDACTED'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def main():
 assert not (R/'audit/resource_admission.json').exists()
 assert sha(R/'deploy_manifest.json')=='4f1b4fbf3a30ea5baa27e9cd4feff3ac163628a61c66db14f5eb525a5c66e3f0'
 for n,v in read(R/'deploy_manifest.json')['files'].items():assert sha(R/n)==v['sha256'],n
 kp=R/'audit/gpu_dynamic_union_gate.json';dp=R/'audit/known_endpoint_158_gate.json';k=read(kp);d=read(dp)
 assert sha(kp)=='60ee5965b8c79e45572a98561e5cfa0b135720be815ede3e6b321bbc0ad4b237' and k['passed']
 assert sha(dp)=='a1493b1e2b2f14c13ae04b634ca3a58a2a50f8feeadeaa7c74c458251dd74dde' and d['passed']
 oldp=S/'audit/resource_admission.json';old=read(oldp)
 current=subprocess.check_output(['nvidia-smi','-i',GPU,'--query-gpu=uuid,memory.total,memory.used,memory.free','--format=csv,noheader,nounits'],text=True).strip();parts=[x.strip() for x in current.split(',')];assert parts[0]==GPU and int(parts[2])<1024
 resource=Path('/data5/researcher/h3_runs/timing_flexiact_native_r49_20261017/logs/resources.jsonl')
 rows=[json.loads(s) for s in resource.read_text().splitlines() if s.strip()];peak=max(int(x['sample'].split(',')[1]) for x in rows)*1024*1024
 actual=max(c['comparisons']['full']['increment_peak_allocated_bytes'] for c in k['cases'] if c['actual_shape'])
 assert actual<=old['routing_increment_bound_bytes'];assert peak<=old['model_resident_measured_bytes']
 probe=R/'audit/root_resource_probe.json';probe.write_text(json.dumps({'time':time.time(),'gpu':current,'R49_sampled_peak_bytes':peak,'R49_resources_sha256':sha(resource),'kernel_full_increment_bytes':actual,'actual158_decoder_peak_reserved_bytes':d['decode']['max_memory_reserved_bytes']},indent=2)+'\n')
 sys.path.insert(0,str(R/'scripts'));import prelaunch_gates as gates
 inherited=gates.inherited_bridge(R)
 out=dict(old,schema='r50-root-resource-admission-v1',gpu_uuid=GPU,protocol_sha256=sha(R/'configs/protocol.json'),kernel_gate_sha256=sha(kp),known_endpoint_gate_sha256=inherited['known_endpoint_gate_sha256'],inheritance_sha256=inherited['inheritance_sha256'],kernel_inheritance_sha256=sha(R/'configs/kernel_inheritance.json'),full158_decoder_gate_sha256=sha(dp),decoder_peak_reserved_bytes=max(old['decoder_peak_reserved_bytes'],d['decode']['max_memory_reserved_bytes']),total_memory_bytes=int(parts[1])*1024*1024,observed_unix=time.time(),actual_kernel_increment_bytes=actual,current_gpu=current,rationale='Conservative existing resident bound exceeds sampled same-shape R49 peak; actual five-case routing increments and full158 standalone decoder verified. Runtime exact-parent co-residence and free-memory checks remain active.')
 out['estimated_combined_bytes']=sum(out[x] for x in ['model_resident_measured_bytes','routing_increment_bound_bytes','decoder_peak_reserved_bytes'])
 out['evidence']=old['evidence']+[{'file':str(p),'sha256':sha(p)} for p in [oldp,probe,resource,kp,dp]]
 (R/'audit/resource_admission.json').write_text(json.dumps(out,indent=2)+'\n')
 result=gates.check(R);print(json.dumps({'passed':True,'resource_sha256':sha(R/'audit/resource_admission.json'),'gates':result}))
if __name__=='__main__':main()
