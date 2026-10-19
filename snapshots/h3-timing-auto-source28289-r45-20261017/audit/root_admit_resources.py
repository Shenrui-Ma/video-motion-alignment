from pathlib import Path
import json,hashlib,subprocess,time,socket
r=Path('/data5/researcher/h3_runs/timing_auto_source28289_r45_20261017')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
procs=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader,nounits'],text=True,timeout=15);own=[]
for ln in procs.splitlines():
 a=[s.strip()for s in ln.split(',')];pid=int(a[0]);uid=(Path('/proc')/str(pid)).stat().st_uid
 if uid==1016:own.append((pid,a[1]))
assert own==[],own
gpu=subprocess.check_output(['nvidia-smi','-i','3','--query-gpu=uuid,memory.total,memory.used,memory.free','--format=csv,noheader,nounits'],text=True,timeout=15).strip();a=[s.strip()for s in gpu.split(',')];assert a[0]=='GPU-REDACTED' and int(a[2])<16
with socket.socket() as s:s.bind(('127.0.0.1',8507))
release=Path('/data5/researcher/h3_runs/timing_source51765_native_r43_20261017/processes/cleanup.json');cleanup=json.loads(release.read_text());assert cleanup['pid']==37646 and cleanup['process_absent'] and cleanup['own_compute_absent'];assert sha(release)=='94c7e768634b4c9dd141a7ae853b741ea596e3455bafc8987ef58095d75de54f'
probe={'unix':time.time(),'gpu':gpu,'compute':procs,'own_compute':own,'peer_identity':None,'r43_cleanup_sha256':sha(release),'port8507_free':True};probe_path=r/'audit/root_current_resource_probe.json';probe_path.write_text(json.dumps(probe,indent=2)+'\n')
resource=json.loads((r/'configs/RESOURCE_ADMISSION_TEMPLATE.json').read_text());old=json.loads(Path('/data5/researcher/h3_runs/timing_auto_source51310_r40_20261017/audit/resource_admission.json').read_text());gate=json.loads((r/'audit/gpu_dynamic_union_gate.json').read_text());assert gate['passed'] and gate['NFE']==0
actual=[x for x in gate['cases'] if x['actual_shape']][0];assert actual['shape']==[1,56,87366,128];assert actual['comparisons']['full']['increment_peak_allocated_bytes']<=old['routing_increment_bound_bytes']
for k in ['known_endpoint_gate_sha256','model_resident_measured_bytes','routing_increment_bound_bytes','decoder_peak_reserved_bytes','estimated_combined_bytes','evidence']:resource[k]=old[k]
resource.update(root_approved=True,kernel_gate_sha256=sha(r/'audit/gpu_dynamic_union_gate.json'),total_memory_bytes=int(a[1])*1024*1024,observed_unix=time.time(),engineering_estimate_scope='Historical R27/R19 same model/runtime/geometry component measurements; new87366 kernel passed. Actual parent plus decoder per-step guard remains mandatory.',actual_kernel_increment_bytes=actual['comparisons']['full']['increment_peak_allocated_bytes'])
resource['evidence']=list(resource['evidence'])+[{'file':str(probe_path),'sha256':sha(probe_path)},{'file':str(r/'audit/gpu_dynamic_union_gate.json'),'sha256':sha(r/'audit/gpu_dynamic_union_gate.json')}]
assert resource['total_memory_bytes']-resource['model_resident_measured_bytes']-resource['routing_increment_bound_bytes']>=12288*1024*1024
(r/'audit/resource_admission.json').write_text(json.dumps(resource,indent=2)+'\n')
admission=json.loads((r/'configs/admission.json').read_text());admission['permitted_compute_processes']=[];admission['root_live_review_required']=False;(r/'configs/admission.json').write_text(json.dumps(admission,indent=2)+'\n')
log=r/'audit/root_full_preflight.log';done=subprocess.run(['python3',str(r/'scripts/preflight.py')],capture_output=True,text=True,timeout=120);log.write_text(done.stdout+done.stderr);print(json.dumps({'preflight_exit':done.returncode,'resource_sha256':sha(r/'audit/resource_admission.json'),'admission_sha256':sha(r/'configs/admission.json')}));print((done.stdout+done.stderr)[-600:]);raise SystemExit(done.returncode)
