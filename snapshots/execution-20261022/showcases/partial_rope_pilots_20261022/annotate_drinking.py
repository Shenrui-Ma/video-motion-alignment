from pathlib import Path
import json,hashlib
from PIL import Image,ImageDraw,ImageFont
E=Path(__file__).resolve().parents[2];D=Path(__file__).resolve().parent/'visual/short_0358'
a=json.loads((E/'timing/event_offset_completion_20261022/short_0358/ANNOTATION.json').read_text());m=json.loads((E/'metrics/manifest.json').read_text())['jobs'];methods=['source','native','global_weak','partial_temporal_rope']
intervals=[[12,17],[36,39],[92,95]]
notes=['手臂在12–17帧下压进入低位；相对参考略提前，过渡范围有重叠。','35帧瓶口仍接近嘴唇，36–39帧进入接触并开始饮酒，与全程弱引导接近。','91帧仍贴嘴，92–95帧逐步离嘴下降；参考80–84帧已经完成该过渡，末段延后仍明显。']
events=[]
for e,iv,note in zip(a['events'],intervals,notes):
 e={k:e[k] for k in ['id','label','definition','source','native','global_weak']};e['partial_temporal_rope']=iv;e['note']=note
 e['offset_frames']={method:sum(e[method])/2-sum(e['source'])/2 for method in methods[1:]}
 e['offset_range_frames']={method:[e[method][0]-e['source'][1],e[method][1]-e['source'][0]] for method in methods[1:]}
 events.append(e)
means={method:sum(abs(e['offset_frames'][method]) for e in events)/3 for method in methods[1:]}
prov={}
for method in methods:
 j=next(j for j in m if j['task_id']=='short_0358' and j['method']==method);sha=hashlib.sha256((D/(method+'.mp4')).read_bytes()).hexdigest();assert sha==j['sha256'];prov[method]={'sha256':sha,'job_id':j['id']}
obj={'case_id':'short_0358','fps':24,'annotation_source':'AI visual frame annotation','frame_indexing':'zero_based','events':events,'means':means,'video_provenance':prov,'protocol':'沿用冻结参考和三事件定义；全片每8帧扫描，事件附近连续逐帧复核；偏移取过渡区间中点差，均值取绝对值。范围表示视觉边界定位范围。','visual_conclusion':'部分RoPE频带使瓶口到嘴的时刻接近参考；饮酒结束时瓶口离嘴仍延后约11.5帧。三事件平均绝对偏移4.67帧，普通编辑6.67帧，全程弱引导1.33帧。'}
(D/'ANNOTATION.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2))
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf',25)
for f in [42,85]:
 out=Image.new('RGB',(3072,490),'black');draw=ImageDraw.Draw(out)
 for i,(method,label) in enumerate(zip(methods,['参考视频','Baseline','α = 0.25','部分RoPE频带'])):
  out.paste(Image.open(D/method/f'{f:03d}.jpg'),(i*768,0));draw.text((i*768+25,442),f'{label} · {f}帧',font=font,fill='white')
 out.save(D/f'comparison_frame_{f:03d}.jpg',quality=90)
print(json.dumps(means))
