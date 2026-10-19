"""Only read exact files from the bound producer; no queue or CUDA API."""
import shlex,subprocess
from common import *
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','H3_SERVER_B']
def read_paths(paths,missing_ok=False):
 c=config();root=c['producer_remote']
 for p in paths:
  require(Path(p).is_relative_to(root) and '..' not in Path(p).parts,'remote path outside producer')
 code='import json,hashlib;from pathlib import Path;root=Path('+repr(root)+');out={};paths='+repr(paths)+'\nfor name in paths:\n p=Path(name)\n if not p.exists():\n  '+('out[name]=None;continue' if missing_ok else 'raise FileNotFoundError(name)')+'\n if not p.resolve().is_relative_to(root):raise ValueError("path escapes producer")\n b=p.read_bytes();out[name]={"sha256":hashlib.sha256(b).hexdigest(),"value":json.loads(b)}\nprint(json.dumps(out))'
 try:result=subprocess.run(SSH+[shlex.join(['python3','-c',code])],capture_output=True,text=True,check=True,timeout=60)
 except subprocess.TimeoutExpired as e:raise TimeoutError('bounded SSH read timed out') from e
 except subprocess.CalledProcessError as e:
  if e.returncode==255:raise ConnectionError('SSH transport unavailable: '+str(e.stderr)[-500:]) from e
  raise
 return json.loads(result.stdout)
def fetch(path,destination,timeout=240):
 p=Path(path);require(p.is_relative_to(config()['producer_remote']) and '..' not in p.parts,'remote output escapes root')
 try:subprocess.run(['rsync','-az','-e','ssh -o BatchMode=yes -o ConnectTimeout=15','H3_SERVER_B:'+str(p),str(destination)],check=True,timeout=timeout)
 except subprocess.TimeoutExpired as e:raise TimeoutError('bounded transfer timed out') from e
 except subprocess.CalledProcessError as e:
  if e.returncode in (12,30,35,255):raise ConnectionError('transfer unavailable: '+str(e.returncode)) from e
  raise

def verify_source_bytes(path,digest):
 p=safe_path(path);root=config()['producer_remote']
 code='import hashlib;from pathlib import Path;p=Path('+repr(str(p))+');root=Path('+repr(root)+');assert p.resolve().is_relative_to(root);h=hashlib.sha256();f=p.open("rb")\nfor b in iter(lambda:f.read(1048576),b""):h.update(b)\nprint(h.hexdigest())'
 result=subprocess.run(SSH+[shlex.join(['python3','-c',code])],capture_output=True,text=True,check=True,timeout=90)
 require(result.stdout.strip()==digest,'remote prepared source SHA differs')
