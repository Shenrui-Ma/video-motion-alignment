from pathlib import Path
import subprocess,json,hashlib
from PIL import Image,ImageDraw
from fractions import Fraction
ROOT=Path('/Users/researcher/DevProjects');OUT=Path(__file__).parent
ids={'long_0031','long_0081','long_0091','short_0116','short_0161','short_0182','long_0035','long_0163','short_0362','short_0395'}
files={}
for s in subprocess.check_output(['rg','--files',str(ROOT)],text=True).splitlines():
 p=Path(s)
 if p.suffix=='.mp4' and p.stem in ids:files.setdefault(p.stem,p)
meta={Path(x['src_video_name']).stem:x for b in ('short','long') for x in json.loads((ROOT/'h3-ivebench-next-candidates-20261018/metadata'/f'ivebenchdb_prompt_{b}.json').read_text())}
manifest=[]
for s,p in sorted(files.items()):
 probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=nb_read_frames,avg_frame_rate','-of','json',str(p)]))['streams'][0]
 n=int(probe['nb_read_frames']);fps=float(Fraction(probe['avg_frame_rate']));ii=sorted(set(round(j*(n-1)/11) for j in range(12)))
 expr='+'.join('eq(n\\,'+str(i)+')' for i in ii)
 raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(p),'-vf',f'select={expr},scale=426:180:force_original_aspect_ratio=decrease,pad=426:180:(ow-iw)/2:(oh-ih)/2','-vsync','0','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
 size=426*180*3
 assert len(raw)==len(ii)*size,(s,len(raw),len(ii)*size)
 canvas=Image.new('RGB',(1280,4*210),(25,25,25));d=ImageDraw.Draw(canvas)
 for j,i in enumerate(ii):
  im=Image.frombytes('RGB',(426,180),raw[j*size:(j+1)*size])
  x=(j%3)*426;y=(j//3)*210;canvas.paste(im,(x,y+24));d.text((x+5,y+5),f'{s} f{i} t={i/fps:.3f}s',fill='white')
 jpg=OUT/(s+'.jpg');canvas.save(jpg,quality=88)
 manifest.append({'source_id':s,'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'frames':n,'fps':fps,'duration':n/fps,'review_indices':ii,'contact':str(jpg),'official_task':meta[s]})
(OUT/'SOURCE_INPUTS.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
for x in manifest:print(x['source_id'],x['duration'],x['frames'],x['official_task']['edit_prompt'])
