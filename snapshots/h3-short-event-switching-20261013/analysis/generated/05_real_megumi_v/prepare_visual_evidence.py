"""Local CPU-only derived evidence for one assigned case. Never writes raw inputs/outputs."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess, json, math, hashlib, time, sys
BASE=Path(__file__).resolve().parents[3]
DEST=Path(__file__).resolve().parent
CASE='05_real_megumi_v'
FF='/opt/homebrew/bin/ffmpeg'; FP='/opt/homebrew/bin/ffprobe'
FONT=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',18)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def data(path, vf, w, h):
 raw=subprocess.check_output([FF,'-v','error','-i',str(path),'-vf',vf,'-f','rawvideo','-pix_fmt','rgb24','-'])
 size=w*h*3
 assert len(raw)%size==0
 return [Image.frombytes('RGB',(w,h),raw[j:j+size]) for j in range(0,len(raw),size)]
def ready(run):
 p=BASE/'outputs'/f'{run}_00001_.mp4'; hp=BASE/'logs'/f'{run}_history.json'
 if not(p.exists() and hp.exists()):return None
 try:
  h=json.loads(hp.read_text())
  if 'outputs' not in h:h=next(iter(h.values()))
  if h['status']['status_str']!='success' or not h['status']['completed']:return None
  if not any(m[0]=='execution_success' for m in h['status']['messages']):return None
  if not any(item.get('filename')==p.name for item in h['outputs'].get('14',{}).get('images',[])):return None
  return p,hp,h
 except (ValueError,KeyError,StopIteration):return None
def render(run):
 found=ready(run)
 if not found:return False
 p,hp,h=found; sig=sha(p); folder=DEST/run;folder.mkdir(exist_ok=True)
 ledger=folder/'ledger.json'
 if ledger.exists() and json.loads(ledger.read_text()).get('sha256')==sig:return True
 probe=json.loads(subprocess.check_output([FP,'-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(p)]))['streams'][0]
 frames=data(p,'scale=400:224',400,224);n=len(frames);pages=[]
 for page in range(math.ceil(n/30)):
  ids=list(range(page*30,min(n,(page+1)*30)));im=Image.new('RGB',(2000,math.ceil(len(ids)/5)*252+32),'white');d=ImageDraw.Draw(im);d.text((4,5),run+' | every frame',font=FONT,fill='black')
  for j,i in enumerate(ids):
   x=j%5*400;y=j//5*252+32;im.paste(frames[i],(x,y));d.text((x+3,y+226),f'f{i:03d} | {i/24:.3f}s',font=FONT,fill='black')
  f=folder/f'all_p{page+1}.jpg';im.save(f,quality=96);pages.append(str(f))
 source=BASE/'inputs'/f'{CASE}.mp4';sf=data(source,'crop=450:400:500:100',450,400);of=data(p,'crop=450:400:500:100',450,400);dense=[]
 ids=list(range(43,min(74,n,len(sf))))
 for page in range(math.ceil(len(ids)/3)):
  nums=ids[page*3:page*3+3];im=Image.new('RGB',(900,len(nums)*428+30),'white');d=ImageDraw.Draw(im)
  for col,label in enumerate(['SOURCE',run]):d.text((col*450+3,4),label,font=FONT,fill='black')
  for row,i in enumerate(nums):
   for col,seq in enumerate([sf,of]):
    x=col*450;y=30+row*428;im.paste(seq[i],(x,y));d.text((x+3,y+402),f'f{i:03d} | {i/24:.3f}s',font=FONT,fill='black')
  f=folder/f'dense_p{page+1}.jpg';im.save(f,quality=97);dense.append(str(f))
 info={'run_id':run,'path':str(p),'sha256':sig,'history_path':str(hp),'history_sha256':sha(hp),'prompt_id':h['prompt'][1],'probe':probe,'decoded_frames':n,'framecount_mismatch':n!=141,'all_sheets':pages,'dense_pages':dense,'dense_window_half_open':[43,min(74,n,len(sf))],'dense_crop_xywh':[500,100,450,400],'source_sha256':sha(source),'same_frame_no_interpolation':True,'reviewed':False}
 ledger.write_text(json.dumps(info,indent=2)+'\n');print('READY_EVIDENCE',run,'frames',n,flush=True);return True
if __name__=='__main__':
 runs=[f'{CASE}_{x}_s{s}' for s in [1,2] for x in ['a','b']]
 if '--watch' not in sys.argv:
  for r in runs:render(r)
 else:
  deadline=time.monotonic()+180*60;done=set()
  while time.monotonic()<deadline:
   for r in runs:
    if r not in done and render(r):done.add(r)
   if len(done)==4:print('ALL_FOUR_READY',flush=True);break
   time.sleep(30)
  else:print('BOUNDED_WAIT_TIMEOUT',sorted(done),flush=True)
