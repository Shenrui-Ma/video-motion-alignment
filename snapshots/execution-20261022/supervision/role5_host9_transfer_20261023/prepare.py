from pathlib import Path
import subprocess,shlex,json,hashlib,tarfile,io,copy
D=Path(__file__).parent;E=D.parent.parent;B=E/'innovation/adaptive_strength_20261023/batch'
S='/data4/research-user/h3_runs/benchmark_schedule_20261022';PREV='/home/research-user/h3_runs/benchmark_schedule_20261022_host9a';OLD='/home/research-user/h3_runs/adaptive_blend_20261023';R='/home/research-user/h3_runs/adaptive_role5_20261023';GPU='GPU-REPLACE-WITH-DEVICE-UUID'
def ssh(h,c,b=None):return subprocess.check_output(['ssh',h,shlex.join(['python3','-c',c])],input=b)
def read(h,p):return ssh(h,'from pathlib import Path;import sys;sys.stdout.buffer.write(Path('+repr(p)+').read_bytes())')
def digest(x):return hashlib.sha256(x).hexdigest()
req=json.loads(read('H3_HOST_PRIMARY',S+'/innovation_handoff/role5_priority_20261023/request.json'));files={};jobs=[];checks=[]
for source in req['pilots']['jobs']:
 job=copy.deepcopy(source);case=job['id'].split('_')[1:3];case='_'.join(case);original=json.loads(read('H3_HOST_PRIMARY',S+'/'+job['graph']));cache=json.loads(read('H3_HOST_PRIMARY',original['5']['inputs']['cache_manifest']));raw9=read('H3_HOST_SECONDARY',PREV+'/innovation_cache/'+case+'/manifest.json');cache9=json.loads(raw9)
 for key in ['seed','source_video_sha256','prompt_sha256','geometry']:assert cache[key]==cache9[key],(case,key)
 assert cache['conditioning']['sha256']==cache9['conditioning']['sha256'];assert [x['sha256'] for x in cache['tensors']]==[x['sha256'] for x in cache9['tensors']]
 graph=json.loads(json.dumps(original).replace(S,R));graph['5']['inputs'].update(cache_manifest=PREV+'/innovation_cache/'+case+'/manifest.json',manifest_sha256=digest(raw9))
 inverse=json.loads(json.dumps(graph).replace(R,S));inverse['5']['inputs']=original['5']['inputs'];assert inverse==original
 raw=(json.dumps(graph,indent=2)+'\n').encode();job=json.loads(json.dumps(job).replace(S,R));job['max_attempts']=1;job['metadata'].update(producer_host='host9_role5',host='H3_HOST_SECONDARY',remote_root=R,source_job_id=job['id'],graph_sha256=digest(raw));jobs.append(job);files[job['graph']]=raw;checks.append({'case':case,'scientific_graph_equal':True,'cache_equal':True,'geometry':cache['geometry']})
for name in ['manage_service.py','host_worker.py','budget_bootstrap.py','compatibility_bootstrap.py','allocator_memory_budget.py','int8_row_chunking.py','memory_peak.py','backend_dispatch_audit.py']:
 text=read('H3_HOST_SECONDARY',OLD+'/scripts/'+name).decode()
 if name=='manage_service.py':text=text.replace('PORT=8677','PORT=8678').replace("'H3TemporalCoverageBlend'","'H3TemporalGainFieldRole5'")
 if name=='host_worker.py':text=text.replace('port=8677','port=8678')
 compile(text,name,'exec');files['scripts/'+name]=text.encode()
files['queue/durable_comfy_queue.py']=read('H3_HOST_SECONDARY',OLD+'/queue/durable_comfy_queue.py')
for p in (E/'innovation/feature_gain_field_role5').glob('*.py'):files['custom_nodes/H3TemporalGainFieldRole5/'+p.name]=p.read_bytes()
for local,name in [(E/'supervision/layer_boundary_20261023/runtime_helpers.py','runtime_helpers.py'),(B/'role5_audit.py','role5_audit.py')]:files['scripts/'+name]=local.read_bytes()
policy={'allow_shared':True,'gpu_uuid':GPU,'minimum_free_mib':33792,'torch_allocator_cap_gib':26,'reserve_vram_gib':6,'external_context_headroom_gib':1,'maximum_attempts':1,'reason':'Unique role5 two pilot transfer; shared GPU1, own allocator26GiB, reserve6GiB+context1GiB, no scientific change'}
files['shared_gpu_authorization.json']=json.dumps(policy,indent=2).encode();files['gpu.json']=json.dumps({'gpu_uuid':GPU,'index':1}).encode()
ssh('H3_HOST_SECONDARY','from pathlib import Path;r=Path('+repr(R)+');r.mkdir(exist_ok=True);assert not (r/"jobs.json").exists();[(r/n).mkdir(exist_ok=True) for n in ["scripts","queue","logs","graphs","custom_nodes","queue_state","output","temp","user","input","innovation_handoff"]]')
stream=io.BytesIO()
with tarfile.open(fileobj=stream,mode='w') as t:
 for name,data in files.items():info=tarfile.TarInfo(name);info.size=len(data);t.addfile(info,io.BytesIO(data))
subprocess.run(['ssh','H3_HOST_SECONDARY','tar -xf - -C '+R],input=stream.getvalue(),check=True)
code='''from pathlib import Path
import json,hashlib,sys,importlib,inspect
r=Path(ROOT);previous=Path(PREV)
for name in ['H3Study','H3DirectionRuntime','H3TemporalCoverage','H3TemporalCoverageV2','H3PartialRoPE','H3TrustedConditionCache','ComfyUI-KJNodes']:
 p=r/'custom_nodes'/name
 if not p.exists():p.symlink_to((previous/'custom_nodes'/name).resolve())
p=r/'innovation_cache'
if not p.exists():p.symlink_to(previous/'innovation_cache')
for case in ['short_0252','short_0358']:
 mf=json.loads((previous/'innovation_cache'/case/'manifest.json').read_text());p=r/'input'/(case+'_video.mp4')
 if not p.exists():p.symlink_to(Path(mf['source_video']))
sys.path.insert(0,str(r/'custom_nodes'));m=importlib.import_module('H3TemporalGainFieldRole5');c=m.NODE_CLASS_MAPPINGS['H3TemporalGainFieldRole5'];importlib.import_module('H3TemporalGainFieldRole5.frozen').load_frozen()
checks=[]
for graph in GRAPHS:
 g=json.loads((r/graph).read_text());assert set(g['50']['inputs'])==set(c.INPUT_TYPES()['required']);a=g['5']['inputs'];p=Path(a['cache_manifest']);assert hashlib.sha256(p.read_bytes()).hexdigest()==a['manifest_sha256'];mf=json.loads(p.read_text())
 for item in [mf['conditioning']]+mf['tensors']:assert hashlib.sha256(Path(item['file']).read_bytes()).hexdigest()==item['sha256']
 assert hashlib.sha256(Path(mf['source_video']).read_bytes()).hexdigest()==mf['source_video_sha256'];checks.append({'graph':graph,'sha256':hashlib.sha256((r/graph).read_bytes()).hexdigest(),'cache':a['manifest_sha256']})
print(json.dumps({'status':'CPU_READY','graphs':checks,'schema':True,'frozen':True}))
'''.replace('ROOT',repr(R)).replace('PREV',repr(PREV)).replace('GRAPHS',repr([j['graph'] for j in jobs]))
p=subprocess.run(['ssh','H3_HOST_SECONDARY','CUDA_VISIBLE_DEVICES= /home/research-user/miniconda3/envs/comfyui/bin/python -'],input=code.encode(),capture_output=True);assert p.returncode==0,p.stderr.decode();(D/'CPU_READY.json').write_bytes(p.stdout)
(D/'jobs.json').write_text(json.dumps({'jobs':jobs,'planned_count':2},indent=2));(D/'SCIENCE_CHECK.json').write_text(json.dumps(checks,indent=2));(D/'ASSETS.json').write_text(json.dumps({n:digest(v) for n,v in files.items()},indent=2));print(p.stdout.decode())
