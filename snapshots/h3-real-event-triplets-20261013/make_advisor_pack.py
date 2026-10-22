"""A two-case, same-time presentation; no claim of whole-video action omission."""
import json
from pathlib import Path
from PIL import Image, ImageDraw
import render_triplets as b

R=Path(__file__).resolve().parent
OUT=R/'导师展示_两个明显时间点'
OUT.mkdir(exist_ok=True)
SPECS=[
 ('05_real_megumi_v_s1','案例1_黑裙改红',[55,56,57],[46,64],'原片手在眼旁，编辑结果同一时刻手仍在较低位置。'),
 ('07_real_ary_v_s1','案例2_白衣改蓝',[60,61,62],[50,69],'原片手在上脸附近，编辑结果同一时刻正在举臂。'),
]
original=json.loads((R/'manifest.json').read_text())
records=[]
for key,name,ids,bounds,note in SPECS:
 c=next(x for x in original['cases'] if x['key']==key)
 seqs=[b.decode(Path(p['path']),c['crop']) for p in c['inputs']]
 im=Image.new('RGB',(b.W*3,46+b.PANEL_H*3),'white');d=ImageDraw.Draw(im)
 d.text((12,10),'同一时刻的小动作不一致 · 左原片 / 中普通提示词 / 右明确强调小动作',font=b.font(22),fill='#263448')
 for j,i in enumerate(ids):im.paste(b.row(seqs,c,i),(0,46+j*b.PANEL_H))
 image=OUT/(name+'_三列截图.jpg');im.save(image,quality=98,subsampling=0)
 rows=[b.row(seqs,c,i) for i in range(bounds[0],bounds[1]+1)]
 normal=OUT/(name+'_正常速度.mp4');slow=OUT/(name+'_慢放展示.mp4')
 b.encode(rows,normal,24);b.encode(rows,slow,6)
 for path in [normal,slow]:assert int(b.probe(path)['nb_read_frames'])==len(rows)
 records.append({'case':key,'name':name,'note':note,'screenshots_frames':ids,'video_frames_inclusive':bounds,
  'image':image.name,'normal_video':normal.name,'slow_video':slow.name,
  'slow_video_probe':b.probe(slow),'normal_video_probe':b.probe(normal),'crop_xywh':c['crop'],
  'inputs':c['inputs'],'same_frame_all_columns':True,'independent_column_time_alignment':False})
 parts=[]
 for r in records:
  lo,hi=r['video_frames_inclusive']
  parts.append(f'<section><h2>{r["name"].replace("_"," · ")}</h2><p>{r["note"]}</p><p>局部放大 · 原片帧 f{lo}–{hi} · 慢放0.25×，无插帧</p><video controls preload="metadata" src="{r["slow_video"]}"></video><p><a href="{r["slow_video"]}">慢放视频</a> · <a href="{r["normal_video"]}">正常速度</a> · <a href="{r["image"]}">三列截图原图</a></p><img src="{r["image"]}" alt="同一帧的原片、A、B三列对照"></section>')
 page='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>两个真人案例：同一时刻的小动作不一致</title><style>body{font:18px/1.6 system-ui,sans-serif;color:#203349;background:#f4f7fa;margin:auto;max-width:1280px;padding:28px}h1{font-size:30px}h2{font-size:24px}section{background:white;padding:22px;border:1px solid #dce4ed;border-radius:10px;margin:25px 0}video,img{width:100%;height:auto}a{color:#165f9f}small{color:#5a6876}</style><h1>两个真人案例：同一时刻的小动作不一致</h1><p><b>左：原参考视频　中：A 普通提示词编辑　右：B 明确强调小动作后编辑</b></p><p>两组均选取原片小动作正在发生的短窗口，三列保持同一帧号；展示外观编辑后局部动作未在原时间忠实保留。</p>'''+''.join(parts)+'''<small>帧号从0开始，原片24 FPS。局部使用相同固定坐标裁切，未按动作重新对齐时间。此展示支持选定时刻动作不一致，不单独证明该动作在整段视频消失。完整上下文与两个种子的复核材料另行保留。</small></html>'''
 (OUT/'index.html').write_text(page)
 (OUT/'展示说明.txt').write_text('展示主题：同一时刻的小动作不一致\n左原片，中A普通提示词，右B明确强调小动作。\n案例1：黑裙改红，截图f55/56/57（2.292–2.375秒）；视频f46–64。\n案例2：白衣改蓝，截图f60/61/62（2.500–2.583秒）；视频f50–69。\n两组均取第一个固定种子。慢放只是同批帧以6 FPS播放，无插帧，无逐列时间对齐。原片和A/B在同一帧的动作明显不同；这不单独等同整段动作消失。\n打开index.html可展示，JPG和MP4可直接放进PPT。\n')
 (OUT/'manifest.json').write_text(json.dumps({'scope':'two clear same-time mismatch windows','cases':records,'new_inference':False},ensure_ascii=False,indent=2))
 print(name,'ready',flush=True)
