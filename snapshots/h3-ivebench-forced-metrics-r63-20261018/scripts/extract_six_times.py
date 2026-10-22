"""Six fixed original-video times; three columns with captions in the black band."""
import argparse,io,shutil,subprocess,json
from pathlib import Path
FRAMES=[0,12,24,36,48,60]

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--native',type=Path,required=True);p.add_argument('--forced',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--font',type=Path);p.add_argument('--ffmpeg',default=shutil.which('ffmpeg'));a=p.parse_args()
 from PIL import Image,ImageDraw,ImageFont
 fonts=[a.font] if a.font else [Path('/System/Library/Fonts/PingFang.ttc'),Path('/System/Library/Fonts/STHeiti Light.ttc'),Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
 font=next((f for f in fonts if f and f.is_file()),None)
 if font is None:raise ValueError('supply a Chinese font using --font')
 inputs=[a.source,a.native,a.forced]
 if not all(f.is_file() for f in inputs):raise ValueError('three completed valid-prefix videos required')
 W,H,B=640,360,48;canvas=Image.new('RGB',(W*3,(H+B)*6),'black');draw=ImageDraw.Draw(canvas);small=ImageFont.truetype(str(font),20)
 labels=['1.参考视频','2.编辑后视频','3.编辑＋时序引导后视频']
 for row,frame in enumerate(FRAMES):
  for col,video in enumerate(inputs):
   cmd=[a.ffmpeg,'-v','error','-nostdin','-threads','1','-i',str(video),'-vf',f'select=eq(n\\,{frame}),scale={W}:{H}:flags=lanczos','-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','-']
   data=subprocess.check_output(cmd,timeout=60);im=Image.open(io.BytesIO(data)).convert('RGB');canvas.paste(im,(col*W,row*(H+B)))
   label=labels[col];bbox=draw.textbbox((0,0),label,font=small);x=col*W+(W-(bbox[2]-bbox[0]))/2
   draw.text((x,row*(H+B)+H+12),label,font=small,fill='white')
  draw.text((8,row*(H+B)+H+12),f'{frame/24:.1f}s',font=small,fill='#bcbcbc')
 a.output.parent.mkdir(parents=True,exist_ok=True)
 if a.output.exists():raise FileExistsError('preserve prior figure')
 canvas.save(a.output);a.output.with_suffix('.json').write_text(json.dumps({'original_frame_indices':FRAMES,'seconds':[i/24 for i in FRAMES],'fps':24,'columns':[str(p) for p in inputs],'time_shift_applied':0,'figure':str(a.output.resolve())},indent=2)+'\n')
 print(a.output.resolve())
if __name__=='__main__':main()
