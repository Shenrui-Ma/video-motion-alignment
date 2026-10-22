"""Only read exact files from the bound producer; no queue or CUDA API."""
import shlex,subprocess
from common import *
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','H3_SERVER_A']
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
 try:subprocess.run(['rsync','-az','-e','ssh -o BatchMode=yes -o ConnectTimeout=15','H3_SERVER_A:'+str(p),str(destination)],check=True,timeout=timeout)
 except subprocess.TimeoutExpired as e:raise TimeoutError('bounded transfer timed out') from e
 except subprocess.CalledProcessError as e:
  if e.returncode in (12,30,35,255):raise ConnectionError('transfer unavailable: '+str(e.returncode)) from e
  raise

def fetch_json_batch(entries):
 """One bounded SSH read for exact small JSON bytes; never copy endpoint tensors."""
 import base64,hashlib
 paths=[str(safe_remote(item['remote'],'audit')) for item in entries];root=config()['producer_remote']
 code='import json,hashlib,base64;from pathlib import Path;root=Path('+repr(root)+');paths='+repr(paths)+';out={}\nfor name in paths:\n p=Path(name)\n if not p.resolve().is_relative_to(root):raise ValueError("path escapes producer")\n b=p.read_bytes()\n if len(b)>8388608:raise ValueError("JSON above bounded size")\n json.loads(b)\n out[name]={"sha256":hashlib.sha256(b).hexdigest(),"bytes_b64":base64.b64encode(b).decode()}\nprint(json.dumps(out))'
 try:result=subprocess.run(SSH+[shlex.join(['python3','-c',code])],capture_output=True,text=True,check=True,timeout=90)
 except subprocess.TimeoutExpired as e:raise TimeoutError('bounded JSON batch timed out') from e
 except subprocess.CalledProcessError as e:
  if e.returncode==255:raise ConnectionError('SSH batch unavailable') from e
  raise
 records=json.loads(result.stdout)
 for item in entries:
  row=records[str(item['remote'])];b=base64.b64decode(row['bytes_b64'],validate=True);digest=hashlib.sha256(b).hexdigest()
  require(digest==row['sha256']==item['sha256'],'exact transaction JSON differs');json.loads(b);p=Path(item['local']);require(not p.exists(),'transaction destination exists');p.write_bytes(b)
