from pathlib import Path
import json,hashlib,urllib.request,concurrent.futures,csv,shutil,datetime
R=Path(__file__).resolve().parent
OLD=Path('/Users/researcher/DevProjects/h3-flexiact-expanded-selection-20261018/metadata/HF_TREE.json')
tree=json.loads(OLD.read_text());rev=tree['revision'];by={x['path']:x for x in tree['files']};receipts=[]
(R/'metadata').mkdir(exist_ok=True)
shutil.copy2(OLD,R/'metadata/PINNED_TREE.json')
def fetch(path):
 item=by[path];dest=R/'assets'/path;dest.parent.mkdir(parents=True,exist_ok=True)
 local=Path('/Users/researcher/DevProjects/h3-flexiact-expanded-selection-20261018/official_assets')/path
 if '/captions/'in path:
  for root in [Path('/Users/researcher/DevProjects/h3-flexiact-expanded-selection-20261018/metadata'),Path('/Users/researcher/DevProjects/h3-timing-auto-motion-r26-20261017/literature/benchmark_selection_20261017/sources')]:
   candidate=root/('flexiact_hf__'+path.replace('/','__'))
   if candidate.exists():local=candidate;break
 if local.exists():data=local.read_bytes();origin='existing_local:'+str(local)
 else:
  url='https://huggingface.co/datasets/shiyi0408/FlexiAct/resolve/'+rev+'/'+path
  with urllib.request.urlopen(url,timeout=45)as response:data=response.read()
  origin=url
 digest=hashlib.sha256(data).hexdigest();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
 if item.get('lfs'):assert digest==item['lfs']['oid'],(path,'lfs mismatch')
 else:assert blob==item['oid'],(path,'git blob mismatch')
 assert len(data)==item['size'];dest.write_bytes(data)
 return {'dataset_path':path,'path':str(dest),'bytes':len(data),'sha256':digest,'git_blob_oid':blob,'origin':origin,'verified':True}
paths=[p for p in by if p.startswith('benchmark/captions/')and p.endswith(('val_image.csv','crop.csv'))]
paths+=['benchmark/reference_videos/animal/'+n+'.mp4' for n in ['dogjump','dogstand','kangaroo']]
with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:
 for result in pool.map(fetch,paths):receipts.append(result)
targets=[]
for name in ['dogjump','dogstand','kangaroo']:
 rows=list(csv.DictReader((R/'assets/benchmark/captions/animal'/name/'val_image.csv').open()))
 targets.extend(r['path'] for r in rows)
with concurrent.futures.ThreadPoolExecutor(max_workers=3)as pool:
 receipts.extend(pool.map(fetch,sorted(set(targets))))
# Current repository revision is checked separately; the experiment candidates stay pinned.
try:
 with urllib.request.urlopen('https://huggingface.co/api/datasets/shiyi0408/FlexiAct',timeout=45)as response:info=json.load(response)
 (R/'metadata/HF_INFO_CURRENT.json').write_text(json.dumps(info,indent=2)+'\n')
 current={'sha':info['sha'],'same_as_pinned':info['sha']==rev}
except Exception as e:current={'error':repr(e)}
(R/'FETCH_RECEIPT.json').write_text(json.dumps({'revision':rev,'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'current_repository':current,'files':receipts,'GPU_started':False},indent=2)+'\n')
print(json.dumps({'files':len(receipts),'bytes':sum(r['bytes']for r in receipts),'current':current},indent=2))
