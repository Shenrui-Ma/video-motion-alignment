"""Bind archived whole-frame media and translate already recorded visual review."""
from pathlib import Path
from fractions import Fraction
from datetime import datetime,timezone
import copy,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
PROJECTS=Path('/Users/researcher/DevProjects')
AUDIT=ROOT/'audit_native_v5'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,d):
 with p.open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2);f.write('\n')
def evidence(p,pointer=None):
 d={'path':str(p),'sha256':sha(p)}
 if pointer is not None:d['json_pointer']=pointer
 return d
base_path=ROOT/'benchmarks.native_snapshot_v4.json';base=read(base_path);data=copy.deepcopy(base)
review_path=PROJECTS/'h3-timing-ivebench-native-r54-20261017/analysis/postrun/mf_execution/fixed_native_review/ROOT_VISUAL_REVIEW.json'
plan_path=review_path.with_name('FIXED_PLAN.json');review=read(review_path);plan=read(plan_path)
review_by_id={v['pair_id']:(i,v) for i,v in enumerate(review['rows'])};plan_by_id={v['pair_id']:v for v in plan['cases']}
translations={
 'short_0210':'六个抽查帧均呈现男性外观。原片站立演讲并做手势，编辑后变为另一房间中的坐姿演讲；抽查画面内未呈现原片的手部动作。',
 'short_0230':'编辑后的构图未包含头巾，无法判断头巾是否改成蓝色；围裙仍有多种颜色。画面变为碗和手的近景，抽查帧中原片从袋中倒入食材，编辑后则用勺搅拌。',
 'short_0263':'六个抽查帧均呈现年轻女孩外观。原片坐着阅读，编辑后变为站立、随后行走；抽查帧中未呈现原片的书、椅子和阅读动作。',
 'short_0352':'抽查帧呈现女性外观，可见的旗袍是否满足“现代连衣裙”要求尚不明确。抽查画面内未呈现原片的指向手势，生成画面出现字幕。',
 'short_0370':'六个抽查帧均呈现衣服由蓝变白的修改，持杯和放下杯子的动作顺序大体保留。部分固定帧的头部朝向有差异，稀疏截图不足以确定可靠的动作时差。',
}
probes={};missing=[];bound=[];translation_audit=[]
def media(p,inventory,archive,kind):
 if not p.is_file():
  missing.append({'path':str(p),'reason':'archived media absent locally','kind':kind});return None
 rel=p.relative_to(archive).as_posix();assert rel in inventory,rel
 digest=sha(p);assert digest==inventory[rel]['sha256'],str(p)
 cmd=['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames,duration,start_time','-show_entries','format=duration','-of','json',str(p)]
 result=subprocess.run(cmd,capture_output=True,text=True,check=True);probe=json.loads(result.stdout);s=probe['streams'][0]
 frames=int(s['nb_read_frames']);fps=Fraction(s['avg_frame_rate'])
 assert frames>0 and fps>0
 if s.get('nb_frames') not in (None,'N/A'):assert int(s['nb_frames'])==frames
 index=len(probes);probe_path=AUDIT/f'ffprobe_{index:02d}.json';write(probe_path,{'path':str(p),'sha256':digest,'command':cmd,'result':probe})
 probes[str(p)]=evidence(probe_path)
 row={'path':str(p),'sha256':digest,'mime':'video/mp4','width':int(s['width']),'height':int(s['height']),'fps':float(fps),'fps_rational':str(fps),'frame_count':frames,'duration_seconds':float(s.get('duration',probe['format']['duration'])),'visible_height':int(s['height']),'panel_count':1,'panel_index':0,'media_kind':kind,'display_scope':'完整原文件；全画幅、全部帧、原顺序及原时间戳。','archive_evidence':evidence(archive/'FILE_INVENTORY.json','/'+rel.replace('~','~0').replace('/','~1')),'probe_evidence':evidence(probe_path)}
 bound.append({'path':str(p),'sha256':digest,'archive_inventory_sha256':sha(archive/'FILE_INVENTORY.json'),'frames':frames,'fps_rational':str(fps),'dimensions':[row['width'],row['height']]})
 return row
for b in data['benchmarks']:
 flex=b['id']=='flexiact'
 root=PROJECTS/('h3-timing-flexiact-native-r49-20261017' if flex else 'h3-timing-ivebench-native-r54-20261017')
 archive=root/'analysis/postrun/captured/batch';inventory=read(archive/'FILE_INVENTORY.json')
 for c in b['cases']:
  cid=c['id'];stem='source_'+cid if flex else cid;run=('r49_source_' if flex else 'r54_')+cid+'_seed2026101701_native'
  prov_path=archive/'inputs'/f'{stem}_provenance.json';prov=read(prov_path)
  for p in [prov_path]:assert sha(p)==inventory[p.relative_to(archive).as_posix()]['sha256']
  source=media(archive/'inputs'/f'{stem}_video.mp4',inventory,archive,'archived_model_input')
  original=media(archive/'inputs'/f'{stem}_original.mp4',inventory,archive,'original_public_source')
  out=media(archive/'output'/f'{run}_00001_.mp4',inventory,archive,'archived_native_full_output')
  if source is not None:
   assert source['sha256']==prov['video_sha256']
   valid=147 if flex else prov['effective_frame_count']
   assert source['frame_count']==(158 if flex else 90) and source['fps']==24
   source.update(valid_frame_count=valid,original_public_video=original,source_preparation=evidence(prov_path),input_to_original_frame=prov['input_to_original' if flex else 'input_to_original_frame'],padding_frame_indices=list(range(valid,source['frame_count'])),presentation_preprocessing='此记录直接使用归档字节；展示阶段没有新增处理。')
   if flex:source['input_preparation_note']='已冻结模型输入将原49帧各重复3次，再在末端填充11帧；本报告直接引用该158帧输入。'
   else:
    source['input_preparation_note']='已冻结模型输入为90帧24fps，保留原有效前缀、末端填充及固定外边距；本报告直接引用该输入。'
    source['content_rectangle_xywh']=prov['content_rectangle_xywh']
  if out is not None:
   assert out['frame_count']==source['frame_count'] and out['fps']==source['fps']
   out.update(valid_frame_count=source['valid_frame_count'],frame_pairing='与实际模型输入按相同帧号对应，展示未做时延对齐。')
  c['source_video']=source;c['ordinary']['video']=out
  if not flex:
   idx,rv=review_by_id[cid];pl=plan_by_id[cid];contact=Path(rv['contact_sheet']);assert contact.is_file() and sha(contact)==rv['sha256']
   c['ordinary'].update(visual_observation=translations[cid],visual_scope='检查有效前缀内预先固定的六帧：'+ '、'.join(map(str,pl['fixed_indices']))+'（24fps）；这些是抽样观察，编辑成功率标签保持 UNKNOWN。',visual_evidence=evidence(review_path,f'/rows/{idx}'),visual_frame_indices=pl['fixed_indices'],visual_contact_sheet={'path':str(contact),'sha256':rv['sha256'],'mime':'image/png'},visual_plan_evidence=evidence(plan_path,f'/cases/{idx}'))
   translation_audit.append({'pair_id':cid,'source':rv,'source_scope':review['scope'],'translation':translations[cid],'fixed_indices':pl['fixed_indices'],'review_sha256':sha(review_path),'plan_sha256':sha(plan_path)})
# Validate exact preservation outside the narrowly authorized media/review fields.
allowed_ordinary={'video','visual_observation','visual_scope','visual_evidence','visual_frame_indices','visual_contact_sheet','visual_plan_evidence'}
changes=[]
for oldb,newb in zip(base['benchmarks'],data['benchmarks']):
 assert {k:v for k,v in oldb.items() if k!='cases'}=={k:v for k,v in newb.items() if k!='cases'}
 for old,new in zip(oldb['cases'],newb['cases']):
  assert old['automatic']==new['automatic']
  assert {k:v for k,v in old.items() if k not in ('source_video','ordinary')}=={k:v for k,v in new.items() if k not in ('source_video','ordinary')}
  assert {k:v for k,v in old['ordinary'].items() if k not in allowed_ordinary}=={k:v for k,v in new['ordinary'].items() if k not in allowed_ordinary}
  if oldb['id']=='flexiact':assert {k:v for k,v in old['ordinary'].items() if k!='video'}=={k:v for k,v in new['ordinary'].items() if k!='video'}
  changes.append({'benchmark':oldb['id'],'case':old['id'],'changed_fields':['source_video']+['ordinary.'+k for k in new['ordinary'] if old['ordinary'].get(k)!=new['ordinary'][k]]})
assert {k:v for k,v in base.items() if k!='benchmarks'}=={k:v for k,v in data.items() if k!='benchmarks'}
write(ROOT/'benchmarks.native_snapshot_v5.json',data)
write(AUDIT/'TRANSLATION_EVIDENCE.json',translation_audit)
write(AUDIT/'MEDIA_BINDINGS.json',{'status':'COMPLETE' if not missing else 'PARTIAL','bound_media_count':len(bound),'main_source_records':sum(c['source_video'] is not None for b in data['benchmarks'] for c in b['cases']),'main_ordinary_records':sum(c['ordinary']['video'] is not None for b in data['benchmarks'] for c in b['cases']),'files':bound,'missing':missing})
write(AUDIT/'FIELD_DIFF_CHECK.json',{'status':'PASS','source_v4':evidence(base_path),'output_v5':evidence(ROOT/'benchmarks.native_snapshot_v5.json'),'preserved':['all original MF values and evidence','all timing values and UNKNOWN','all edit_success UNKNOWN','all policy IDs and evidence','all automatic pending objects','all original task text and evaluation definitions','all original top-level fields'],'changed_fields':changes,'missing':missing,'created_utc':datetime.now(timezone.utc).isoformat()})
print(json.dumps({'v5_sha256':sha(ROOT/'benchmarks.native_snapshot_v5.json'),'sources':10,'ordinary':10,'media_bound':len(bound),'missing':missing,'diff':'PASS'},indent=2))
