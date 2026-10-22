import concurrent.futures, json, pathlib, urllib.request
b=pathlib.Path(__file__).resolve().parent
repos={'DeT':'Shi-qingyu/DeT','DiTFlow':'ditflow/ditflow','DMT':'diffusion-motion-transfer/diffusion-motion-transfer'}
def get(u):return urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'research-metadata-audit'}),timeout=40).read()
def one(k,r):
 d=b/'sources'/k;d.mkdir(parents=True,exist_ok=True)
 meta=json.loads(get('https://api.github.com/repos/'+r));c=json.loads(get(f'https://api.github.com/repos/{r}/commits/'+meta['default_branch']));s=c['sha'];t=json.loads(get(f'https://api.github.com/repos/{r}/git/trees/{s}?recursive=1'))
 for n,v in [('repo.json',meta),('commit.json',c),('tree.json',t)]: (d/n).write_text(json.dumps(v,indent=2))
 files=[x for x in t['tree'] if x['type']=='blob'];picked=[]
 for f in files:
  p=f['path']
  if f.get('size',0)<300000 and (p.lower() in ['readme.md','license','license.txt','license.md','evaluation.py','requirements.txt'] or p.startswith('eval/') and p.endswith('.py') or ('motion_fidelity' in p) or p.startswith('MTBench_subset/') and p.endswith(('.json','.txt','.csv','.yaml'))):
   out=d/p;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(get(f'https://raw.githubusercontent.com/{r}/{s}/{p}'));picked.append(p)
 return {'name':k,'repo':r,'commit':s,'truncated':t.get('truncated'),'files':len(files),'downloaded':picked,'relevant_files':[x for x in files if any(v in x['path'].lower() for v in ['eval','mtbench','motion_fidelity'])]}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex: rows=list(ex.map(lambda x:one(*x),repos.items()))
(b/'SCORER_REPOSITORIES.json').write_text(json.dumps(rows,indent=2))
for r in rows: print(r['name'],r['commit'],r['files'],r['downloaded']); print('Relevant count',len(r['relevant_files']))
d=b/'sources'/'MTBench';d.mkdir(parents=True,exist_ok=True)
for n,u in [('dataset_info.json','https://huggingface.co/api/datasets/QingyuShi/MTBench'),('tree.json','https://huggingface.co/api/datasets/QingyuShi/MTBench/tree/main?recursive=true&limit=1000')]:
 try:(d/n).write_bytes(get(u))
 except Exception as e:(d/(n+'.error')).write_text(str(e))
