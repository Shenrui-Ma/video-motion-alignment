import concurrent.futures, hashlib, json, pathlib, urllib.request
BASE=pathlib.Path(__file__).resolve().parent
REPOS={'FlowMotion':'HKUST-LongGroup/FlowMotion','FlowDirector':'Westlake-AGI-Lab/FlowDirector','MotionEcho':'euminds/motionecho','TempoControl':'Shira-Schiber/TempoControl','SyncLoRA':'SagiPolaczek/Sync-LoRA','DynaEdit':'dynaedit/dynaedit.github.io'}
def get(url):
 r=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'research-metadata-audit'}),timeout=40)
 return r.read()
def one(k,repo):
 d=BASE/'sources'/k;d.mkdir(parents=True,exist_ok=True)
 meta=json.loads(get('https://api.github.com/repos/'+repo)); branch=meta['default_branch']
 commit=json.loads(get(f'https://api.github.com/repos/{repo}/commits/{branch}'));sha=commit['sha']
 tree=json.loads(get(f'https://api.github.com/repos/{repo}/git/trees/{sha}?recursive=1'))
 for n,v in [('repo.json',meta),('commit.json',commit),('tree.json',tree)]: (d/n).write_text(json.dumps(v,indent=2))
 files=[x for x in tree['tree'] if x['type']=='blob']
 for x in files:
  if x['path'].lower() in ['readme.md','license','license.md','license.txt']:
   (d/pathlib.Path(x['path']).name).write_bytes(get(f'https://raw.githubusercontent.com/{repo}/{sha}/'+x['path']))
 return {'name':k,'repo':repo,'commit':sha,'truncated':tree.get('truncated'),'files':len(files),'candidates':[{'path':x['path'],'bytes':x.get('size'),'sha':x['sha']} for x in files if any(s in x['path'].lower() for s in ['eval','metric','bench','dataset','data/','test/']) or x['path'].endswith(('.csv','.json','.yaml','.yml'))]}
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
 for f in concurrent.futures.as_completed([ex.submit(one,k,v) for k,v in REPOS.items()]):
  try:rows.append(f.result())
  except Exception as e:rows.append({'error':repr(e)})
(BASE/'REPOSITORY_AUDIT.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
