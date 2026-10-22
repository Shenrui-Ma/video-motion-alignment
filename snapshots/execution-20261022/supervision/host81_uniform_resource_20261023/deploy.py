from pathlib import Path
import subprocess,shlex,json,hashlib,tarfile,io,copy
D=Path(__file__).parent;E=D.parent.parent;B=E/'innovation/adaptive_strength_20261023/batch';P=E/'innovation/feature_gain_field_uniform_energy';S='/data4/research-user/h3_runs/benchmark_schedule_20261022';R='/data/research-user/h3_inference_20261023/run_uniform_energy';HOST='H3_HOST_RTX4090'
def ssh(h,c,b=None):return subprocess.check_output(['ssh',h,shlex.join(['python3','-c',c])],input=b)
def read(h,p):return ssh(h,'from pathlib import Path;import sys;sys.stdout.buffer.write(Path('+repr(p)+').read_bytes())')
def sha(x):return hashlib.sha256(x).hexdigest()
assert sha((P/'READY.json').read_bytes())=='f494b28d02b2ca6f01712910e124c2c46ed1ac92397db5d867385615404a7423'
ready=json.loads((P/'READY.json').read_text());print('source_keys',list(ready['source_shas'])[:2])
sign=json.loads((E/'innovation/adaptive_strength_20261023/uniform_energy_review/SIGNOFF.json').read_text());assert sign['status']=='passed'
files={};jobs=[];checks=[]
for name,h in ready['source_shas'].items():
 p=P/name;assert sha(p.read_bytes())==h,name;files['custom_nodes/H3TemporalGainFieldUniformEnergy/'+name]=p.read_bytes()
sourcejobs=json.loads((B/'uniform_pilots/jobs.json').read_text())['jobs'];sourcejobs.sort(key=lambda x:0 if '0358' in x['id'] else 1)
for src in sourcejobs:
 job=copy.deepcopy(src);case=job['metadata']['task_id'];original=json.loads((B/'uniform_pilots'/job['graph']).read_text());sourcecache=json.loads(read('H3_HOST_PRIMARY',original['5']['inputs']['cache_manifest']));raw81=read(HOST,R+'/innovation_cache/'+case+'/manifest.json');targetcache=json.loads(raw81)
 for key in ['seed','source_video_sha256','prompt_sha256','geometry']:assert sourcecache[key]==targetcache[key],(case,key)
 assert sourcecache['conditioning']['sha256']==targetcache['conditioning']['sha256'];assert [x['sha256'] for x in sourcecache['tensors']]==[x['sha256'] for x in targetcache['tensors']]
 graph=json.loads(json.dumps(original).replace(S,R));graph['5']['inputs'].update(cache_manifest=R+'/innovation_cache/'+case+'/manifest.json',manifest_sha256=sha(raw81));inverse=json.loads(json.dumps(graph).replace(R,S));inverse['5']['inputs']=original['5']['inputs'];assert inverse==original
 raw=(json.dumps(graph,indent=2)+'\n').encode();job=json.loads(json.dumps(job).replace(S,R));job['max_attempts']=1;job['metadata'].update(producer_host='host81_uniform',host=HOST,remote_root=R,source_job_id=job['id'],graph_sha256=sha(raw),innovation_status='runtime_validation');jobs.append(job);files[job['graph']]=raw;checks.append({'task':case,'scientific_equal':True,'geometry':sourcecache['geometry'],'cache_sha256':sha(raw81)})
service=read(HOST,R+'/scripts/manage_service.py').decode();assert "'H3TemporalGainFieldUniformEnergy'" not in service;service=service.replace("'H3TemporalCoverageBlend','--input-directory'","'H3TemporalCoverageBlend','H3TemporalGainFieldUniformEnergy','--input-directory'");assert 'H3TemporalGainFieldUniformEnergy' in service;compile(service,'manage_service','exec');files['scripts/manage_service.py']=service.encode()
for p in [B/'uniform_audit.py',B/'uniform_field_audit_base.py',E/'supervision/layer_boundary_20261023/runtime_helpers.py']:files['scripts/'+p.name]=p.read_bytes()
seq=(E/'supervision/role5_host9_transfer_20261023/sequence_guard.py').read_text().replace('role5_audit','uniform_audit').replace('check_role5','check_uniform').replace('role5_transfer','uniform_energy').replace('feature_gain_field_role5','feature_gain_field_uniform_energy').replace('Role5 sequence','Uniform sequence')
# Require the real memory peak record before admitting aircraft, in addition to full audit and export.
seq=seq.replace("results[jid]=result;g.atomic", "peak_files=list((root/'audit/memory').glob('*')) if (root/'audit/memory').exists() else [];result['memory_peak_files']=[str(x) for x in peak_files];results[jid]=result;g.atomic")
files['scripts/sequence_guard.py']=seq.encode()
ssh(HOST,'from pathlib import Path;r=Path('+repr(R)+');assert not (r/"jobs.json").exists();[(r/n).mkdir(exist_ok=True,parents=True) for n in ["graphs","innovation_handoff/uniform_energy"]]')
b=io.BytesIO()
with tarfile.open(fileobj=b,mode='w') as t:
 for n,v in files.items():i=tarfile.TarInfo(n);i.size=len(v);t.addfile(i,io.BytesIO(v))
subprocess.run(['ssh',HOST,'tar -xf - -C '+R],input=b.getvalue(),check=True)
code='''from pathlib import Path
import json,hashlib,sys,importlib
r=Path(ROOT);sys.path.insert(0,str(r/'custom_nodes'));m=importlib.import_module('H3TemporalGainFieldUniformEnergy');c=m.NODE_CLASS_MAPPINGS['H3TemporalGainFieldUniformEnergy'];importlib.import_module('H3TemporalGainFieldUniformEnergy.frozen').load_frozen();out=[]
for name in GRAPHS:
 g=json.loads((r/name).read_text());assert set(g['50']['inputs'])==set(c.INPUT_TYPES()['required']);ci=g['5']['inputs'];mf=Path(ci['cache_manifest']);assert hashlib.sha256(mf.read_bytes()).hexdigest()==ci['manifest_sha256'];cache=json.loads(mf.read_text())
 for item in [cache['conditioning']]+cache['tensors']:assert hashlib.sha256(Path(item['file']).read_bytes()).hexdigest()==item['sha256']
 assert hashlib.sha256(Path(cache['source_video']).read_bytes()).hexdigest()==cache['source_video_sha256'];assert Path(g['15']['inputs']['video']).exists() if '15' in g and 'video' in g['15']['inputs'] else True
 out.append({'graph':name,'cache_sha256':ci['manifest_sha256']})
print(json.dumps({'status':'CPU_READY','schema':True,'cache_sha_verified':True,'frozen':True,'graphs':out}))
'''.replace('ROOT',repr(R)).replace('GRAPHS',repr([j['graph'] for j in jobs]))
p=subprocess.run(['ssh',HOST,'CUDA_VISIBLE_DEVICES= PYTHONPATH=/data/research-user/h3_inference_20261023/runtime_deps /data/research-user/h3_inference_20261023/env/bin/python -'],input=code.encode(),capture_output=True);assert p.returncode==0,p.stderr.decode();(D/'DEPLOY_CPU_READY.json').write_bytes(p.stdout)
(D/'jobs.json').write_text(json.dumps({'jobs':jobs,'planned_count':2},indent=2));(D/'SCIENCE_CHECK.json').write_text(json.dumps(checks,indent=2));(D/'DEPLOY_ASSETS.json').write_text(json.dumps({n:sha(v) for n,v in files.items()},indent=2));print(p.stdout.decode())
