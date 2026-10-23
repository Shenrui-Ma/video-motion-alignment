"""Copy only task-local runtime/source files, verifying completed live runtime identity."""
from pathlib import Path
import subprocess,shlex,json,hashlib
from check_science import D,E,F,B,R,sha,check
H='H3_HOST_RTX4090';L=E/'supervision/live_phase_pair_20261023'
check(json.loads((D/'graph.json').read_text()),json.loads((D/'jobs.json').read_text()))
science=json.loads((D/'SCIENCE_CHECK.json').read_text());liveassets=json.loads((L/'DEPLOY_ASSETS.json').read_text())
files={'custom_nodes/H3TemporalGainField/'+n:(F/n).read_bytes().hex() for n in science['frozen_six_sources']}
for target,source in [('graphs/temporal_gain_field_graph.json',D/'graph.json'),('jobs.json',D/'jobs.json'),('SCIENCE_CHECK.json',D/'SCIENCE_CHECK.json'),('SCIENCE_READY.json',F/'READY.json'),('scripts/field_audit.py',B/'field_audit.py')]:files[target]=source.read_bytes().hex()
code=r'''
from pathlib import Path
import sys,json,hashlib,time,socket,os
r=Path(ROOT);old=r.parent/'live_phase_pair_20261023';data=json.load(sys.stdin);sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not (r/'STARTED.json').exists() and not (r/'jobs').exists()
assert json.loads((old/'STATUS.json').read_text())['phase']=='complete'
for method in ['native','global_weak']:assert json.loads((old/'jobs'/method/'SERVICE_CLEANUP.json').read_text())['stopped']
s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',8687));s.close()
r.mkdir(exist_ok=True);copied={}
for name,h in data['liveassets'].items():
 if not (name.startswith('scripts/') or name.startswith('custom_nodes/')):continue
 if name in ['scripts/live_pair_supervisor.py','scripts/trajectory_gate.py']:continue
 p=old/name;assert sha(p)==h,('live runtime changed',name);b=p.read_bytes()
 if name=='scripts/manage_service.py':
  text=b.decode();assert 'PORT=8685' in text;text=text.replace('PORT=8685','PORT=8687').replace("'H3LivePhase',","'H3LivePhase','H3TemporalGainField',");compile(text,name,'exec');b=text.encode()
 q=r/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b);copied[name]={'live_sha256':h,'target_sha256':sha(q),'modified':name=='scripts/manage_service.py'}
for name,hexdata in data['files'].items():
 q=r/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(bytes.fromhex(hexdata))
for name in ['gpu.json','shared_gpu_authorization.json','MODEL_REHASH.json']:(r/name).write_bytes((old/name).read_bytes())
p=json.loads((r/'shared_gpu_authorization.json').read_text());p['scope']='one frozen original temporal_gain_field drink same-live-environment reproduction; no submit before independent review and root release';(r/'shared_gpu_authorization.json').write_text(json.dumps(p,indent=2)+'\n')
link=r/'custom_nodes/ComfyUI-KJNodes'
if not link.exists():link.symlink_to((old/'custom_nodes/ComfyUI-KJNodes').resolve())
m=json.loads((r/'MODEL_REHASH.json').read_text());st=Path(m['path']).stat();assert (st.st_ino,st.st_mtime_ns,st.st_size)==(m['inode'],m['mtime_ns'],m['bytes'])
g=json.loads((r/'graphs/temporal_gain_field_graph.json').read_text());inputs=[]
for node in g.values():
 for k,v in node['inputs'].items():
  if isinstance(v,str) and k.endswith('_path') and Path(v).is_file():inputs.append({'field':k,'path':v,'sha256':sha(v)})
out={'status':'prepared_only_no_model_started','time':time.time(),'root':str(r),'copied_live_runtime':copied,'source_assets':{k:sha(r/k) for k in data['files']},'model_current_stat_matches_full_sha':m,'input_files':inputs,'policy':p,'port':8687}
(r/'PREPARED_ONLY.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
'''.replace('ROOT',repr(R))
p=subprocess.run(['ssh',H,'python3 -c '+shlex.quote(code)],input=json.dumps({'files':files,'liveassets':liveassets}),text=True,capture_output=True,timeout=90);assert p.returncode==0,p.stderr
out=json.loads(p.stdout);(D/'STAGED_PREPARED.json').write_text(json.dumps(out,indent=2)+'\n')
code=r'''
from pathlib import Path
import sys,importlib,json,torch
r=Path(ROOT);sys.path[:0]=[str(r/'custom_nodes'),str(r/'scripts')];import int8_row_chunking,backend_dispatch_audit
maps={}
for name in ['H3Study','H3TrustedConditionCache','H3LivePhase','H3TemporalGainField']:maps.update(importlib.import_module(name).NODE_CLASS_MAPPINGS)
g=json.loads((r/'graphs/temporal_gain_field_graph.json').read_text());checked=[]
for k,n in g.items():
 if n['class_type'] in maps:
  required=maps[n['class_type']].INPUT_TYPES()['required'];assert set(n['inputs'])==set(required),(k,set(n['inputs'])^set(required));checked.append([k,n['class_type']])
importlib.import_module('H3TemporalGainField.frozen').load_frozen()
assert not torch.cuda.is_initialized()
print(json.dumps({'passed':True,'cuda_initialized':False,'torch':torch.__version__,'checked':checked}))
'''.replace('ROOT',repr(R))
p=subprocess.run(['ssh',H,'CUDA_VISIBLE_DEVICES= PYTHONPATH=/data/research-user/h3_inference_20261023/runtime_deps /data/research-user/h3_inference_20261023/env/bin/python -'],input=code,text=True,capture_output=True,timeout=90);assert p.returncode==0,p.stderr
out=json.loads(p.stdout);(D/'DEPLOY_CPU_READY.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
