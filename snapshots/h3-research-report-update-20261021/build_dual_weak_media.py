from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import hashlib
import io
import json
import subprocess

ROOT = Path(__file__).resolve().parent / 'dual_vs_weak'
ROOT.mkdir(exist_ok=True)
BASE = Path('/Users/researcher/DevProjects')
inputs = [
    BASE/'h3-ive-prompt-envelope-metrics-r123-20261020/variants/full_context/inputs/short_0358_video.mp4',
    BASE/'h3-ive-prompt-envelope-metrics-r123-20261020/variants/full_context/incoming_pairs/short_0358/native.mp4',
    BASE/'h3-guidance-schedule-eval-r149-20261020/actual/short_0358/early/video.mp4',
    BASE/'h3-guidance-schedule-eval-r149-20261020/actual/short_0358/global_weak/video.mp4',
    BASE/'h3-reference-feedback-r151-20261021/cases/short_0358/output/r151_short_0358_seed2026101701_combined_00001_.mp4',
]
labels = ['1.参考视频', '2.普通编辑', '3.单向引导 · 第1–9步', '4.单向全程弱引导', '5.双向引导 · 第1–9步']
font = ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', 25)
coords = [(0,0), (640,0), (1280,0), (320,402), (960,402)]
caption = Image.new('RGBA', (1920,850), (0,0,0,0))
draw = ImageDraw.Draw(caption)
for label,(x,y) in zip(labels,coords):
    draw.text((x+320,y+380), label, font=font, fill='white', anchor='mm')
caption.save(ROOT/'captions.png')

filters=[]
for i in range(5):
    filters.append(f'[{i}:v]trim=start_frame=0:end_frame=105,setpts=PTS-STARTPTS,crop=1280:720:16:8,scale=640:360:flags=lanczos,setsar=1[v{i}]')
layout='|'.join(f'{x}_{y}' for x,y in coords)
filters.append(''.join(f'[v{i}]' for i in range(5))+f'xstack=inputs=5:layout={layout}:fill=black:shortest=1,pad=1920:850:0:0:black[grid]')
filters.append('[grid][5:v]overlay=0:0:shortest=1,format=yuv420p[out]')
cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-filter_complex_threads','2']
for p in inputs:
    assert p.is_file(),p
    cmd+=['-i',str(p)]
cmd+=['-loop','1','-framerate','24','-i',str(ROOT/'captions.png'),'-filter_complex',';'.join(filters),'-map','[out]','-frames:v','105','-an','-c:v','libx264','-preset','fast','-crf','20','-threads','4','-movflags','+faststart',str(ROOT/'drink_five_versions.mp4')]
subprocess.run(cmd,check=True)

# The still uses the identical source frame in all five columns.
frame=39
still=Image.new('RGB',(3200,410),'black')
sd=ImageDraw.Draw(still)
for i,p in enumerate(inputs):
    data=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(p),'-vf',f'select=eq(n\\,{frame}),crop=1280:720:16:8,scale=640:360:flags=lanczos','-frames:v','1','-f','image2pipe','-vcodec','png','-'],capture_output=True,check=True).stdout
    still.paste(Image.open(io.BytesIO(data)).convert('RGB'),(i*640,0))
    sd.text((i*640+320,382),labels[i],font=font,fill='white',anchor='mm')
still.save(ROOT/'drink_five_versions_frame039.jpg',quality=92)
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(ROOT/'drink_five_versions.mp4'),'-vf','select=eq(n\\,39)','-frames:v','1',str(ROOT/'video_preview_frame039.png')],check=True)
manifest={'source_files':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in inputs], 'labels':labels,'frame':frame,'fps':24,'valid_frames':105,'crop_xywh':[16,8,1280,720],'layout':'3 panels above, 2 centered below','video':str(ROOT/'drink_five_versions.mp4'),'still':str(ROOT/'drink_five_versions_frame039.jpg')}
(ROOT/'MEDIA_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print(json.dumps({'video':manifest['video'],'still':manifest['still'],'bytes':(ROOT/'drink_five_versions.mp4').stat().st_size},ensure_ascii=False))
