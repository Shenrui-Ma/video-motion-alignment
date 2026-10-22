from pathlib import Path
import subprocess,tarfile,json,hashlib,io
b=Path(__file__).resolve().parent
remote='/data4/researcher/h3_runs/timing_phase_combined_r148_20261020/cases'
rows=[]
for sid in ('short_0252','short_0358','long_0039','long_0059'):
 root=b/'cases'/sid
 rels=['scripts/start_controller.py','scripts/job.py','scripts/run_queue.py','scripts/preflight.py','configs/runtime.json','tests/test_startup.py','deploy_manifest.json']
 if (root/'configs/runtime_device_rebind.json').exists():rels+=['configs/runtime_device_rebind.json']
 payload=io.BytesIO()
 with tarfile.open(fileobj=payload,mode='w:gz') as t:
  for rel in rels:t.add(root/rel,arcname=rel)
 script=f'''import pathlib,json,hashlib,subprocess,sys,tarfile,io
root=pathlib.Path({str(remote+'/'+sid)!r})
assert not (root/'processes/service.json').exists(),'registered service present; root recovery required'
archive=root/'audit/controller_gate_fix_before';archive.mkdir(exist_ok=True)
rels={rels!r}
for rel in rels:
 p=root/rel;a=archive/rel
 if p.exists() and not a.exists():a.parent.mkdir(parents=True,exist_ok=True);a.write_bytes(p.read_bytes())
data=sys.stdin.buffer.read();tarfile.open(fileobj=io.BytesIO(data),mode='r:gz').extractall(root)
manifest=json.loads((root/'deploy_manifest.json').read_text())
for name,row in manifest['files'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==row['sha256'],name
r=subprocess.run(['python3','-m','unittest','discover','-s','tests','-p','test_startup.py','-v'],cwd=root,capture_output=True,text=True)
assert r.returncode==0,r.stderr
sys.path.insert(0,str(root/'scripts'))
import preflight
smoke=json.loads((root/'audit/RUNTIME_IMPORT_SMOKE.json').read_text());assert preflight.runtime_smoke_matches(root,smoke)
print(json.dumps({{'case':{sid!r},'seal':hashlib.sha256((root/'deploy_manifest.json').read_bytes()).hexdigest(),'startup_tests':4,'passed':True,'all_sealed_files_verified':True,'prior_CPU_smoke_bound':True}}))
'''
 # Python source via argv; stdin remains the small tar stream.
 import shlex
 result=subprocess.run(['ssh','H3_SERVER_B','python3 -c '+shlex.quote(script)],input=payload.getvalue(),capture_output=True)
 print(result.stdout.decode(),result.stderr.decode(),flush=True)
 if result.returncode:raise SystemExit(result.returncode)
 rows.append(json.loads(result.stdout))
(b/'CONTROLLER_FIX_HANDOFF.json').write_text(json.dumps(rows,indent=2)+'\n')
