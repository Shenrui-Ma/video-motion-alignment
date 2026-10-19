"""Supplement the frozen 49-source-time presentation with every generated valid frame."""
from pathlib import Path
import json,hashlib,subprocess
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parents[1];O=R/'audit/full147_review'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
c=read(R/'configs/contract.json');g=read(R/'incoming/PAIR_RUNTIME_GATE.json')
assert g['passed'] and all(g['checks'].values())
media={k:Path(c['media'][k]['file']) for k in ['source','native']};media['forced']=R/'incoming/forced.mp4'
for k in ['source','native']:assert sha(media[k])==c['media'][k]['sha256']
assert sha(media['forced'])==g['runs']['forced']['video']['sha256']
O.mkdir(exist_ok=True);W,H,N=480,320,147;frames={};bindings={}
for k,p in media.items():
 q=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(p)]))
 st=q['streams'][0];assert (st['width'],st['height'],st['avg_frame_rate'],len(q['frames']))==(1152,768,'24/1',158)
 assert all(abs(float(f['best_effort_timestamp_time'])-i/24)<1e-6 for i,f in enumerate(q['frames']))
 raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',str(p),'-an','-vf',f'scale={W}:{H}:flags=lanczos','-frames:v',str(N),'-threads','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
 size=W*H*3;assert len(raw)==N*size
 frames[k]=[Image.frombytes('RGB',(W,H),raw[i*size:(i+1)*size]) for i in range(N)]
 bindings[k]={'file':str(p),'sha256':sha(p),'158PTS_checked':True}
font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',17);pages=[]
for start in range(0,N,6):
 stop=min(start+6,N);im=Image.new('RGB',(3*W,(H+28)*(stop-start)+30),'#0c0d10');d=ImageDraw.Draw(im)
 for col,label in enumerate(['SOURCE','REPAIRED ORDINARY','FIXED GUIDANCE 6..14']):d.text((col*W+8,5),label,font=font,fill='white')
 for row,i in enumerate(range(start,stop)):
  y=30+row*(H+28);d.text((8,y+3),f'Frame {i:03d} | {i/24:.3f}s | source {i//3}',font=font,fill='#eadca1')
  for col,k in enumerate(['source','native','forced']):im.paste(frames[k][i],(col*W,y+28))
 p=O/f'frames_{start:03d}-{stop-1:03d}.jpg';im.save(p,quality=94);pages.append({'file':str(p),'frames':list(range(start,stop)),'sha256':sha(p)})
(O/'MEDIA_BINDINGS.json').write_text(json.dumps({'gate_sha256':sha(R/'incoming/PAIR_RUNTIME_GATE.json'),'media':bindings,'pages':pages,'coverage':list(range(N)),'source_original_rate':8,'source_motion_precision_seconds':.125,'generated_rate':24},indent=2)+'\n')
print(json.dumps({'pages':len(pages),'frames':N,'folder':str(O)}))
