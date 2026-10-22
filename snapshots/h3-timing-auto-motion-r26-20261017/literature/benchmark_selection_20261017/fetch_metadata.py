# Read-only source acquisition: text metadata/code only, no media or model weights.
import concurrent.futures, hashlib, json, urllib.request
from pathlib import Path
P=Path(__file__).parent; S=P/'sources'
old=json.loads((P/'source_inventory.json').read_text())
jobs={}
for dataset,local in [('shiyi0408/FlexiAct','flexiact'),('Coraxor/IVEBench','ive')]:
 jobs[local+'_hf_info.json']='https://huggingface.co/api/datasets/'+dataset
for row in json.loads((S/'flexiact_hf_retry').read_text()):
 path=row['path']
 if path.endswith('.csv') or path.endswith('extract_vid_and_crop.py'):
  jobs['flexiact_hf__'+path.replace('/','__')]='https://huggingface.co/datasets/shiyi0408/FlexiAct/resolve/main/'+path
for repo,prefix,paths in [
 ('shiyi-zh0408/FlexiAct','flexiact',['eval/motion_fidelity/co-tracker/cotracker/utils/visualizer.py','scripts/inference.py','data/image_dataset.py','requirements.txt']),
 ('RyanChenYN/IVEBench','ive',['data_process/mp42frames_batch.py','data_process/resize_batch.py','requirements.txt'])]:
 commit=json.loads((S/(prefix+'_tree.txt')).read_text())['sha']
 for path in paths:jobs[prefix+'_'+path.replace('/','__')]='https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+path

def get(item):
 n,url=item
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'H3-benchmark-readonly-audit'}),timeout=45) as r:b=r.read(2000001)
  if len(b)>2000000:raise ValueError('text size cap')
  (S/n).write_bytes(b)
  return {'local':str(S/n),'url':url,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'status':'downloaded_text_only'}
 except Exception as e:return {'local':str(S/n),'url':url,'status':'failed','error':repr(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:results=list(ex.map(get,jobs.items()))
(P/'source_inventory_additional.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({'total':len(results),'ok':sum(x['status']=='downloaded_text_only' for x in results),'errors':[x for x in results if x['status']=='failed']}))
