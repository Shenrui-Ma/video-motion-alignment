from pathlib import Path
import json,hashlib,subprocess,shlex,tarfile,io,concurrent.futures
D=Path(__file__).parent;E=D.parent.parent;S='/home/research-user/h3_runs/benchmark_schedule_20261022_host9a';C=json.loads((D.parent/'runtime_0807_20261023/EXTENSION_CANDIDATES.json').read_text())
HOSTS={'host41_extension':('H3_HOST_PRIMARY','/data4/research-user/h3_runs/benchmark_schedule_20261022','short_0135'),'host81_extension':('H3_HOST_RTX4090','/data/research-user/h3_inference_20261023/run_uniform_energy','long_0161'),'host9_extension':('H3_HOST_SECONDARY','/home/research-user/h3_runs/adaptive_role5_20261023','short_0166')}
def ssh(h,c,b=None):return subprocess.check_output(['ssh',h,shlex.join(['python3','-c',c])],input=b)
def read(h,p):return ssh(h,'from pathlib import Path;import sys;sys.stdout.buffer.write(Path('+repr(p)+').read_bytes())')
def sha(b):return hashlib.sha256(b).hexdigest()
source_shas=json.loads(ssh('H3_HOST_SECONDARY',"from pathlib import Path;import json,hashlib;r=Path("+repr(S)+");print(json.dumps({str(p.relative_to(r/'custom_nodes/H3Study')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (r/'custom_nodes/H3Study').rglob('*.py')}))"))
def prep(owner):
 h,r,case=HOSTS[owner];o=D/owner;o.mkdir(exist_ok=True);xs=[x for x in C if x['job']['metadata']['task_id']==case];assert len(xs)==2;files={};jobs=[]
 for x in xs:
  original=x['graph'];g=json.loads(json.dumps(original).replace(S,r));assert json.loads(json.dumps(g).replace(r,S))==original;raw=(json.dumps(g,indent=2)+'\n').encode();j=json.loads(json.dumps(x['job']).replace(S,r));j['max_attempts']=1;j['metadata'].update(producer_host=owner,host=h,remote_root=r,source_job_id=j['id'],graph_sha256=sha(raw),extension_release='three_pairs_20261023');jobs.append(j);files[j['graph']]=raw
 for name in ['extension_guard.py','test_guard.py']:files['scripts/'+name]=(D/name).read_bytes()
 files['scripts/extension_helpers.py']=(E/'supervision/layer_boundary_20261023/runtime_helpers.py').read_bytes()
 buf=io.BytesIO()
 with tarfile.open(fileobj=buf,mode='w') as tar:
  for n,b in files.items():ti=tarfile.TarInfo(n);ti.size=len(b);tar.addfile(ti,io.BytesIO(b))
 subprocess.run(['ssh',h,'tar -xf - -C '+r],input=buf.getvalue(),check=True)
 # Input transfer is internal streaming, never persisted on the Mac.
 src=xs[0]['job']['metadata']['source_video'];dst=r+'/input/'+Path(src).name
 exists=json.loads(ssh(h,'from pathlib import Path;import json,hashlib;p=Path('+repr(dst)+');print(json.dumps({"exists":p.exists(),"sha":hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None}))'))
 if exists['exists']:assert exists['sha']==xs[0]['source_sha']
 else:
  with subprocess.Popen(['ssh','H3_HOST_SECONDARY','cat '+shlex.quote(src)],stdout=subprocess.PIPE) as a:
   b=subprocess.run(['ssh',h,'cat > '+shlex.quote(dst+'.partial')],stdin=a.stdout);a.stdout.close();assert a.wait()==b.returncode==0
  ssh(h,'from pathlib import Path;import hashlib;p=Path('+repr(dst+'.partial')+');assert hashlib.sha256(p.read_bytes()).hexdigest()=='+repr(xs[0]['source_sha'])+';p.replace('+repr(dst)+')')
 code='''from pathlib import Path
import json,hashlib,sys
r=Path(ROOT);x=json.load(sys.stdin);sys.path.insert(0,str(r/'scripts'));import extension_helpers as g
s=g.snapshot(r);assert s['worker']['state']=='exited' and s['service']['state']=='exited';assert not any(s['locks'].values()) and not s['port_listening'];assert g.read(r/'innovation_handoff/fixed_budget_20261023/RESULT.json')['status']=='passed'
for n,h in x['source_shas'].items():assert hashlib.sha256((r/'custom_nodes/H3Study'/n).read_bytes()).hexdigest()==h,n
for n,h in x['assets'].items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h
for j in x['manifest']['jobs']:
 assert j['id'] not in s['states'] and j['id'] not in {a['id'] for a in s['manifest']['jobs']};graph=g.read(r/j['graph']);assert graph['5']['inputs']['prompt']==j['metadata']['recommended_prompt'];assert graph['6']['inputs']['noise_seed']==2026101701
 for node in ['1','2','3','4']:
  fn=next(v for k,v in graph[node]['inputs'].items() if k.endswith('_name'));assert list((r/'models').rglob(fn)) or list(Path(MODELS).rglob(fn)),fn
p=r/'input'/x['input_name'];assert hashlib.sha256(p.read_bytes()).hexdigest()==x['input_sha'];d=r/'innovation_handoff/extension_three_20261023';d.mkdir(exist_ok=True);assert not (d/'TARGET_RECEIPT.json').exists();g.atomic(d/'planned_jobs.json',x['manifest']);g.atomic(d/'base_manifest.json',s['manifest']);print(json.dumps({'status':'prepared','source_shas_equal':True,'inputs_verified':True,'scientific_graphs_only_path_mapping':True,'base_count':len(s['manifest']['jobs']),'snapshot':{k:s[k] for k in ['worker','service','locks','worker_status']}}))
'''.replace('ROOT',repr(r)).replace('MODELS',repr('/data/research-user/h3_inference_20261023/models' if h=='H3_HOST_RTX4090' else '/data3/research-user/ComfyUI-H3/models' if h=='H3_HOST_PRIMARY' else '/data5/research-user/ComfyUI/models'))
 assets={n:sha(b) for n,b in files.items()};x={'source_shas':source_shas,'assets':assets,'manifest':{'jobs':jobs},'input_name':Path(src).name,'input_sha':xs[0]['source_sha']};v=ssh(h,code,json.dumps(x).encode());(o/'PREPARED.json').write_bytes(v);(o/'jobs.json').write_text(json.dumps({'jobs':jobs},indent=2));(o/'ASSETS.json').write_text(json.dumps(assets,indent=2));print(owner,v.decode(),flush=True)
if __name__=='__main__':
 import sys
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:list(ex.map(prep,sys.argv[1:] or HOSTS))
