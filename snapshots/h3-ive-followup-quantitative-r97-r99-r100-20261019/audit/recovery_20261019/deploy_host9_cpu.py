"""Passive transfer and CPU validation of the R106 MF fallback."""
from pathlib import Path
import json,hashlib,tarfile,subprocess,shlex,os
H=Path(__file__).resolve().parent;r=H/'r106_short_0252_solvers_host9';cfg=json.loads((r/'configs/RUNTIME.json').read_text());seal=json.loads((r/'SEAL.json').read_text());runtime=json.loads((r/'configs/RUNTIME_INHERITANCE.json').read_text())['files'];files=dict(seal['files']);files.update({'runtime/'+n:h for n,h in runtime.items()});sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for n,h in files.items():assert sha(r/n)==h,n
archive=H/'r106_host9_cpu.sealed.tar.gz'
with tarfile.open(archive,'w:gz') as t:
 for n in list(files)+['SEAL.json']:t.add(r/n,arcname=n)
remote=cfg['remote_root'];subprocess.run(['scp','-q','-o','BatchMode=yes','-o','ConnectTimeout=10',str(archive),'H3_SERVER_A:'+remote+'.tar.gz'],check=True)
code='R='+repr(remote)+'\nSEAL='+repr(sha(r/'SEAL.json'))+'\n'+'''
from pathlib import Path
import hashlib,json,tarfile,subprocess,sys,os,importlib.metadata
r=Path(R);assert not r.exists();r.mkdir()
with tarfile.open(R+'.tar.gz') as t:t.extractall(r,filter='data')
assert hashlib.sha256((r/'SEAL.json').read_bytes()).hexdigest()==SEAL
p=subprocess.run([sys.executable,str(r/'audit/check_package.py'),str(r)],capture_output=True,text=True,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'));assert p.returncode==0,p.stderr
v=json.loads(p.stdout);v['versions']={k:importlib.metadata.version(k) for k in ['torch','numpy','scipy','opencv-python']};v['remote']=R;v['seal_sha256']=SEAL;v['GPU_started']=False
(r/'audit/HOST9_CPU_READY.json').write_text(json.dumps(v,indent=2)+chr(10));print(json.dumps(v))
'''
p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','H3_SERVER_A',cfg['python']+' -c '+shlex.quote(code)],capture_output=True,text=True);(r/'audit/PASSIVE_DEPLOY_RESPONSE.json').write_text(json.dumps({'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr},indent=2));assert p.returncode==0,p.stderr;v=json.loads(p.stdout);(r/'audit/HOST9_CPU_READY.json').write_text(json.dumps(v,indent=2)+'\n');print(json.dumps(v))
