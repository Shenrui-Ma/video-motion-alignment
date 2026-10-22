from pathlib import Path
import json,subprocess,shlex,hashlib,tarfile,io,copy,sys,concurrent.futures
D=Path(__file__).parent;E=D.parent.parent;P=E/'innovation/feature_gain_field_fixed_budget';S='/data4/research-user/h3_runs/benchmark_schedule_20261022'
HOSTS={'host41_fixed_budget':('H3_HOST_PRIMARY',S,'/data3/research-user/ComfyUI/.venv/bin/python',8672,['long_0059']),'host81_fixed_budget':('H3_HOST_RTX4090','/data/research-user/h3_inference_20261023/run_uniform_energy','/data/research-user/h3_inference_20261023/env/bin/python',8679,['short_0358','short_0252']),'host9_fixed_budget':('H3_HOST_SECONDARY','/home/research-user/h3_runs/adaptive_role5_20261023','/home/research-user/miniconda3/envs/comfyui/bin/python',8678,['long_0039'])}
def ssh(h,c,b=None):return subprocess.check_output(['ssh',h,shlex.join(['python3','-c',c])],input=b)
def read(h,p):return ssh(h,'from pathlib import Path;import sys;sys.stdout.buffer.write(Path('+repr(p)+').read_bytes())')
def sha(x):return hashlib.sha256(x).hexdigest()
assert sha((P/'READY.json').read_bytes())=='5b32848ead9252fee90b9dfbd484e9c339853016cba2e0c31f711d1c26d43e95'
ready=json.loads((P/'READY.json').read_text());sign=json.loads((E/'innovation/adaptive_strength_20261023/review_0637/fixed_budget/SIGNOFF.json').read_text());assert str(sign.get('status',sign.get('decision'))).lower() in ['approved','passed'],sign
alljobs=json.loads((P/'pilots/jobs.json').read_text())['jobs']
def deploy(owner):
 host,R,python,port,cases=HOSTS[owner];out=D/owner;out.mkdir(exist_ok=True);files={};jobs=[];checks=[]
 for n,h in ready['source_shas'].items():
  b=(P/n).read_bytes();assert sha(b)==h;files['custom_nodes/H3TemporalGainFieldFixedBudget/'+n]=b
 for case in cases:
  src=next(j for j in alljobs if j['metadata']['task_id']==case);original=json.loads((P/'pilots'/src['graph']).read_text());sourcecache=json.loads(read('H3_HOST_PRIMARY',original['5']['inputs']['cache_manifest']));targetraw=read(host,R+'/innovation_cache/'+case+'/manifest.json');targetcache=json.loads(targetraw)
  for k in ['seed','geometry','source_video_sha256','prompt_sha256']:assert sourcecache[k]==targetcache[k],(case,k)
  assert sourcecache['conditioning']['sha256']==targetcache['conditioning']['sha256'];assert [x['sha256'] for x in sourcecache['tensors']]==[x['sha256'] for x in targetcache['tensors']]
  graph=json.loads(json.dumps(original).replace(S,R));graph['5']['inputs'].update(cache_manifest=R+'/innovation_cache/'+case+'/manifest.json',manifest_sha256=sha(targetraw));reverse=json.loads(json.dumps(graph).replace(R,S));reverse['5']['inputs']=original['5']['inputs'];assert reverse==original
  raw=(json.dumps(graph,indent=2)+'\n').encode();job=json.loads(json.dumps(src).replace(S,R));job['metadata'].update(host=host,producer_host=owner,remote_root=R,graph_sha256=sha(raw),innovation_status='runtime_validation',source_job_id=src['id']);assert job['max_attempts']==1;jobs.append(job);files[job['graph']]=raw;checks.append({'case':case,'science_equal':True,'cache_equal':True,'geometry':sourcecache['geometry']})
 service=read(host,R+'/scripts/manage_service.py');text=service.decode();assert 'H3TemporalGainFieldFixedBudget' not in text;text=text.replace("'--input-directory'","'H3TemporalGainFieldFixedBudget','--input-directory'");compile(text,'service','exec');files['scripts/fixed_budget_service.staged.py']=text.encode()
 files['scripts/fixed_budget_guard.py']=(D/'guard.py').read_bytes();files['scripts/fixed_budget_helpers.py']=(E/'supervision/layer_boundary_20261023/runtime_helpers.py').read_bytes()
 ssh(host,'from pathlib import Path;r=Path('+repr(R)+');d=r/"innovation_handoff/fixed_budget_20261023";d.mkdir(exist_ok=True);assert not (d/"TARGET_RECEIPT.json").exists()')
 buf=io.BytesIO()
 with tarfile.open(fileobj=buf,mode='w') as t:
  for name,b in files.items():info=tarfile.TarInfo(name);info.size=len(b);info.mtime=1792711000;t.addfile(info,io.BytesIO(b))
 subprocess.run(['ssh',host,'tar -xf - -C '+R],input=buf.getvalue(),check=True)
 code='''from pathlib import Path
import sys,json,importlib,hashlib
r=Path(ROOT);sys.path.insert(0,str(r/'custom_nodes'));m=importlib.import_module('H3TemporalGainFieldFixedBudget');c=m.NODE_CLASS_MAPPINGS['H3TemporalGainFieldFixedBudget'];importlib.import_module('H3TemporalGainFieldFixedBudget.frozen').load_frozen()
for name in GRAPHS:
 g=json.loads((r/name).read_text());assert set(g['50']['inputs'])==set(c.INPUT_TYPES()['required']);v=g['5']['inputs'];p=Path(v['cache_manifest']);assert hashlib.sha256(p.read_bytes()).hexdigest()==v['manifest_sha256'];cache=json.loads(p.read_text())
 for x in [cache['conditioning']]+cache['tensors']:assert hashlib.sha256(Path(x['file']).read_bytes()).hexdigest()==x['sha256']
 assert hashlib.sha256(Path(cache['source_video']).read_bytes()).hexdigest()==cache['source_video_sha256'];target=r/'input'/(cache['source_video'].split('/')[-1]);source=Path(cache['source_video'])
 # canonical metadata source path uses task identifier, validated identical source bytes.
 case=Path(v['cache_manifest']).parent.name;p=r/'input'/(case+'_video.mp4')
 if not p.exists():p.symlink_to(source)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==cache['source_video_sha256']
print(json.dumps({'status':'CPU_READY','schema':True,'source_cache_sha':True,'graphs':GRAPHS}))
'''.replace('ROOT',repr(R)).replace('GRAPHS',repr([j['graph'] for j in jobs]))
 envprefix='CUDA_VISIBLE_DEVICES= '
 if host=='H3_HOST_RTX4090':envprefix+='PYTHONPATH=/data/research-user/h3_inference_20261023/runtime_deps '
 p=subprocess.run(['ssh',host,envprefix+shlex.quote(python)+' -'],input=code.encode(),capture_output=True);assert p.returncode==0,p.stderr.decode();(out/'CPU_READY.json').write_bytes(p.stdout)
 assets={k:sha(v) for k,v in files.items()};(out/'ASSETS.json').write_text(json.dumps(assets,indent=2));(out/'jobs.json').write_text(json.dumps({'jobs':jobs},indent=2));(out/'SCIENCE_CHECK.json').write_text(json.dumps(checks,indent=2));(out/'SERVICE_CHANGE.json').write_text(json.dumps({'before_sha256':sha(service),'after_sha256':sha(text.encode())},indent=2));print(owner,'CPU_READY',flush=True)
for owner in sys.argv[1:] or HOSTS:deploy(owner)
