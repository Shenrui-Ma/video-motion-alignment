from pathlib import Path
import json,hashlib,urllib.request,shutil,concurrent.futures,time
R=Path(__file__).resolve().parents[1];plan=json.loads((R/'metadata/REVIEW_PLAN.json').read_text());rev=plan['official_revision']
paths=['ivebenchdb_mp4_'+i.split('_')[0]+'/'+i+'.mp4' for i in plan['review_ids']]
req=urllib.request.Request('https://huggingface.co/api/datasets/Coraxor/IVEBench/paths-info/'+rev,data=json.dumps({'paths':paths,'expand':True}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req,timeout=60) as f:info=json.load(f)
(R/'metadata/OFFICIAL_FILES_INFO.json').write_text(json.dumps(info,indent=2)+'\n')
assert len(info)==len(paths)
print('official_bytes',sum(x['size'] for x in info),flush=True)
def one(i):
 rec=next(x for x in info if x['path'].endswith('/'+i+'.mp4'));p=R/'sources'/(i+'.mp4');local=Path('/Users/researcher/DevProjects/h3-ivebench-next-candidates-20261018/sources')/p.name
 url='https://huggingface.co/datasets/Coraxor/IVEBench/resolve/'+rev+'/'+rec['path'];method='download_official'
 if not p.exists():
  if local.exists():shutil.copy2(local,p);method='copy_existing_official'
  else:
   with urllib.request.urlopen(url,timeout=120) as f,p.with_suffix('.part').open('wb') as g:shutil.copyfileobj(f,g)
   p.with_suffix('.part').rename(p)
 h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==rec['lfs']['oid'] and p.stat().st_size==rec['size'],i
 return {'source_id':i,'path':str(p),'sha256':h,'bytes':p.stat().st_size,'url':url,'method':method,'official_lfs':rec['lfs']}
res=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for f in concurrent.futures.as_completed([pool.submit(one,i) for i in plan['review_ids']]):
  row=f.result();res.append(row);(R/'metadata/SOURCE_RECEIPTS.json').write_text(json.dumps(res,indent=2)+'\n');print(row['source_id'],row['bytes'],flush=True)
