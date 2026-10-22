from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import subprocess,json,math,hashlib,sys
base=Path(__file__).resolve().parents[2];dest=Path(__file__).resolve().parent;ff='/opt/homebrew/bin/ffmpeg';fp='/opt/homebrew/bin/ffprobe';font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',18)
ids=['05_real_megumi_v','06_anime_eye_insert','07_real_ary_v']
for cid in (sys.argv[1:] or ids):
 folder=dest/cid;folder.mkdir(exist_ok=True)
 paths={'source':base/'inputs'/f'{cid}.mp4','prepared':base/'outputs'/f'{cid}_actual_prepared_reference_00001_.mp4','vae':base/'outputs'/f'{cid}_reference_vae_reconstruction_00001_.mp4'}
 for role,path in paths.items():
  if not path.is_file():continue
  hash_=hashlib.sha256(path.read_bytes()).hexdigest();old=folder/(role+'_ledger.json')
  if old.exists() and json.loads(old.read_text()).get('sha256')==hash_:continue
  probe=json.loads(subprocess.check_output([fp,'-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,nb_read_frames,duration','-of','json',str(path)]))['streams'][0]
  raw=subprocess.check_output([ff,'-v','error','-i',str(path),'-vf','scale=400:224','-f','rawvideo','-pix_fmt','rgb24','-']);s=400*224*3;n=len(raw)//s
  for page in range(math.ceil(n/30)):
   ids_page=list(range(page*30,min(n,(page+1)*30)));can=Image.new('RGB',(2000,math.ceil(len(ids_page)/5)*252+32),'white');draw=ImageDraw.Draw(can);draw.text((4,5),cid+' | '+role+' | every frame',font=font,fill='black')
   for j,i in enumerate(ids_page):
    x=j%5*400;y=j//5*252+32;can.paste(Image.frombytes('RGB',(400,224),raw[i*s:(i+1)*s]),(x,y));draw.text((x+3,y+226),f'f{i:03d} | {i/24:.3f}s',font=font,fill='black')
   can.save(folder/f'{role}_all_p{page+1}.jpg',quality=95)
  info={'path':str(path),'sha256':hash_,'probe':probe,'decoded_frames':n,'sheets':[str(folder/f'{role}_all_p{i}.jpg') for i in range(1,math.ceil(n/30)+1)]};old.write_text(json.dumps(info,indent=2));print(cid,role,n,flush=True)
