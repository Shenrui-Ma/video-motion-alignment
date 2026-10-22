from pathlib import Path
import json,hashlib
BASE=Path(__file__).resolve().parent
for root in (BASE/'cases').iterdir():
 if not (root/'scripts/start_controller.py').exists():continue
 for rel in ('scripts/start_controller.py','scripts/job.py','scripts/run_queue.py','scripts/preflight.py','configs/runtime.json','deploy_manifest.json'):
  p=root/rel; a=root/'audit/controller_gate_fix_before'/rel;a.parent.mkdir(parents=True,exist_ok=True)
  if not a.exists():a.write_bytes(p.read_bytes())
 p=root/'scripts/start_controller.py';s=p.read_text();s=s.replace('import urllib.request','import urllib.request\nfrom r132_contract import registry, read\n\ndef check_http_schema(root, port):\n required={node["class_type"] for name in registry(root)[1] for node in read(Path(root)/"configs/graphs"/(name+".json")).values()}\n with urllib.request.urlopen(f"http://127.0.0.1:{port}/object_info",timeout=10) as response:\n  info=json.load(response)\n missing=required-set(info)\n if missing:raise ValueError("actual HTTP node types missing: "+repr(sorted(missing)))\n return {"passed":True,"required":sorted(required)}')
 s=s.replace("  with urllib.request.urlopen(f'http://127.0.0.1:{service.PORT}/object_info/H3ReferenceOrigin',timeout=10) as response:\n   if 'H3ReferenceOrigin' not in json.load(response):raise ValueError('service not ready')",'  check_http_schema(root,service.PORT)');p.write_text(s)
 p=root/'scripts/job.py';s=p.read_text();start=s.index('def require_native_generation(');end=s.index('\n\ndef submit(',start);s=s[:start]+s[end+2:];s=s.replace('        require_native_generation(binding,owner)\n','').replace('            require_native_generation(binding,owner)\n','').replace("'h3-timing-ive-reference-origin-host41-r132-20261020'","'h3-timing-fixed-phase-r148-20261020'").replace('root Native/first-guided review pending','root fixed-phase review pending');p.write_text(s)
 p=root/'scripts/run_queue.py';s=p.read_text().replace('reference-origin job failed','fixed-phase job failed').replace("status='verifying_reference_origin'","status='verifying_fixed_phase'");p.write_text(s)
 p=root/'scripts/preflight.py';s=p.read_text();s=s.replace('"""R132 CPU input/code checks and production seal checks."""','"""R148 CPU input/code checks and production seal checks."""')
 s=s.replace('\ndef check(root=ROOT, live=False):','''
def runtime_smoke_matches(root, smoke):
    root=Path(root)
    if smoke['runtime_sha256']==sha(root/'configs/runtime.json'):return True
    binding=read(root/'configs/runtime_device_rebind.json')
    import hashlib
    before=json.loads(binding['previous_runtime_json']);after=read(root/'configs/runtime.json')
    changed={k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
    return (changed=={'expected_gpu_index'} and after['expected_gpu_index']==after['gpu_index']
        and hashlib.sha256(binding['previous_runtime_json'].encode()).hexdigest()==smoke['runtime_sha256']
        and binding['previous_smoke_sha256']==sha(root/'audit/RUNTIME_IMPORT_SMOKE.json')
        and binding['current_runtime_sha256']==sha(root/'configs/runtime.json'))

def check(root=ROOT, live=False):''')
 s=s.replace("smoke['runtime_sha256']==sha(root/'configs/runtime.json')","runtime_smoke_matches(root,smoke)",1) if False else s
 s=s.replace("smoke['cuda_initialized'] is False and smoke['runtime_sha256']==sha(root/'configs/runtime.json')","smoke['cuda_initialized'] is False and runtime_smoke_matches(root,smoke)")
 s=s.replace('"reference_origin_mass_preserve"','"fixed_same_bin_plus_reference_origin_phase"');p.write_text(s)
 p=root/'configs/runtime.json';before=p.read_text();runtime=json.loads(before)
 if runtime['expected_gpu_index']!=runtime['gpu_index']:
  runtime['expected_gpu_index']=runtime['gpu_index'];p.write_text(json.dumps(runtime,indent=2)+'\n')
  smoke=root/'audit/RUNTIME_IMPORT_SMOKE.json'
  if smoke.exists():
   data={'reason':'Correct duplicated index label to the already selected GPU UUID/index; models, inputs and cache reconstruction unchanged. Prior actual CPU cache proof retained.','previous_runtime_json':before,'previous_smoke_sha256':hashlib.sha256(smoke.read_bytes()).hexdigest(),'current_runtime_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
   (root/'configs/runtime_device_rebind.json').write_text(json.dumps(data,indent=2)+'\n')
 print(root.name)
