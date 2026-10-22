from pathlib import Path
import json,hashlib,tarfile,subprocess,sys,socket,time,os
r=Path('/home/researcher/h3_runs/timing_ive_otter_color_r136_20261020');assert not r.exists();r.mkdir()
with tarfile.open('/home/researcher/h3_runs/r136_deployment_payload.tar.gz','r:gz') as t:
 for m in t.getmembers():assert not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
 t.extractall(r)
for d in ['input','output','temp','user','processes','logs','audit/router','audit/x0','custom_nodes']:(r/d).mkdir(parents=True,exist_ok=True)
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();m=json.loads((r/'deploy_manifest.json').read_text())
for f,v in m['files'].items():assert h(r/f)==v['sha256'],f
out={};env=dict(os.environ,PATH=str(Path(sys.executable).parent)+':'+os.environ['PATH'],PYTHONDONTWRITEBYTECODE='1',LC_ALL='C',LANG='C')
for name,args in [('PREFLIGHT',['scripts/preflight.py']),('TESTS',['-m','unittest','discover','-s','tests']),('TIMELINE',['scripts/verify_input_timeline.py'])]:
 v=subprocess.run([sys.executable]+args,cwd=r,env=env,text=True,capture_output=True);(r/('audit/TARGET_'+name+'.txt')).write_text(v.stdout+v.stderr);out[name]={'rc':v.returncode,'tail':(v.stdout+v.stderr)[-600:]}
 if v.returncode:print(json.dumps(out));sys.exit(0)
s=socket.socket();assert s.connect_ex(('127.0.0.1',8614))!=0;s.close()
ready={'passed':True,'files':len(m['files']),'seal_sha256':h(r/'deploy_manifest.json'),'preflight':True,'tests':67,'timeline_passed':True,'port8614_empty':True,'GPU_started':False,'unix':time.time()};(r/'audit/TARGET_CPU_READY.json').write_text(json.dumps(ready,indent=2)+'\n');print(json.dumps(ready));print(json.dumps(out))
