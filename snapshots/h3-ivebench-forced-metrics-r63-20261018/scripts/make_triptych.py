"""Render matched physical frames in three horizontal columns with bottom captions."""
import argparse,shutil,subprocess,json
from pathlib import Path

def build(inputs,font,output,ffmpeg):
 texts=['1.参考视频','2.编辑后视频','3.编辑＋时序引导后视频'];filters=[]
 for i,text in enumerate(texts):
  filters.append(f'[{i}:v]setsar=1,pad=iw:ih+88:0:0:black,drawtext=fontfile={font}:text={text}:fontcolor=white:fontsize=32:x=(w-text_w)/2:y=h-58[v{i}]')
 filters.append('[v0][v1][v2]hstack=inputs=3:shortest=1[out]')
 cmd=[ffmpeg,'-v','error','-nostdin','-n']
 for f in inputs:cmd+=['-threads','2','-i',str(f)]
 cmd+=['-filter_complex',';'.join(filters),'-map','[out]','-an','-vsync','0','-c:v','libx264','-crf','17','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(output)]
 return cmd

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--native',type=Path,required=True);p.add_argument('--forced',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--font',type=Path);p.add_argument('--ffmpeg',default=shutil.which('ffmpeg'));p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
 fonts=[a.font] if a.font else [Path('/System/Library/Fonts/PingFang.ttc'),Path('/System/Library/Fonts/STHeiti Light.ttc'),Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
 font=next((f for f in fonts if f and f.is_file()),None)
 if font is None:raise ValueError('supply a Chinese font using --font')
 if not a.ffmpeg:raise ValueError('ffmpeg is required')
 inputs=[a.source,a.native,a.forced]
 if not all(f.is_file() for f in inputs):raise ValueError('three actual valid-prefix comparison videos required')
 # Equal resolution/count/PTS are validated by prepare_pair before these score views are released.
 cmd=build(inputs,str(font),a.output,a.ffmpeg)
 if a.prepare_only:print(json.dumps({'command':cmd,'captions_below_image':True,'layout':'three1280x720 columns plus88px black caption band','time':'same physical frame and24fps'}));return
 a.output.parent.mkdir(parents=True,exist_ok=True);subprocess.run(cmd,check=True,timeout=240)
 print(json.dumps({'output':str(a.output.resolve()),'columns':['参考视频','编辑后视频','编辑＋时序引导后视频']}))
if __name__=='__main__':main()
