"""CPU-only reuse of evaluator's identically cropped frames; no visual selection."""
from pathlib import Path
import json, hashlib
import av
from PIL import Image, ImageDraw, ImageFont
ROOT=Path('/data/research-user/h3_metrics_20261022/showcase_main10_20261022')
ROLES=['source','native','early','fixed','late','split','global_weak']
LABELS=['参考视频','普通编辑','1–9 步引导','7–15 步引导','12–20 步引导','1–4＋16–20 步引导','全程弱引导 α=0.25']
font=ImageFont.truetype('/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc',22)
manifest=json.loads((ROOT/'new4_manifest.json').read_text())
for sid in ['short_0343','short_0114','crouch__movie_man_4','long_0167']:
 jobs={j['method']:j for j in manifest['jobs'] if j['task_id']==sid}
 outdir=ROOT/sid;outdir.mkdir(exist_ok=True)
 paths={r:Path(jobs[r]['target_frames_parent'])/Path(jobs[r]['metadata']['src_video_name']).stem for r in ROLES}
 n=jobs['source']['valid_frames'];fps=jobs['source']['fps'];shotframe=max(1,n//2)
 for r in ROLES:
  assert len(list(paths[r].glob('*.png')))==n,(sid,r)
  assert jobs[r]['valid_frames']==n and jobs[r]['fps']==fps
 output=av.open(str(outdir/'comparison.mp4'),'w');stream=output.add_stream('libx264',rate=fps);stream.width=1920;stream.height=1232;stream.pix_fmt='yuv420p';stream.codec_context.thread_count=2;stream.options={'crf':'19','preset':'fast'}
 for f in range(n):
  canvas=Image.new('RGB',(1920,1232),'black');strip=Image.new('RGB',(4480,384),'black') if f==shotframe else None
  for i,r in enumerate(ROLES):
   im=Image.open(paths[r]/f'{f+1:06d}.png').convert('RGB');im.thumbnail((640,360),Image.Resampling.LANCZOS)
   panel=Image.new('RGB',(640,384),'black');panel.paste(im,((640-im.width)//2,(360-im.height)//2));draw=ImageDraw.Draw(panel);draw.text((320,372),LABELS[i],font=font,fill='white',anchor='mm')
   xy=(640,0) if i==0 else (((i-1)%3)*640,384 if i<=3 else 768);canvas.paste(panel,xy)
   if strip is not None:strip.paste(panel,(i*640,0))
  if strip is not None:strip.save(outdir/'same_frame.jpg',quality=92)
  frame=av.VideoFrame.from_image(canvas);frame.pts=f
  for packet in stream.encode(frame):output.mux(packet)
 for packet in stream.encode():output.mux(packet)
 output.close()
 inp=av.open(str(outdir/'comparison.mp4'));count=sum(1 for _ in inp.decode(video=0));assert count==n;inp.close()
 rec={'task_id':sid,'roles':ROLES,'valid_frames':n,'fps':fps,'width':1920,'height':1232,'caption_height':24,'bottom_controls_padding':80,'screenshot_frame':shotframe,'screenshot_selection':'统一取有效时长中点，同帧比较；动作偏移暂未测','full_decode_frames':count,'inputs':{r:{'job':jobs[r]['id'],'sha256':jobs[r]['sha256']} for r in ROLES},'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [outdir/'comparison.mp4',outdir/'same_frame.jpg']}}
 (outdir/'PRESENTATION.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2));print(sid,n,'done',flush=True)
