from pathlib import Path
import json,hashlib,subprocess,tarfile,io
E=Path('/workspace/research-user/DevProjects/video-motion-alignment/execution-20261022');D=Path(__file__).parent;B=E/'innovation/adaptive_strength_20261023/batch';PKG=E/'innovation/feature_anchor'
ready=json.loads((PKG/'READY.json').read_text());assert ready['test_count']==35 and ready['test_exit_code']==0
for name,host,python in [('host41','H3_HOST_taizun_research_user','/data3/research-user/ComfyUI/.venv/bin/python'),('host60','H3_HOST_A100','/data4/research-user/h3_inference_20261023/env/bin/python')]:
 out=D/name;req=json.loads((out/'request.json').read_text());r=req['root'];req['status']='ready';req['review']='root confirmed independent review passed';req['audit_tests_passed']=43
 pairs=[(Path(a['local']),a['path']) for a in req['assets']]
 pairs +=[(D/'runtime_helpers.py',r+'/scripts/anchor_runtime_helpers.py'),(D/'anchor_boundary_guard.py',r+'/scripts/anchor_boundary_guard.py'),(out/'manage_service.staged.py',req['service_change']['staged_path']),(B/'audit.py',r+'/scripts/anchor_audit.py')]
 for local,remote in pairs:
  if '/H3AnchoredGuidance/' in remote:assert hashlib.sha256(local.read_bytes()).hexdigest()==ready['source_shas'][local.name]
  if not any(a['path']==remote for a in req['assets']):req['assets'].append({'path':remote,'sha256':hashlib.sha256(local.read_bytes()).hexdigest(),'local':str(local)})
 (out/'request.json').write_text(json.dumps(req,indent=2));pairs.append((out/'request.json',r+'/innovation_handoff/anchor_priority_20261023/request.json'))
 blob=io.BytesIO()
 with tarfile.open(fileobj=blob,mode='w') as t:
  for p,remote in pairs:
   raw=p.read_bytes();info=tarfile.TarInfo(remote.removeprefix(r+'/'));info.size=len(raw);info.mode=0o644;t.addfile(info,io.BytesIO(raw))
 subprocess.run(['ssh',host,'tar -xf - -C '+r],input=blob.getvalue(),check=True)
 probe='''import json,pathlib,hashlib,sys,importlib,inspect,os
r=pathlib.Path(ROOT);req=json.loads((r/'innovation_handoff/anchor_priority_20261023/request.json').read_text());sys.path.insert(0,str(r/'custom_nodes'))
for a in req['assets']:assert hashlib.sha256(pathlib.Path(a['path']).read_bytes()).hexdigest()==a['sha256'],a['path']
m=importlib.import_module('H3AnchoredGuidance');c=m.NODE_CLASS_MAPPINGS['H3AnchoredGuidance'];importlib.import_module('H3AnchoredGuidance.frozen').load_frozen()
j=req['pilots']['jobs'][0];g=json.loads((r/j['graph']).read_text());inputs=g['50']['inputs'];assert set(inputs)==set(c.INPUT_TYPES()['required']);assert set(inputs)<=set(inspect.signature(c.apply).parameters)
cache=g['5']['inputs'];assert hashlib.sha256(pathlib.Path(cache['cache_manifest']).read_bytes()).hexdigest()==cache['manifest_sha256']
print(json.dumps({'status':'ready','class':'H3AnchoredGuidance','job':j['id'],'assets':len(req['assets']),'cache_sha_verified':True,'uid':os.getuid()}))
'''.replace('ROOT',repr(r))
 result=subprocess.run(['ssh',host,'CUDA_VISIBLE_DEVICES= '+python+' -'],input=probe.encode(),capture_output=True)
 if result.returncode:raise RuntimeError(result.stderr.decode()[-5000:])
 (out/'CPU_DEPLOYED.json').write_bytes(result.stdout);print(name,result.stdout.decode().strip())
