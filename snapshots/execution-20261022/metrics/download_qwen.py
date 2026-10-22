"""Resume verified official AWQ shards, physical en0 to SSH; never allocates a GPU."""
import fcntl,json,shlex,subprocess,time,urllib.parse,urllib.request
from pathlib import Path
from metric_worker import atomic
ROOT=Path(__file__).resolve().parent
m=json.loads((ROOT/'qwen_download_manifest.json').read_text())
lock=open(ROOT/'qwen_download.lock','a')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit(0)
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=12','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3',m['host']]
def remote(code,timeout=180):
 r=subprocess.run(SSH+[shlex.join(['python3','-c',code])],capture_output=True,text=True,timeout=timeout)
 if r.returncode:raise RuntimeError('remote operation failed: '+r.stderr[-350:])
 return r.stdout.strip()
# Disk reservation check is a preflight budget, not a GPU reservation.
remote('import pathlib,shutil;p=pathlib.Path('+repr(m['remote_dir'])+');p.mkdir(parents=True,exist_ok=True);assert shutil.disk_usage(p).free>70*1024**3')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7897'}))
def resolve(host):
 d=json.loads(opener.open('https://dns.alidns.com/resolve?name='+host+'&type=A',timeout=30).read())
 return next(x['data'] for x in d['Answer'] if x['type']==1)
def final_url(url):
 trace=[]
 for _ in range(8):
  host=urllib.parse.urlparse(url).hostname;ip=resolve(host)
  r=subprocess.run(['curl','--interface','en0','--noproxy','*','--resolve',host+':443:'+ip,'-sSI','--connect-timeout','10','--max-time','45',url],capture_output=True,text=True)
  if r.returncode:raise RuntimeError('direct HEAD failed for '+host)
  loc=next((x.split(':',1)[1].strip() for x in r.stdout.splitlines() if x.lower().startswith('location:')),None)
  status=[x for x in r.stdout.splitlines() if x.startswith('HTTP/')][-1]
  trace.append({'host':host,'ip':ip,'status':status})
  if not loc:
   if '200' not in status:raise RuntimeError('direct HEAD status '+status+' for '+host)
   return url,host,ip,trace
  url=urllib.parse.urljoin(url,loc)
 raise RuntimeError('too many redirects')
def verify(path,item,promote=False):
 expected=item.get('lfs',{}).get('oid') or item['oid'];algo='sha256' if item.get('lfs') else 'gitblob'
 code='''import hashlib,pathlib
p=pathlib.Path(PATH)
if not p.exists() or p.stat().st_size!=SIZE:print('missing')
else:
 h=hashlib.sha256() if ALGO=='sha256' else hashlib.sha1()
 if ALGO=='gitblob':h.update(('blob '+str(SIZE)+'\\0').encode())
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 ok=h.hexdigest()==EXPECTED
 if ok and PROMOTE:p.replace(str(p)[:-8])
 print('verified' if ok else 'mismatch')
'''.replace('PATH',repr(path)).replace('SIZE',str(item['size'])).replace('ALGO',repr(algo)).replace('EXPECTED',repr(expected)).replace('PROMOTE',repr(promote))
 return remote(code,600)
state_path=ROOT/'qwen_download_status.json';state=json.loads(state_path.read_text()) if state_path.exists() else {'files':{},'started':time.time()}
state['revision']=m['revision'];deadline=time.time()+48*3600
for item in m['files']:
 name=item['path'];dst=m['remote_dir']+'/'+name
 if verify(dst,item)=='verified':state['files'][name]={'status':'verified','bytes':item['size']};atomic(state_path,state);continue
 for attempt in range(1,4):
  if time.time()>deadline:raise SystemExit('48h download window ended')
  try:
   state['active']=name;state['updated']=time.time();state['files'][name]={'status':'downloading','attempt':attempt,'bytes':item['size']};atomic(state_path,state)
   url,host,ip,trace=final_url('https://hf-mirror.com/'+m['repo']+'/resolve/'+m['revision']+'/'+name)
   offset=int(remote('from pathlib import Path;p=Path('+repr(dst+'.partial')+');n=p.stat().st_size if p.exists() else 0;print(n if n<'+str(item['size'])+' else 0);p.unlink() if n>='+str(item['size'])+' else None'))
   target=subprocess.Popen(SSH+['cat '+('>>' if offset else '>')+' '+shlex.quote(dst+'.partial')],stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
   with open(ROOT/'qwen_download_progress.log','a') as log:
    args=['curl','--interface','en0','--noproxy','*','--resolve',host+':443:'+ip,'-fS','--connect-timeout','10','--max-time','3600']
    if offset:args+=['--range',str(offset)+'-']
    proc=subprocess.Popen(args+[url],stdout=target.stdin,stderr=log);target.stdin.close();rc=proc.wait();trc=target.wait(timeout=120)
   if rc or trc:raise RuntimeError('stream transfer failed '+str((rc,trc)))
   if verify(dst+'.partial',item,True)!='verified':raise RuntimeError('checksum mismatch')
   state['files'][name]={'status':'verified','bytes':item['size'],'route':'physical en0 / real-IP TLS / SSH stream','redirects':trace,'finished':time.time()};atomic(state_path,state);break
  except Exception as exc:
   state['files'][name]={'status':'retry' if attempt<3 else 'failed','attempt':attempt,'error':str(exc),'time':time.time()};atomic(state_path,state);time.sleep(15)
state['finished']=time.time();state['complete']=all(x.get('status')=='verified' for x in state['files'].values()) and len(state['files'])==len(m['files']);atomic(state_path,state)
