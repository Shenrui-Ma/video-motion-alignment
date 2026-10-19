from pathlib import Path
import csv,json,hashlib,subprocess,io
from PIL import Image,ImageDraw,ImageFont,ImageOps
ROOT=Path(__file__).resolve().parent
OLD=Path('/Users/researcher/DevProjects/h3-ivebench-remaining-metrics-r69-20261018/audit/flex_official_inventory/FIXED_8_CANDIDATES.json')
ASSETS=Path('/Users/researcher/DevProjects/h3-flexiact-expanded-selection-20261018')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=json.loads(OLD.read_text())['pairs']
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',23)
small=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',19)
verified=[];sources={}
for p in rows:
 source=p['source'];t=Path(p['target']).stem
 for key in ['source_asset','target_asset']: assert sha(p[key]['path'])==p[key]['sha256']
 csvp=ASSETS/'metadata'/('flexiact_hf__benchmark__captions__human__'+source+'__val_image.csv')
 official=list(csv.DictReader(csvp.open()))[p['csv_row_zero_based']]
 assert official['path']==p['target'] and official['caption']==p['official_caption']
 verified.append({'pair':source+'__'+t,'source_sha':p['source_asset']['sha256'],'target_sha':p['target_asset']['sha256'],'csv_path':str(csvp),'csv_sha':sha(csvp),'csv_row_zero_based':p['csv_row_zero_based'],'official_row_exact':True})
 if source in ['chest','crouch','rotate','fitness']: sources[source]=p['source_asset']
for name,asset in sources.items():
 cmd=['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate,avg_frame_rate,nb_frames:frame=best_effort_timestamp_time','-show_frames','-of','json',asset['path']]
 meta=json.loads(subprocess.check_output(cmd));stream=meta['streams'][0];pts=[float(f['best_effort_timestamp_time']) for f in meta['frames']]
 assert len(pts)==49 and stream['r_frame_rate']=='8/1'
 inds=list(range(0,49,4));canvas=Image.new('RGB',(1440,830),'black');draw=ImageDraw.Draw(canvas)
 draw.text((16,10),f'{name} | ORIGINAL source | 49 frames, 8 fps | samples every 0.5 s',font=font,fill='white')
 for i,n in enumerate(inds):
  raw=subprocess.check_output(['ffmpeg','-v','error','-i',asset['path'],'-vf',f'select=eq(n\\,{n})','-frames:v','1','-f','image2pipe','-vcodec','png','-threads','1','-'])
  im=Image.open(io.BytesIO(raw)).convert('RGB');im.thumbnail((352,224))
  x=(i%4)*360+(360-im.width)//2;y=48+(i//4)*194
  # Preserve full field of view and fit into 352x162, including original black borders.
  im=ImageOps.contain(im,(352,160));x=(i%4)*360+(360-im.width)//2
  canvas.paste(im,(x,y));draw.text(((i%4)*360+10,y+164),f'frame {n:02d} | {pts[n]:.3f}s',font=small,fill='white')
 path=ROOT/(name+'_source_13_times.png');canvas.save(path)
 sources[name]={'asset':asset,'stream':stream,'sample_indices':inds,'pts':pts,'sheet':str(path),'sheet_sha256':sha(path)}
remaining=[p for p in rows if p['source']+'__'+Path(p['target']).stem not in {'crouch__movie_man_5','one_leg__movie_man_9'}]
canvas=Image.new('RGB',(1560,960),'black');draw=ImageDraw.Draw(canvas)
for i,p in enumerate(remaining):
 im=Image.open(p['target_asset']['path']).convert('RGB');im=ImageOps.contain(im,(500,410));x=(i%3)*520+(520-im.width)//2;y=(i//3)*480+40
 canvas.paste(im,(x,y));draw.text(((i%3)*520+10,(i//3)*480+8),p['source']+' / '+Path(p['target']).stem,font=font,fill='white')
 draw.text(((i%3)*520+10,(i//3)*480+456),f'official CSV row {p["csv_row_zero_based"]+1}',font=small,fill='white')
canvas.save(ROOT/'remaining_6_target_images.png')
(ROOT/'SOURCE_SHEET_RECEIPT.json').write_text(json.dumps({'old_fixed8_sha':sha(OLD),'verified_official_rows':verified,'sources':sources,'target_gallery':str(ROOT/'remaining_6_target_images.png'),'GPU_started':False},indent=2)+'\n')
print(json.dumps({'official_rows_verified':len(verified),'source_sheets':list(sources),'output':str(ROOT)}))
