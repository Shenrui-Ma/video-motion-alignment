from pathlib import Path
import json,hashlib,subprocess,shlex,tarfile
R=Path(__file__).resolve().parents[1];P=R/'host41_package';cfg=json.loads((P/'configs/RUNTIME.json').read_text());D=cfg['remote_root'];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();f=json.loads((P/'CONSUMER_FREEZE.json').read_text());assert all(sha(P/n)==h for n,h in f['files'].items());A=R/'host41_package.tar.gz'
with tarfile.open(A,'w:gz') as t:
 for n in [*f['files'],'CONSUMER_FREEZE.json']:t.add(P/n,arcname=n)
subprocess.run(['scp','-q','-o','BatchMode=yes','-o','ConnectTimeout=10',str(A),'H3_SERVER_B:'+D+'.tar.gz'],check=True)
code='D='+repr(D)+'\nH='+repr(sha(P/'CONSUMER_FREEZE.json'))+'\nPY='+repr(cfg['python'])+'\n'+'''
from pathlib import Path
import tarfile,hashlib,subprocess,os,json,time
r=Path(D);assert not r.exists();r.mkdir()
with tarfile.open(D+'.tar.gz') as t:t.extractall(r,filter='data')
assert hashlib.sha256((r/'CONSUMER_FREEZE.json').read_bytes()).hexdigest()==H
p=subprocess.run([PY,str(r/'audit/check_package.py'),str(r)],check=True,capture_output=True,text=True,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'))
d=json.loads(p.stdout);d.update(freeze_sha256=H,unix=time.time());(r/'audit/PASSIVE_DEPLOYMENT.json').write_text(json.dumps(d,indent=2));print(json.dumps(d))
'''
p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','H3_SERVER_B','python3 -c '+shlex.quote(code)],capture_output=True,text=True);(R/'audit/HOST41_DEPLOY_RESPONSE.json').write_text(json.dumps({'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr},indent=2));print(p.stdout);print(p.stderr);assert p.returncode==0
