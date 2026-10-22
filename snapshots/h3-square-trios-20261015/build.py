from pathlib import Path
import json, subprocess, hashlib
from PIL import Image, ImageDraw, ImageFont

ROOT=Path('/Users/researcher/DevProjects/h3-square-trios-20261015')
DOWNLOADS=Path('/Users/researcher/Downloads')
SOURCE=DOWNLOADS/'H3_四组完整原视频_Musk_Sam_20261015'
OLD=DOWNLOADS/'H3_四组完整版横向对比_Musk_Sam_20261015'
old_manifest=json.loads((OLD/'manifest.json').read_text())
FONT=old_manifest['caption_style']['font']['path']
SIDE=736
FOOTER=88
LABELS=['1.参考视频','2.编辑后视频','3.编辑＋短时动作三倍加权后视频']
GROUPS=['01_Musk_真人书记舞','02_Musk_床边舞','03_Sam_真人书记舞','04_Sam_床边舞']
NAMES=['1_参考原视频.mp4','2_编辑后视频_未加权.mp4','3_编辑后视频_短时动作三倍加权.mp4']
font=ImageFont.truetype(FONT,30,index=3)
band=Image.new('RGB',(SIDE*3,FOOTER),'black')
draw=ImageDraw.Draw(band)
draw.text((24,FOOTER/2),'角色替换',font=font,fill='white',anchor='lm')
for i,label in enumerate(LABELS):
    assert draw.textlength(label,font=font)<SIDE-32
    draw.text(((i+.5)*SIDE,FOOTER/2),label,font=font,fill='white',anchor='mm')
band.save(ROOT/'caption_band.png')
records=[]
for group in GROUPS:
    # A shared fixed crop for every column and every frame of a group.
    # The Megumi source contains pre-existing 72px top/bottom letterboxing.
    crop=(360,72,592,592) if '书记' in group else (336,0,736,736)
    x,y,w,h=crop
    inputs=[SOURCE/group/n for n in NAMES]
    output=DOWNLOADS/(group+'_1比1画面_三列横向对比.mp4')
    filters=[]
    for i in range(3):
        filters.append(f'[{i}:v]setpts=PTS-STARTPTS,crop={w}:{h}:{x}:{y},scale={SIDE}:{SIDE}:flags=lanczos,setsar=1[v{i}]')
    filters += ['[v0][v1][v2]hstack=inputs=3[top]', '[3:v]setsar=1[cap]', '[top][cap]vstack=inputs=2:shortest=1,format=yuv420p[out]']
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y']
    for p in inputs:cmd+=['-i',str(p)]
    cmd+=['-loop','1','-framerate','24','-i',str(ROOT/'caption_band.png'),'-filter_complex_threads','2','-filter_complex',';'.join(filters),'-map','[out]','-an','-frames:v','141','-fps_mode','passthrough','-c:v','libx264','-threads','4','-preset','medium','-crf','18','-movflags','+faststart','-metadata','comment=AI identity replacement comparison; reference / unweighted edit / short-event reference weight x3.',str(output)]
    (ROOT/(group+'_command.json')).write_text(json.dumps(cmd,ensure_ascii=False,indent=2))
    subprocess.run(cmd,check=True)
    preview=ROOT/'qa'/(group+'_frame056.png')
    subprocess.run(['ffmpeg','-v','error','-i',str(output),'-vf',r'select=eq(n\,56)','-frames:v','1','-y',str(preview)],check=True)
    montage=ROOT/'qa'/(group+'_timeline.jpg')
    subprocess.run(['ffmpeg','-v','error','-i',str(output),'-vf','fps=1,scale=1104:412,tile=1x6','-frames:v','1','-y',str(montage)],check=True)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_entries','stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,nb_read_frames,duration,pix_fmt,sample_aspect_ratio:format=duration,size','-of','json',str(output)]))
    stream=probe['streams'][0]
    assert (stream['width'],stream['height'])==(2208,824)
    assert int(stream['nb_read_frames'])==141 and stream['avg_frame_rate']=='24/1'
    assert abs(float(stream['duration'])-5.875)<.00001
    subprocess.run(['ffmpeg','-v','error','-i',str(output),'-f','null','-'],check=True)
    records.append({'group':group,'inputs':[str(p) for p in inputs],'crop_xywh_all_columns':crop,'square_panel':SIDE,'caption_height':FOOTER,'caption_labels':LABELS,'legend':'角色替换','output':str(output),'probe':probe,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'preview':str(preview),'timeline':str(montage)})
    print(json.dumps({'completed':group,'output':str(output),'duration':stream['duration'],'frames':stream['nb_read_frames']},ensure_ascii=False),flush=True)
(ROOT/'manifest.json').write_text(json.dumps({'videos':records,'alignment':'Original frame 0–140, same index across columns, no retiming or interpolation; fixed common crop per group.','method':'Crop each native video to a square, scale equally to 736px, horizontal concatenation, black 88px footer with burned-in Chinese captions.'},ensure_ascii=False,indent=2))
