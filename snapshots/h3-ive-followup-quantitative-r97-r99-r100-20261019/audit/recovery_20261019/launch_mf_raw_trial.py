"""Launch one sealed, approved short MF job after a fresh no-CUDA admission."""
import hashlib,json,shlex,subprocess,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve();cfg=json.loads((root/'configs/RUNTIME.json').read_text());remote=cfg['remote_root'];seal=hashlib.sha256((root/'SEAL.json').read_bytes()).hexdigest()
code='R='+repr(remote)+'\nEXPECTED='+repr(seal)+'\nPYTHON='+repr(cfg['python'])+'\n'+'''
from pathlib import Path
import hashlib,json,os,subprocess,sys,time,importlib.util
r=Path(R);assert hashlib.sha256((r/'SEAL.json').read_bytes()).hexdigest()==EXPECTED
sys.path.insert(0,str(r/'scripts'));from common import verify_seal,identity
verify_seal();s=importlib.util.spec_from_file_location('authorized_slot',r/'audit/run_authorized.py');w=importlib.util.module_from_spec(s);s.loader.exec_module(w)
os.environ['CUDA_VISIBLE_DEVICES']=w.GPU
preflight=w.capacity();assert not w.BATCH.exists()
log=(r/'audit/SLOT_CAPACITY4.log').open('xb')
child=subprocess.Popen([PYTHON,'-u',str(r/'audit/run_authorized.py')],cwd=r,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True);log.close()
d={'identity':identity(child.pid),'unix':time.time(),'seal_sha256':EXPECTED,'preflight':preflight,'attempt':str(w.BATCH),'remote':R}
(r/'audit/SLOT_CAPACITY4_LAUNCH.json').write_text(json.dumps(d,indent=2)+chr(10))
print(json.dumps({'identity':d['identity'],'attempt':str(w.BATCH),'remote':R,'seal_sha256':EXPECTED}))
'''
p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','H3_SERVER_B',cfg['python']+' -c '+shlex.quote(code)],capture_output=True,text=True)
(root/'audit/CAPACITY4_LAUNCH_RESPONSE.json').write_text(json.dumps({'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr},indent=2)+'\n')
print(p.stdout);print(p.stderr);assert p.returncode==0
