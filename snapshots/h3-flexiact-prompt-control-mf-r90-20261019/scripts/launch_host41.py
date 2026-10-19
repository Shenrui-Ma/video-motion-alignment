from pathlib import Path
import json,hashlib,subprocess,shlex
R=Path(__file__).resolve().parents[1];P=R/'host41_package';cfg=json.loads((P/'configs/RUNTIME.json').read_text());D=cfg['remote_root'];H=hashlib.sha256((P/'CONSUMER_FREEZE.json').read_bytes()).hexdigest()
code='D='+repr(D)+'\nH='+repr(H)+'\nPY='+repr(cfg['python'])+'\n'+'''
from pathlib import Path
import hashlib,json,sys,os,subprocess,time,importlib.util
r=Path(D);assert hashlib.sha256((r/'CONSUMER_FREEZE.json').read_bytes()).hexdigest()==H
sys.path.insert(0,str(r/'scripts'));from common import verify_runtime
verify_runtime();s=importlib.util.spec_from_file_location('r90_slot',r/'audit/run_authorized.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);os.environ['CUDA_VISIBLE_DEVICES']=m.GPU;pre=m.capacity();assert not m.BATCH.exists()
with (r/'audit/SLOT_CAPACITY4.log').open('xb') as log:p=subprocess.Popen([PY,'-u',str(r/'audit/run_authorized.py')],cwd=r,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
d={'identity':dict(m.process_record(p.pid),pid=p.pid),'unix':time.time(),'preflight':pre,'freeze_sha256':H};(r/'audit/SLOT_CAPACITY4_LAUNCH.json').write_text(json.dumps(d,indent=2));print(json.dumps({'identity':d['identity'],'freeze_sha256':H,'remote':D}))
'''
p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','H3_SERVER_B',cfg['python']+' -c '+shlex.quote(code)],capture_output=True,text=True);(R/'audit/HOST41_LAUNCH_RESPONSE.json').write_text(json.dumps({'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr},indent=2));print(p.stdout);print(p.stderr);assert p.returncode==0
