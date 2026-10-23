import json,subprocess,shlex,hashlib,time
from pathlib import Path
P=Path(__file__).resolve().parent
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3']
TARGET='H3_HOST_CONFIGURE_LOCALLY'
def remote(host,code,timeout=120):
 return subprocess.run(SSH+[host,shlex.join(['python3','-c',code])],capture_output=True,text=True,check=True,timeout=timeout).stdout.strip()
def digest(host,path):
 return remote(host,"import hashlib;from pathlib import Path;p=Path("+repr(path)+");print(hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else '')")
def transfer(host,src,dst,expected):
 old=digest(TARGET,dst)
 if old==expected:return 'existing_verified'
 if old:raise RuntimeError('destination already differs: '+dst)
 source_hash=digest(host,src) if host else hashlib.sha256(Path(src).read_bytes()).hexdigest()
 if source_hash!=expected:raise RuntimeError('source SHA mismatch '+src)
 if host==TARGET:
  code="import shutil,hashlib;from pathlib import Path;s=Path("+repr(src)+");d=Path("+repr(dst)+");d.parent.mkdir(parents=True,exist_ok=True);t=d.with_name(d.name+'.stage');shutil.copyfile(s,t);assert hashlib.sha256(t.read_bytes()).hexdigest()=="+repr(expected)+";t.replace(d)"
  remote(TARGET,code);return 'same_host_copy_verified'
 cmd='mkdir -p '+shlex.quote(str(Path(dst).parent))+' && cat > '+shlex.quote(dst+'.stage')
 target=subprocess.Popen(SSH+[TARGET,cmd],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 if host:
  source=subprocess.Popen(SSH+[host,shlex.join(['cat',src])],stdout=target.stdin,stderr=subprocess.PIPE);target.stdin.close();_,err=source.communicate(timeout=600)
  if source.returncode:target.terminate();raise RuntimeError(err.decode())
 else:
  with Path(src).open('rb') as f:
   for b in iter(lambda:f.read(1048576),b''):target.stdin.write(b)
  target.stdin.close()
 if target.wait(timeout=600):raise RuntimeError(target.stderr.read().decode())
 remote(TARGET,"import hashlib;from pathlib import Path;t=Path("+repr(dst+'.stage')+");assert hashlib.sha256(t.read_bytes()).hexdigest()=="+repr(expected)+";t.replace("+repr(dst)+")")
 return 'ssh_stream_verified'
a=json.loads((P/'assets.json').read_text());rows=[]
try:
 for r in a['assets']:
  status=transfer(r['remote_source_host'],r['remote_source'],r['destination'],r['sha256']);rows.append(dict(task_id=r['task_id'],role=r['role'],destination=r['destination'],sha256=r['sha256'],status=status));print(r['task_id'],r['role'],status,flush=True)
 for f in sorted((P/'cache_manifests').glob('*.json')):
  dst=a['remote_target_root']+'/innovation_cache/'+f.stem+'/manifest.json';h=hashlib.sha256(f.read_bytes()).hexdigest();rows.append(dict(role='manifest',destination=dst,sha256=h,status=transfer(None,str(f),dst,h)))
 f=P/'custom_nodes/H3TrustedConditionCache/__init__.py';dst=a['remote_target_root']+'/custom_nodes/H3TrustedConditionCache/__init__.py';h=hashlib.sha256(f.read_bytes()).hexdigest();rows.append(dict(role='cache_node',destination=dst,sha256=h,status=transfer(None,str(f),dst,h)))
finally:
 (P/'deployment_receipt.json').write_text(json.dumps(dict(time=time.time(),rows=rows,complete=len(rows)==48),indent=2)+'\n')
