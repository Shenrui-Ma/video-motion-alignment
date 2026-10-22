from pathlib import Path
import json,hashlib,time
R=Path(__file__).resolve().parent;B=Path('/Users/researcher/DevProjects');h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
replacement='short_0021 short_0039 short_0084 short_0166 short_0185 short_0220 short_0242 short_0299 short_0308 short_0318 short_0394 long_0166'.split();clothes='short_0122 short_0167 short_0309 short_0330 short_0353 short_0395'.split();ids=replacement+clothes
inv=B/'h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json';used={r['source_id']for r in json.loads(inv.read_text())['items']};assert not set(ids)&used
metadata={};mb=[]
for kind in ['short','long']:
 p=B/f'h3-ivebench-next-candidates-20261018/metadata/ivebenchdb_prompt_{kind}.json';data=json.loads(p.read_text());mb.append({'file':str(p),'sha256':h(p),'records':len(data)})
 metadata.update({r['src_video_name'][:-4]:r for r in data})
review_paths=[B/'h3-ivebench-subject-candidates-r82-20261018/audit/INITIAL_25_VISUAL_REVIEW.json',B/'h3-ivebench-subject-candidates-r82-20261018/audit/SOURCE_REVIEW.json',B/'h3-ive-short-source-selection-20261020/SOURCE_SELECTION_REVIEW.json',B/'h3-ive-short-source-selection-20261020/ADDITIONAL_SOURCE_REVIEW.json',B/'h3-ive-short-source-selection-20261020/additional_subject_candidates/SOURCE_REVIEW.json']
hist={sid:[]for sid in ids}
def visit(x,p,loc='$'):
 if isinstance(x,dict):
  sid=x.get('source_id')
  if sid in hist and any(k in x for k in ['decision','priority','observation','observations']):
   fields={k:x[k]for k in ['decision','priority','scope','reason','observation','observations','limitations','visible_phases','reviewed_frames']if k in x}
   hist[sid].append({'record':fields,'evidence':{'file':str(p),'sha256':h(p),'json_path':loc}})
   return
  for k,v in x.items():visit(v,p,loc+'.'+k)
 elif isinstance(x,list):
  for i,v in enumerate(x):visit(v,p,f'{loc}[{i}]')
for p in review_paths:visit(json.loads(p.read_text()),p)
rows=[]
for sid in ids:
 m=metadata[sid];history=hist[sid];last=history[-1]['record']if history else {}
 reasons=[]
 for rec in history:
  d=rec['record'];dec=str(d.get('decision',d.get('priority',''))).lower()
  if any(s in dec for s in ['defer','exclude','reject']):
   txt=d.get('reason',d.get('limitations',d.get('observations',d.get('observation',''))))
   if txt and txt not in reasons:reasons.append(txt)
 rows.append({'source_id':sid,'selection_group':'person_animal_character_replacement'if sid in replacement else 'clothing_edit','official_category':m['category'],'official_subcategory':m['subcategory'],'official_edit_prompt':m['edit_prompt'],'official_source_caption':m['source_prompt'],'official_target_caption':m['target_prompt'],'reference_image_used':False,'not_in_current_inventory':True,'existing_defer_reasons':reasons,'latest_located_source_review_status':last.get('decision',last.get('priority','NO_PRIOR_REVIEW_LOCATED_IN_CHECKED_FILES')),'existing_review_history':history,'new_visual_review_performed':False})
out={'schema':'untried-subject-clothing-metadata-v1','created_unix':time.time(),'coverage':'All 400 short + 200 long official records. Untested means source_id absent from current inventory; no inference-history claim beyond this inventory audit. Captions are official metadata, not new visual observations.','inventory':{'file':str(inv),'sha256':h(inv),'unique_source_count':len(used)},'official_metadata':mb,'counts':{'replacement':12,'clothing':6,'total_unique_sources':18},'group_definition':'Replacement: existing people, animals or characters replaced, not objects replaced by animals. Clothing: five clothing-color edits and one suit removal; long0166 suit-associated character replacement counted only in replacement.','current_root_defer_directive':['short_0039','long_0166'],'rows':rows,'new_downloads':0,'new_gpu_jobs':0}
p=R/'UNTRIED_SUBJECT_CLOTHING_18.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(str(p));print(h(p));print('bytes',p.stat().st_size)
for r in rows:print(r['source_id'],r['latest_located_source_review_status'],len(r['existing_defer_reasons']))
