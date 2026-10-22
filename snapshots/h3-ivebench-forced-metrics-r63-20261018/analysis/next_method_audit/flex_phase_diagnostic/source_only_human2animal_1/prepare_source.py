from pathlib import Path
import json,hashlib,subprocess,math
from PIL import Image,ImageFont,ImageDraw
r=Path(__file__).resolve().parent;frames=r/'frames';frames.mkdir(exist_ok=True)
src=Path('/Users/researcher/DevProjects/h3-flexiact-expanded-selection-20261018/official_assets/benchmark/reference_videos/human/human2animal_1.mp4')
prov=Path('/Users/researcher/DevProjects/h3-timing-flexiact-expanded-r66-20261018/inputs/source_human2animal_1_provenance.json')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=json.loads(prov.read_text());assert sha(src)==p['official_source']['official_lfs_sha256']==p['source_original_sha256']
q=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_streams','-show_entries','stream=width,height,nb_frames,avg_frame_rate,start_time,duration:frame=best_effort_timestamp_time','-of','json',str(src)]))
assert len(q['frames'])==49
assert q['streams'][0]['width']==720 and q['streams'][0]['height']==480 and q['streams'][0]['avg_frame_rate']=='8/1'
pts=[float(f['best_effort_timestamp_time']) for f in q['frames']];assert all(abs(t-i/8)<1e-7 for i,t in enumerate(pts))
subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-y','-i',str(src),'-map','0:v:0','-fps_mode','passthrough','-start_number','0',str(frames/'frame_%03d.png')],check=True)
imgs=sorted(frames.glob('frame_*.png'));assert len(imgs)==49 and [x.stem for x in imgs]==[f'frame_{i:03d}' for i in range(49)]
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',20)
def sheet(indices,cols,width,name):
 height=width*2//3;caption=32;rows=math.ceil(len(indices)/cols)
 out=Image.new('RGB',(cols*width,rows*(height+caption)),'black');d=ImageDraw.Draw(out)
 for k,i in enumerate(indices):
  x=(k%cols)*width;y=(k//cols)*(height+caption)
  im=Image.open(imgs[i]).convert('RGB');assert im.size==(720,480)
  out.paste(im.resize((width,height),Image.Resampling.LANCZOS),(x,y));d.text((x+8,y+height+5),f'Original {i:02d} | {pts[i]:.3f} s',font=font,fill='white')
 out.save(r/name)
sheet(list(range(49)),7,360,'all49.png')
sheet(list(range(16)),4,480,'frames00_15.png')
sheet(list(range(16,32)),4,480,'frames16_31.png')
sheet(list(range(32,49)),4,480,'frames32_48.png')
check={'passed':True,'scope':'source only; no generated result opened or used for selection in this task','source':{'file':str(src),'sha256':sha(src),'official_pinned_url':p['official_source']['pinned_url']},'provenance':{'file':str(prov),'sha256':sha(prov)},'probe':q,'checks':{'source_sha_matches_official_lfs_and_preparation':True,'all49_frames_present_once_in_all49_sheet':True,'pts_equal_original_index_over_8':True,'original_720x480_preserved_in_raw_png':True,'no_temporal_resampling':True},'frame_records':[{'original_index':i,'pts_seconds':pts[i],'prepared_index':3*i,'file':str(x.relative_to(r)),'sha256':sha(x),'decoded_rgb_sha256':hashlib.sha256(Image.open(x).convert('RGB').tobytes()).hexdigest()} for i,x in enumerate(imgs)]}
(r/'SOURCE_CHECK.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'passed':True,'frames':len(imgs),'sheets':['all49.png','frames00_15.png','frames16_31.png','frames32_48.png']}))
