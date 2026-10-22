"""Acquire approved public source assets, bound by pinned revision, LFS SHA and 500MB cap."""
import concurrent.futures,hashlib,json,subprocess,urllib.request,time
from pathlib import Path
P=Path(__file__).parent;plan=json.loads((P/'FLEXIACT_ASSET_DOWNLOAD_PLAN.json').read_text());root=P/'official_assets';root.mkdir(exist_ok=True)
assert plan['declared_total_bytes']<=plan['byte_limit']
headers=[]
for item in plan['files']:
 url='https://huggingface.co/datasets/shiyi0408/FlexiAct/resolve/'+plan['revision']+'/'+item['path']
 with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=60) as r:
  hs={k.lower():v for k,v in r.headers.items()};headers.append({'path':item['path'],'url':url,'status':r.status,'headers':hs,'declared_bytes':item['size']})
  if hs.get('content-length'):assert int(hs['content-length'])==item['size']
(P/'FLEXIACT_ASSET_HEAD.json').write_text(json.dumps(headers,indent=2)+'\n')
def get(item):
 url='https://huggingface.co/datasets/shiyi0408/FlexiAct/resolve/'+plan['revision']+'/'+item['path'];dest=root/item['path'];dest.parent.mkdir(parents=True,exist_ok=True)
 if dest.exists():b=dest.read_bytes()
 else:
  with urllib.request.urlopen(url,timeout=60) as r:b=r.read(item['size']+1)
  assert len(b)==item['size'];assert hashlib.sha256(b).hexdigest()==item['lfs']['oid'];dest.write_bytes(b)
 assert len(b)==item['size'];assert hashlib.sha256(b).hexdigest()==item['lfs']['oid']
 result={'path':item['path'],'local_path':str(dest),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'url':url,'lfs_exact':True}
 if dest.suffix=='.mp4':
  q=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,avg_frame_rate,nb_frames,duration,time_base:format=duration','-of','json',str(dest)],check=True,capture_output=True,text=True);result['probe']=json.loads(q.stdout)
 return result
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:out=list(ex.map(get,plan['files']))
(P/'FLEXIACT_ASSET_RECEIPT.json').write_text(json.dumps({'revision':plan['revision'],'downloaded_bytes':sum(x['bytes'] for x in out),'count':len(out),'all_lfs_exact':True,'files':out},indent=2)+'\n')
print(json.dumps({'count':len(out),'bytes':sum(x['bytes'] for x in out),'videos':[(x['path'],x.get('probe')) for x in out if 'probe' in x]}))
