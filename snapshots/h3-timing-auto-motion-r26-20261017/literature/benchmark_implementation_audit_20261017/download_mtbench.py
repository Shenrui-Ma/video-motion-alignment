import hashlib,json,pathlib,time,urllib.request,os
b=pathlib.Path(__file__).resolve().parent;meta=json.loads((b/'MTBENCH_DOWNLOAD_HEAD.json').read_text());d=b/'downloads';d.mkdir(exist_ok=True)
p=d/'MTBench.zip';tmp=d/'MTBench.zip.partial';start=time.time();h=hashlib.sha256();n=0
with urllib.request.urlopen(meta['url'],timeout=60) as r, tmp.open('xb') as f:
 while True:
  c=r.read(1024*1024)
  if not c:break
  f.write(c);h.update(c);n+=len(c)
  if n%(32*1024*1024)==0:print(n,round(time.time()-start,2),flush=True)
assert n==meta['declared_bytes_from_api'];assert h.hexdigest()==meta['expected_sha256'];os.replace(tmp,p)
a={'path':str(p),'bytes':n,'sha256':h.hexdigest(),'seconds':time.time()-start,'url':meta['url']};(b/'MTBENCH_DOWNLOAD_RECEIPT.json').write_text(json.dumps(a,indent=2));print(a)
