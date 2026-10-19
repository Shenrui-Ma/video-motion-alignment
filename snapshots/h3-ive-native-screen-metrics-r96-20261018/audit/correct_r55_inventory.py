import sys,json,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import sha,read,save,require
r=Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018');inv=r/'inventory/ivebench.json';review=r/'audit/task_acceptance_consistency_20261019/REVIEW.json';native=Path('/Users/researcher/DevProjects/h3-timing-ivebench-native-r54-20261017/analysis/postrun/mf_execution/fixed_native_review/ROOT_VISUAL_REVIEW.json')
d=read(inv);before=copy.deepcopy(d);report=read(review);targets=['r55_short_0210','r55_short_0230','r55_short_0263','r55_short_0352'];a=r/'audit/ive_task_acceptance_correction_20261019';a.mkdir();(a/'PREVIOUS_IVEBENCH.json').write_bytes(inv.read_bytes())
summaries={
'r55_short_0210':'对应R54的固定六帧审阅：男人已出现，但站立演讲变为另一房间的坐姿，参考中的手势在所检画面缺席，原场景与动作保持失败。R55实际0次干预，成片RGB与PTS逐帧等同R54，继承同样的已观察问题。',
'r55_short_0230':'对应R54的固定六帧审阅：画面变为手与碗的近景，参考的倒料动作变成勺子搅拌。头巾出画、围裙仍含多色，改蓝任务完成度为UNKNOWN。R55实际0次干预，成片RGB与PTS逐帧等同R54，原动作保持失败。',
'r55_short_0263':'对应R54的固定六帧审阅：女孩已出现，但坐姿阅读变为站立、走动，书、椅及阅读动作在所检画面缺席，原场景与动作保持失败。R55实际0次干预，成片RGB与PTS逐帧等同R54。',
'r55_short_0352':'对应R54的固定六帧审阅：女人已出现，但可见旗袍是否满足现代连衣裙要求为UNKNOWN；参考指点手势在所检画面缺席，并新增字幕。R55实际0次干预，成片RGB与PTS逐帧等同R54，原动作保持失败。'}
changes=[]
for x in d['items']:
 if x['id'] not in targets:continue
 row=next(z for z in report['rows'] if z['id']==x['id']);old=copy.deepcopy(x)
 for e in row['evidence']:require(sha(e['file'])==e['sha256'],'review evidence bytes changed')
 ident=next(Path(p) for p in x['evidence_paths'] if 'media_identity' in p);proof=read(ident);require(proof['all_off'] and proof['proofs']['full_video']['exact'] and proof['proofs']['score_video']['exact'],'zero/exact media proof absent')
 x['review_status']='原场景与动作保持失败；自动零触发' if x['id'] in targets[::2] else '原动作保持失败；自动零触发'
 x['review_status_code']='task_failure';x['review_summary']=summaries[x['id']]
 x['task_acceptance']={k:v.upper() for k,v in row['classification'].items()};x['task_acceptance_scope']='R54预定六个时刻的既有审阅，通过已核RGB/PTS完全相同关系继承到R55；本次未新增成片审阅。'
 for p in [str(native),str(review)]:
  if p not in x['evidence_paths']:x['evidence_paths'].append(p)
  x['evidence_sha256'][p]=sha(p)
 require(x['guidance_activation']=='zero' and x['actual_routed_blocks']==0,'activation changed')
 require(x['media_sha256']==old['media_sha256'],'media changed')
 changes.append({'id':x['id'],'before_status':old['review_status'],'after_status':x['review_status'],'reason':row['reason'],'classification':x['task_acceptance']})
require(len(changes)==4,'target count differs');require(len(d['items'])==len(before['items']),'denominator changed')
for old,new in zip(before['items'],d['items']):
 if old['id'] not in targets:require(old==new,'unowned inventory entry changed')
 else:
  for k in old:
   if k not in ['review_status','review_status_code','review_summary','evidence_paths','evidence_sha256']:require(old[k]==new[k],'unexpected changed field '+k)
tmp=inv.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');tmp.replace(inv)
save(a/'RECEIPT.json',{'passed':True,'modified':4,'added':0,'total_items':len(d['items']),'media_changed':False,'activation_counts_changed':False,'success_count_fields_changed':False,'changes':changes,'previous_sha256':sha(a/'PREVIOUS_IVEBENCH.json'),'inventory_sha256':sha(inv),'review_sha256':sha(review),'native_visual_sha256':sha(native)})
print(json.dumps(read(a/'RECEIPT.json'),ensure_ascii=False))
