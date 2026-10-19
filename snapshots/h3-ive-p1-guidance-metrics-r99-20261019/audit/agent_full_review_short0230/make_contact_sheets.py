from pathlib import Path
import subprocess,json,hashlib,math
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;INC=ROOT/'incoming/short_0230'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
gate=read(INC/'PAIR_RUNTIME_GATE.json');collection=read(INC/'COLLECTION.json');assert gate['passed'] and all(gate['checks'].values()) and gate['valid_frames']==86
for name,digest in collection['files'].items():assert sha(INC/name)==digest,name
for key in ['native','forced']:assert sha(INC/(key+'.mp4'))==gate['runs'][key]['video']['sha256']
font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',17)
W,H,N=480,270,86;allframes={};info={}
for name in ['source','native','forced']:
 p=INC/(name+'.mp4');probe=read(INC/'COLLECTION.json')
 q=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(p)]))
 st=q['streams'][0];assert (st['width'],st['height'],st['avg_frame_rate'])==(1312,736,'24/1');assert len(q['frames'])==90
 times=[float(f['best_effort_timestamp_time']) for f in q['frames']];assert all(abs(x-i/24)<1e-6 for i,x in enumerate(times))
 raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',str(p),'-an','-vf',f'crop=1280:720:16:8,scale={W}:{H}:flags=lanczos','-frames:v',str(N),'-threads','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
 size=W*H*3;assert len(raw)==N*size
 allframes[name]=[Image.frombytes('RGB',(W,H),raw[i*size:(i+1)*size]) for i in range(N)];info[name]={'file':str(p),'sha256':sha(p),'all90times_validated':True,'reviewed_frame_domain':[0,85],'crop_xywh':[16,8,1280,720]}
pages=[]
for start in range(0,N,6):
 stop=min(start+6,N);im=Image.new('RGB',(W*3,(H+28)*(stop-start)+30),'#0c0d10');d=ImageDraw.Draw(im)
 for col,label in enumerate(['SOURCE','ORDINARY P1','FIXED GUIDANCE 6..14']):d.text((col*W+8,5),label,font=font,fill='white')
 for row,i in enumerate(range(start,stop)):
  y=30+row*(H+28);d.text((8,y+3),f'Frame {i:03d} | {i/24:.3f} s',font=font,fill='#eadca1')
  for col,key in enumerate(['source','native','forced']):im.paste(allframes[key][i],(col*W,y+28))
 path=OUT/f'frames_{start:03d}-{stop-1:03d}.jpg';im.save(path,quality=94);pages.append({'file':str(path),'frames':list(range(start,stop)),'sha256':sha(path)})
(OUT/'MEDIA_BINDINGS.json').write_text(json.dumps({'gate_sha256':sha(INC/'PAIR_RUNTIME_GATE.json'),'collection_sha256':sha(INC/'COLLECTION.json'),'inputs':info,'pages':pages,'coverage':list(range(N)),'sampling':'every physical frame 0..85 at24fps, same indices, no retiming'},indent=2)+'\n')
print(json.dumps({'pages':len(pages),'frames':N,'output':str(OUT)}))
