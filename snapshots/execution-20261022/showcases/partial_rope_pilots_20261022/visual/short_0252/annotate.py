from pathlib import Path
import json,hashlib
from PIL import Image,ImageDraw,ImageFont
D=Path(__file__).resolve().parent; E=D.parents[3]
a=json.loads((E/'timing/event_offset_completion_20261022/short_0252/ANNOTATION.json').read_text())
manifest=json.loads((E/'metrics/manifest.json').read_text())['jobs']
roles=['source','native','global_weak','partial_temporal_rope']; prov=[]
for role in roles:
 j=next(j for j in manifest if j['task_id']=='short_0252' and j['method']==role)
 digest=hashlib.sha256((D/(role+'.mp4')).read_bytes()).hexdigest(); assert digest==j['sha256']
 if role!='partial_temporal_rope': assert digest==a['video_provenance'][role]['sha256']
 prov.append({'method':role,'sha256':digest,'video':j['video']})
intervals=[[58,61],[63,66],[83,89]]
notes=['57帧左手先抬，58帧右手开始离腿，59–61帧双手持续向面罩靠近；双手事件按58–61记录。','62帧左手仍接近杯体；63帧指尖开始与杯缘重叠，64–66帧逐渐形成抓持。透明袋、杯缘和指尖遮挡使接触定位采用63–66过渡区间。','82帧右手仍靠近杯侧；83帧开始离杯抬带，84–86帧持续上抬，87–89帧进入胸前上方。按83–89过渡区间记录。']
events=[]
for ev,iv,note in zip(a['events'],intervals,notes):
 d={k:ev[k] for k in ['id','label','definition','source','native','global_weak']};d['partial_temporal_rope']=iv; d['notes']=note
 d['offset_frames']={m:(sum(d[m])-sum(d['source']))/2 for m in roles[1:]}
 d['offset_interval_frames']={m:[d[m][0]-d['source'][1],d[m][1]-d['source'][0]] for m in roles[1:]}
 events.append(d)
mean={m:sum(abs(x['offset_frames'][m]) for x in events)/3 for m in roles[1:]}
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf',28)
labels=['参考视频','Baseline','α = 0.25','部分RoPE频带']
for frame in [52,75]:
 out=Image.new('RGB',(2560,410),'black');dr=ImageDraw.Draw(out)
 for i,(role,label) in enumerate(zip(roles,labels)):
  im=Image.open(D/role/f'{frame:03d}.png').resize((640,360));out.paste(im,(i*640,0));box=dr.textbbox((0,0),label,font=font);dr.text((i*640+(640-box[2]+box[0])/2,372-box[1]),label,font=font,fill='white')
 out.save(D/f'comparison_frame_{frame:03d}.jpg',quality=94)
r={'case_id':'short_0252','dataset':'IVEBench','fps':24,'valid_frames':98,'annotation_source':'AI visual frame annotation, current source/native/weak boundary frames rechecked and partial full-span overview plus event-adjacent consecutive frames inspected','frame_index':'zero_based','offset_definition':'generated transition midpoint minus source transition midpoint; positive means delayed','events':events,'mean_absolute_offset_frames':mean,'video_provenance':prov,'historical_annotations_sha256':hashlib.sha256((E/'timing/event_offset_completion_20261022/short_0252/ANNOTATION.json').read_bytes()).hexdigest(),'visual_conclusion':'部分RoPE频带的三个动作仍整体延后，平均绝对偏移15.0帧，与普通编辑15.0帧接近；全程α=0.25为0.0帧。该样例的局部动作时间对齐未改善。','uncertainty':'事件以过渡区间标注，杯缘与手指遮挡造成数帧定位范围；原始区间和偏移范围均保留。','evidence_files':['partial_overview.jpg','partial_hands_detail.jpg','partial_raise_detail.jpg','source_events.jpg','native_events.jpg','global_weak_events.jpg','comparison_frame_052.jpg','comparison_frame_075.jpg']}
(D/'ANNOTATION.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
print(json.dumps(mean,ensure_ascii=False))
