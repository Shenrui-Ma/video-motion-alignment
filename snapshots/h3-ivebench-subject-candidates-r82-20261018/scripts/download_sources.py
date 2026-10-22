from pathlib import Path
import json,hashlib,urllib.request,shutil,time,concurrent.futures
R=Path(__file__).resolve().parents[1];plan=json.loads((R/'metadata/REVIEW_PLAN.json').read_text());REV=plan['official_dataset_revision'];IDS=plan['review_order']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
paths=['ivebenchdb_mp4_short/'+s+'.mp4' for s in IDS]
request=urllib.request.Request('https://huggingface.co/api/datasets/Coraxor/IVEBench/paths-info/'+REV,data=json.dumps({'paths':paths,'expand':True}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=60) as f:info=json.load(f)
(R/'metadata/OFFICIAL_FILES_INFO.json').write_text(json.dumps(info,indent=2)+'\n');assert {x['path'] for x in info}==set(paths)
print('source_count',len(IDS),'bytes',sum(x['size'] for x in info),flush=True)
def one(sid):
 rec=next(x for x in info if x['path'].endswith(sid+'.mp4'));url='https://huggingface.co/datasets/Coraxor/IVEBench/resolve/'+REV+'/'+rec['path'];p=R/'sources'/(sid+'.mp4');start=time.monotonic()
 if not p.exists():
  with urllib.request.urlopen(url,timeout=120) as f,p.with_suffix('.part').open('wb') as out:shutil.copyfileobj(f,out)
  p.with_suffix('.part').rename(p)
 assert p.stat().st_size==rec['size'] and sha(p)==rec['lfs']['oid'],sid
 return {'source_id':sid,'file':str(p),'url':url,'sha256':sha(p),'bytes':p.stat().st_size,'official_lfs':rec['lfs'],'wall_seconds':time.monotonic()-start}
receipts=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 futures={pool.submit(one,sid):sid for sid in IDS}
 for f in concurrent.futures.as_completed(futures):
  row=f.result();receipts.append(row);(R/'audit/DOWNLOAD_RECEIPTS.json').write_text(json.dumps(receipts,indent=2)+'\n');print(row['source_id'],row['bytes'],flush=True)
