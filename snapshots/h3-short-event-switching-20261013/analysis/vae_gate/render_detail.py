from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import subprocess,json,math,hashlib,sys
base=Path(__file__).resolve().parents[2];dest=Path(__file__).resolve().parent;font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',17)
settings={'05_real_megumi_v':([45,71],[500,100,450,400]),'06_anime_eye_insert':([35,74],[520,140,450,400]),'07_real_ary_v':([49,75],[510,0,600,530])}
for cid in (sys.argv[1:] or settings):
 window,crop=settings[cid];folder=dest/cid;folder.mkdir(exist_ok=True);paths={'SOURCE':base/'inputs'/f'{cid}.mp4','PREPARED':base/'outputs'/f'{cid}_actual_prepared_reference_00001_.mp4','VAE':base/'outputs'/f'{cid}_reference_vae_reconstruction_00001_.mp4'}
 roles=[r for r,p in paths.items() if p.exists()];signature=':'.join(hashlib.sha256(paths[r].read_bytes()).hexdigest() for r in roles);ledgerpath=folder/'detail_ledger.json'
 if ledgerpath.exists() and json.loads(ledgerpath.read_text()).get('signature')==signature:continue
 x,y,w,h=crop;pw,ph=450,400;frames={}
 for role in roles:
  raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(paths[role]),'-vf',f'crop={w}:{h}:{x}:{y},scale={pw}:{ph}','-f','rawvideo','-pix_fmt','rgb24','-']);s=pw*ph*3;frames[role]=[Image.frombytes('RGB',(pw,ph),raw[i*s:(i+1)*s]) for i in range(len(raw)//s)]
 ids=list(range(*window));pages=[]
 if len(roles)==1:
  for pg in range(math.ceil(len(ids)/20)):
   vals=ids[pg*20:(pg+1)*20];can=Image.new('RGB',(pw*4,math.ceil(len(vals)/4)*(ph+25)),'white');d=ImageDraw.Draw(can)
   for j,i in enumerate(vals):
    xx=j%4*pw;yy=j//4*(ph+25);can.paste(frames['SOURCE'][i],(xx,yy));d.text((xx+3,yy+ph),f'SOURCE f{i:03d} | {i/24:.3f}s',font=font,fill='black')
   p=folder/f'source_detail_p{pg+1}.jpg';can.save(p,quality=96);pages.append(str(p))
 else:
  for pg in range(math.ceil(len(ids)/3)):
   vals=ids[pg*3:(pg+1)*3];can=Image.new('RGB',(pw*len(roles),len(vals)*(ph+25)+30),'white');d=ImageDraw.Draw(can)
   for col,role in enumerate(roles):d.text((col*pw+3,5),role+' | same frame',font=font,fill='black')
   for row,i in enumerate(vals):
    for col,role in enumerate(roles):
     xx=col*pw;yy=30+row*(ph+25);can.paste(frames[role][i],(xx,yy));d.text((xx+3,yy+ph),f'f{i:03d} | {i/24:.3f}s',font=font,fill='black')
   p=folder/f'aligned_detail_p{pg+1}.jpg';can.save(p,quality=96);pages.append(str(p))
 ledgerpath.write_text(json.dumps({'signature':signature,'roles':roles,'window_half_open':window,'crop_xywh':crop,'panel_size':[pw,ph],'pages':pages,'no_temporal_interpolation':True,'no_enhancement':True,'same_frame_alignment':True},indent=2));print(cid,roles,'pages',len(pages),flush=True)
