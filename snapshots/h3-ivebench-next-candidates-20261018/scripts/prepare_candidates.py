from pathlib import Path
import json,hashlib,urllib.request,shutil,time,csv,re
R=Path(__file__).resolve().parents[1]
REV='1e6cb655c0a537f6093edcf18e2607fb03e76734'
P=Path('/Users/researcher/DevProjects/h3-ivebench-pilot-20261017')
IDS=['short_0135','short_0252','short_0065','long_0031','long_0163','long_0115']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
for name in ('ivebenchdb_prompt_short.json','ivebenchdb_prompt_long.json','ivebenchdb_name_mapping.csv'):shutil.copy2(P/'literature/dataset_original'/name,R/'metadata'/name)
alltasks=json.loads((P/'inputs_selection/ALL_600_TASKS.json').read_text());tasks=[next(x for x in alltasks if x['src_video_name']==s+'.mp4') for s in IDS]
write(R/'metadata/METADATA_PREFILTER.json',{'revision':REV,'source_only':True,'generated_results_used':0,'review_order':IDS,'tasks':tasks,'criteria':'Visible body/hand/tool motion; official task changes appearance or identity without requesting action change. Select at most6 after inspecting full source six-frame overview. Original official task stays verbatim.'})
paths=['ivebenchdb_mp4_'+s.split('_')[0]+'/'+s+'.mp4' for s in IDS]
url='https://huggingface.co/api/datasets/Coraxor/IVEBench/paths-info/'+REV
req=urllib.request.Request(url,data=json.dumps({'paths':paths,'expand':True}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req,timeout=60) as f:info=json.load(f)
write(R/'metadata/OFFICIAL_FILES_INFO.json',info)
assert {x['path'] for x in info}==set(paths)
print('planned bytes',sum(x['size'] for x in info),flush=True)
receipts=[]
for src in IDS:
 rel='ivebenchdb_mp4_'+src.split('_')[0]+'/'+src+'.mp4';record=next(x for x in info if x['path']==rel);url='https://huggingface.co/datasets/Coraxor/IVEBench/resolve/'+REV+'/'+rel;p=R/'sources'/(src+'.mp4');start=time.monotonic()
 if not p.exists():
  with urllib.request.urlopen(url,timeout=90) as f,p.with_suffix('.part').open('wb') as out:shutil.copyfileobj(f,out)
  p.with_suffix('.part').rename(p)
 assert sha(p)==record['lfs']['oid'] and p.stat().st_size==record['size']
 receipts.append({'source_id':src,'relative_path':rel,'file':str(p),'url':url,'sha256':sha(p),'bytes':p.stat().st_size,'official_lfs':record['lfs'],'wall_seconds':time.monotonic()-start})
 write(R/'audit/DOWNLOAD_RECEIPTS.json',receipts);print(src,p.stat().st_size,flush=True)
