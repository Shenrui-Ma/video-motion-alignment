from pathlib import Path
import subprocess,shlex,json,hashlib,copy,time
D=Path(__file__).parent;SRC='/home/research-user/h3_runs/benchmark_schedule_20261022_host9a';DST='/data/research-user/h3_inference_20261023/run_uniform_energy';case='short_0252'
def remote(host,code,data=None):return subprocess.check_output(['ssh',host,shlex.join(['python3','-c',code])],input=data)
raw=remote('H3_HOST_SECONDARY','from pathlib import Path;import sys;sys.stdout.buffer.write(Path('+repr(SRC+'/innovation_cache/'+case+'/manifest.json')+').read_bytes())');m=json.loads(raw);target=copy.deepcopy(m);entries=[]
for item in [target['conditioning']]+target['tensors']:
 source=item['file'];dest=DST+'/innovation_cache/'+case+'/'+Path(source).name;entries.append({'source':source,'dest':dest,'sha256':item['sha256'],'name':Path(source).name});item['file']=dest
target['source_video']=DST+'/input/short_0252_video.mp4';entries.append({'source':m['source_video'],'dest':target['source_video'],'sha256':m['source_video_sha256'],'name':'short_0252_video.mp4'})
code='''from pathlib import Path
import json,hashlib,sys
r=Path(ROOT);x=json.load(sys.stdin);p=r/'innovation_cache'
if p.is_symlink():assert p.resolve()==Path('/data/research-user/h3_inference_20261023/run/innovation_cache').resolve();p.unlink();p.mkdir();(p/'short_0358').symlink_to('/data/research-user/h3_inference_20261023/run/innovation_cache/short_0358')
missing=[]
for item in x:
 p=Path(item['dest']);p.parent.mkdir(exist_ok=True,parents=True)
 if p.exists():assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
 else:missing.append(item)
(r/'innovation_handoff/aircraft_cache_transfer.json').write_text(json.dumps(missing));print(json.dumps(missing))
'''.replace('ROOT',repr(DST));missing=json.loads(remote('H3_HOST_RTX4090',code,json.dumps(entries).encode()))
sender='''import tarfile,hashlib
from pathlib import Path
items=ITEMS
with tarfile.open(fileobj=__import__('sys').stdout.buffer,mode='w|') as t:
 for item in items:
  p=Path(item['source']);assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'];t.add(p,arcname=item['name'],recursive=False)
'''.replace('ITEMS',repr(missing))
receiver='''from pathlib import Path
import json,tarfile,hashlib,sys,os,time
items=json.loads(Path(REQUEST).read_text());expected={x['name']:x for x in items};done=[];total=0
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as t:
 for member in t:
  assert member.isfile() and member.name in expected;item=expected.pop(member.name);p=Path(item['dest']);tmp=p.with_suffix(p.suffix+'.transfer');h=hashlib.sha256()
  with t.extractfile(member) as source,tmp.open('wb') as out:
   for chunk in iter(lambda:source.read(1024**2),b''):out.write(chunk);h.update(chunk);total+=len(chunk)
  assert h.hexdigest()==item['sha256'];tmp.replace(p);done.append(item['name'])
assert not expected;print(json.dumps({'status':'verified','files':done,'bytes':total,'time':time.time()}))
'''.replace('REQUEST',repr(DST+'/innovation_handoff/aircraft_cache_transfer.json'))
if missing:
 s=subprocess.Popen(['ssh','H3_HOST_SECONDARY',shlex.join(['python3','-c',sender])],stdout=subprocess.PIPE);t=subprocess.Popen(['ssh','H3_HOST_RTX4090',shlex.join(['python3','-c',receiver])],stdin=s.stdout,stdout=subprocess.PIPE);s.stdout.close();out=t.communicate()[0];assert t.returncode==0 and s.wait()==0;receipt=json.loads(out)
else:receipt={'status':'already_verified','files':[],'bytes':0}
code='''from pathlib import Path
import json,hashlib,sys
x=json.load(sys.stdin);m=x['manifest']
for i in [m['conditioning']]+m['tensors']:assert hashlib.sha256(Path(i['file']).read_bytes()).hexdigest()==i['sha256']
assert hashlib.sha256(Path(m['source_video']).read_bytes()).hexdigest()==m['source_video_sha256'];p=Path(TARGET);raw=(json.dumps(m,indent=2)+'\\n').encode();p.write_bytes(raw);print(json.dumps({'status':'cache_ready','manifest':str(p),'manifest_sha256':hashlib.sha256(raw).hexdigest(),'source_video_sha256':m['source_video_sha256'],'geometry':m['geometry']}))
'''.replace('TARGET',repr(DST+'/innovation_cache/short_0252/manifest.json'));ready=json.loads(remote('H3_HOST_RTX4090',code,json.dumps({'manifest':target}).encode()));(D/'AIRCRAFT_CACHE_READY.json').write_text(json.dumps({'ready':ready,'transfer':receipt,'source_manifest_sha256':hashlib.sha256(raw).hexdigest(),'network':'privateIP SSH direct; no proxy/no local payload file'},indent=2));print(json.dumps(ready))
