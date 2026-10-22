"""Add full-frame neighboring/ending motion evidence after the user's scope clarification."""
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw
import render_triplets as base

R=Path(__file__).resolve().parent
D=json.loads((R/'manifest.json').read_text())
SETTINGS={
 '05_real_megumi_v_s1':([104,125,139],[90,140],'片尾与侧倾：目标动作存在不代表后续序列完整保留。'),
 '05_real_megumi_v_s2':([104,125,139],[90,140],'片尾动作阶段与背景：源片结束姿态未被完整到达。'),
 '07_real_ary_v_s1':([82,100,130],[70,140],'后置举臂及片尾：A未清楚单独保留后置举臂；B有延后的举臂段。'),
 '07_real_ary_v_s2':([33,60,100],[18,110],'次数与上下文：B早期额外手势、目标时间和后续举臂均需一起核查。'),
}
W,H=656,368
RH=base.HEADER+H+base.FOOTER

def frames(path):
 raw=subprocess.check_output([base.FF,'-v','error','-threads','2','-i',path,'-filter_threads','1','-vf','scale=656:368','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','-'])
 size=W*H*3;assert len(raw)==141*size
 return [Image.frombytes('RGB',(W,H),raw[i*size:(i+1)*size]) for i in range(141)]

def row(seqs,c,i):
 im=Image.new('RGB',(W*3,RH),'white');d=ImageDraw.Draw(im)
 for col,label in enumerate(base.LABELS):
  x=col*W;d.rectangle((x,0,x+W-1,4),fill=base.COLORS[col]);d.text((x+12,11),label,font=base.font(24),fill=base.COLORS[col]);d.text((x+12,40),f"{c['title']} · f{i:03d} · {i/24:.3f} 秒",font=base.font(18),fill='#263448');im.paste(seqs[col][i],(x,base.HEADER));d.text((x+12,base.HEADER+H+9),'全画面 · 未裁切 · 三列同一时刻',font=base.font(19),fill='#667383')
 return im

def encode(rows,path,fps):
 p=subprocess.Popen([base.FF,'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W*3}x{RH}','-r',str(fps),'-i','-','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(path)],stdin=subprocess.PIPE)
 try:
  for im in rows:p.stdin.write(im.tobytes())
  p.stdin.close();assert p.wait()==0
 finally:
  if p.poll() is None:p.kill();p.wait()

page=(R/'index.html').read_text()
for c in D['cases']:
 key=c['key'];ids,bounds,note=SETTINGS[key];seqs=[frames(x['path']) for x in c['inputs']]
 im=Image.new('RGB',(W*3,36+RH*3),'white');draw=ImageDraw.Draw(im);draw.text((12,6),'后续动作 / 片尾概览 · 各行选取不同时间，每行三列同一时间 · 完整片段另附',font=base.font(20),fill='#263448')
 for j,i in enumerate(ids):im.paste(row(seqs,c,i),(0,36+j*RH))
 image=R/key/'后续动作与片尾_全画面概览.jpg';im.save(image,quality=97,subsampling=0)
 rows=[row(seqs,c,i) for i in range(bounds[0],bounds[1]+1)];vs=[]
 for fps,name in [(24,'上下文三列_正常速度.mp4'),(6,'上下文三列_四分之一速度.mp4')]:
  p=R/key/name;encode(rows,p,fps);pr=base.probe(p);assert int(pr['nb_read_frames'])==len(rows);vs.append({'path':p.relative_to(R).as_posix(),'probe':pr})
 c['neighbor_context']={'overview_frames':ids,'bounds':bounds,'note':note,'overview':image.relative_to(R).as_posix(),'videos':vs}
 marker=f'<details><summary>展开全画面连续对照 · 原片全部141帧</summary>'
 start=page.index(f'<section id="{key}">');pos=page.index(marker,start)
 new=f'<details open><summary>后续动作与片尾核查</summary><p>{note}</p><p>连续上下文 f{bounds[0]}–{bounds[1]}，保持三列同一帧；下方默认0.25倍速。</p><video controls preload="metadata" src="{vs[1]["path"]}"></video><p><a href="{vs[0]["path"]}">上下文正常速度</a>　<a href="{vs[1]["path"]}">上下文0.25倍速</a></p><a href="{image.relative_to(R).as_posix()}"><img loading="lazy" src="{image.relative_to(R).as_posix()}" alt="后续动作和片尾全画面三列概览"></a></details>'
 page=page[:pos]+new+page[pos:];print('CONTEXT',key,flush=True)
page=page.replace('<nav>','<p class="note"><b>结论范围：</b>预选手—脸目标在真人结果中可找到，并不代表整段没有丢失、缩短或改变其他动作。后续举臂和片尾也单独附上，不能把全部差异概括为时间对不上。</p><nav>',1)
(R/'index.html').write_text(page);(R/'manifest.json').write_text(json.dumps(D,ensure_ascii=False,indent=2))
with (R/'README.txt').open('a') as f:f.write('\n补充：每组另有后续动作/片尾全画面截图与连续视频。预选手—脸目标可找到，不等于所有动作完整保留；不得把其他动作的缺失/缩短/次数改变统称为时间错位。\n')
