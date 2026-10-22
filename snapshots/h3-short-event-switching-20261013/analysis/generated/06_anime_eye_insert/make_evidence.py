"""Local read-only source/outputs -> owned review derivatives, formal case06 only."""
from pathlib import Path
import subprocess, hashlib, json, argparse
from PIL import Image, ImageDraw, ImageFont
R=Path('/Users/researcher/DevProjects/h3-short-event-switching-20261013')
D=R/'analysis/generated/06_anime_eye_insert'
ap=argparse.ArgumentParser();ap.add_argument('--seed',type=int,choices=[1,2],required=True);args=ap.parse_args()
font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',18)
paths={'source':R/'inputs/06_anime_eye_insert.mp4','A':R/f'outputs/06_anime_eye_insert_a_s{args.seed}_00001_.mp4','B':R/f'outputs/06_anime_eye_insert_b_s{args.seed}_00001_.mp4'}
for p in paths.values():assert p.is_file(),p
out=D/f'seed{args.seed}';out.mkdir(exist_ok=True)
def decode(p,filter,w,h):
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-vf',filter,'-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','-'])
 size=w*h*3;assert len(raw)%size==0
 frames=[Image.frombytes('RGB',(w,h),raw[i:i+size]) for i in range(0,len(raw),size)]
 assert len(frames)==141,(p,len(frames));return frames
meta={'seed':args.seed,'frame_convention':'0-based24FPS','files':{},'all_frame_sheets':{},'dense_target_sheets':[],'no_interpolation_or_temporal_warp':True}
for label,p in paths.items():
 meta['files'][label]={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 if label=='source':continue
 frames=decode(p,'scale=492:276',492,276);sheets=[]
 for start in range(0,141,20):
  im=Image.new('RGB',(1968,1500),'white');dr=ImageDraw.Draw(im)
  for j,frame in enumerate(frames[start:start+20]):
   x=j%4*492;y=j//4*300;im.paste(frame,(x,y+24));dr.text((x+5,y+2),f'{label} seed{args.seed} f{start+j:03d} {(start+j)/24:.3f}s',font=font,fill='black')
  fn=out/f'{label}_allframes_p{start//20+1}.jpg';im.save(fn,quality=95);sheets.append(str(fn))
 meta['all_frame_sheets'][label]=sheets
roi={label:decode(p,'crop=650:550:340:65,scale=520:440',520,440) for label,p in paths.items()}
indices=list(range(32,53))
for begin in range(0,len(indices),3):
 group=indices[begin:begin+3];im=Image.new('RGB',(1560,len(group)*468),'white');dr=ImageDraw.Draw(im)
 for j,idx in enumerate(group):
  for k,label in enumerate(['source','A','B']):
   x=k*520;y=j*468;im.paste(roi[label][idx],(x,y+28));dr.text((x+5,y+3),f'{label} seed{args.seed} f{idx:03d} {idx/24:.3f}s',font=font,fill='black')
 fn=out/f'target_dense_p{begin//3+1}.jpg';im.save(fn,quality=97);meta['dense_target_sheets'].append(str(fn))
(out/'evidence_manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(meta,ensure_ascii=False))
