"""Explicit direct-SSH CPU deployment; no service, decoder, observer or GPU dispatch."""
import argparse,hashlib,io,json,shlex,subprocess,tarfile,time
from pathlib import Path
from r86_contract import ROOT,read,sha,require

def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true',required=True);p.parse_args()
 runtime=read(ROOT/'configs/runtime.json');manifest=read(ROOT/'deploy_manifest.json');pre=read(ROOT/'audit/HOST9_BOUNDED_READ.json')['stdout']
 reuse={k:v for k,v in pre['inputs'].items() if v.get('exists') and v.get('sha256')==v.get('expected')}
 buffer=io.BytesIO()
 with tarfile.open(fileobj=buffer,mode='w:gz') as tar:
  for rel,row in manifest['files'].items():
   require(sha(ROOT/rel)==row['sha256'],'local sealed file changed: '+rel)
   if rel.startswith('inputs/') and rel[7:] in reuse:continue
   tar.add(ROOT/rel,arcname=rel,recursive=False)
  tar.add(ROOT/'deploy_manifest.json',arcname='deploy_manifest.json',recursive=False)
 payload=buffer.getvalue();config={'runtime':runtime,'reuse':reuse,'seal_sha256':sha(ROOT/'deploy_manifest.json')}
 remote=r"""import hashlib,io,json,os,subprocess,sys,tarfile,time
from pathlib import Path
c=CONFIG;r=c['runtime'];root=Path(r['remote_root']);root.mkdir(parents=True,exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
received=sys.stdin.buffer.read()
with tarfile.open(fileobj=io.BytesIO(received),mode='r:gz') as tar:
 for m in tar:
  p=root/m.name
  if not m.isfile() or not p.resolve().is_relative_to(root.resolve()) or p.is_symlink():raise ValueError('unsafe archive member')
  data=tar.extractfile(m).read();p.parent.mkdir(parents=True,exist_ok=True)
  if p.exists():
   if p.read_bytes()!=data:raise ValueError('existing target differs: '+m.name)
  else:p.write_bytes(data)
for name,row in c['reuse'].items():
 source=Path(row['path']);dest=root/'inputs'/name
 if sha(source)!=row['expected']:raise ValueError('cached input differs')
 dest.parent.mkdir(exist_ok=True)
 if not dest.exists():os.link(source,dest)
 if sha(dest)!=row['expected']:raise ValueError('linked input differs')
if sha(root/'deploy_manifest.json')!=c['seal_sha256']:raise ValueError('seal differs')
m=json.loads((root/'deploy_manifest.json').read_text())
for name,row in m['files'].items():
 if sha(root/name)!=row['sha256']:raise ValueError('sealed bytes differ: '+name)
for name in ['audit','processes','logs','analysis/postrun','input','output','temp','user','custom_nodes']:(root/name).mkdir(parents=True,exist_ok=True)
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',TOKENIZERS_PARALLELISM='false')
commands=[['scripts/materialize_parent.py'],['scripts/cpu_runtime_smoke.py'],['scripts/preflight.py'],['-m','unittest','discover','-s','tests','-v']];results=[]
for i,args in enumerate(commands):
 result=subprocess.run([r['python']]+args,cwd=root,env=env,capture_output=True,text=True)
 (root/'audit'/('TARGET_CPU_%02d.txt'%i)).write_text(result.stdout+result.stderr)
 results.append({'argv':args,'returncode':result.returncode})
 if result.returncode:raise RuntimeError('CPU command failed: '+str(args)+'\n'+(result.stdout+result.stderr)[-3000:])
out={'passed':True,'CPU_only':True,'GPU_dispatch':False,'received_bytes':len(received),'reused_input_bytes':sum((root/'inputs'/n).stat().st_size for n in c['reuse']),'producer_seal_sha256':c['seal_sha256'],'sealed_files_verified':len(m['files']),'commands':results,'created_unix':time.time()}
(root/'audit/TARGET_CPU_VALIDATION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
""".replace('CONFIG',repr(config))
 result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',runtime['host'],'python3 -c '+shlex.quote(remote)],input=payload,capture_output=True,timeout=180)
 record={'returncode':result.returncode,'payload_bytes':len(payload),'stdout':result.stdout.decode(),'stderr':result.stderr.decode(),'created_unix':time.time()};(ROOT/'audit/CPU_DEPLOYMENT.json').write_text(json.dumps(record,indent=2)+'\n')
 if result.returncode:raise RuntimeError(record['stderr'][-4000:])
 receipt=json.loads(record['stdout']);(ROOT/'audit/TARGET_CPU_VALIDATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
