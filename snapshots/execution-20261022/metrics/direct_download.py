"""Stream one public HF file via physical en0 to remote storage; no local weight copy."""
import argparse,hashlib,json,subprocess,time,urllib.parse,urllib.request
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('repo');p.add_argument('filename');p.add_argument('size',type=int);p.add_argument('--dest');a=p.parse_args()
root=Path(__file__).resolve().parent
opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7897'}))
def ip(host):
 d=json.loads(opener.open('https://dns.alidns.com/resolve?name='+host+'&type=A',timeout=20).read());return next(r['data'] for r in d['Answer'] if r['type']==1)
url='https://hf-mirror.com/'+a.repo+'/resolve/main/'+a.filename
redirects=[]
for _ in range(8):
 host=urllib.parse.urlparse(url).hostname;address=ip(host)
 r=subprocess.run(['curl','--interface','en0','--noproxy','*','--resolve',host+':443:'+address,'-sSI','--connect-timeout','10','--max-time','45',url],capture_output=True,text=True,check=True)
 lines=r.stdout.splitlines();status=next(x for x in reversed(lines) if x.startswith('HTTP/'));loc=next((x.split(':',1)[1].strip() for x in lines if x.lower().startswith('location:')),None)
 redirects.append({'host':host,'ip':address,'status':status})
 if not loc:break
 url=urllib.parse.urljoin(url,loc)
else:raise RuntimeError('Too many redirects')
dest='/data/research-user/h3_metrics_20261022/weights/'+(a.dest or a.filename)
import shlex
ssh=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','H3_HOST_CONFIGURE_LOCALLY']
target=subprocess.Popen(ssh+['cat > '+shlex.quote(dest+'.partial')],stdin=subprocess.PIPE)
with open(root/(Path(a.filename).name+'.download.log'),'w') as log:
 proc=subprocess.Popen(['curl','--interface','en0','--noproxy','*','--resolve',host+':443:'+address,'-fS','--connect-timeout','10','--max-time','1800',url],stdout=target.stdin,stderr=log)
 target.stdin.close();rc=proc.wait();trc=target.wait()
if rc or trc:raise RuntimeError('Transfer failed '+str((rc,trc)))
code='import hashlib,json;from pathlib import Path;p=Path('+repr(dest+'.partial')+');assert p.stat().st_size=='+str(a.size)+';h=hashlib.sha256(p.read_bytes()).hexdigest();p.replace('+repr(dest)+');print(h)'
digest=subprocess.check_output(ssh+[shlex.join(['python3','-c',code])],text=True).strip()
(root/(Path(a.filename).name+'.download.json')).write_text(json.dumps({'repo':a.repo,'file':a.filename,'size':a.size,'sha256':digest,'route':'physical en0 bound curl real DNS; SSH remote stream','redirects':redirects,'finished':time.time()},indent=2))
print(a.filename,a.size,digest)
