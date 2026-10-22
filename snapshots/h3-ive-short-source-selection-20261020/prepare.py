from pathlib import Path
import subprocess,json,hashlib,io,time
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parent;B=R.parent
meta=B/'h3-ivebench-next-candidates-20261018/metadata/ivebenchdb_prompt_short.json'
records={x['src_video_name'][:-4]:x for x in json.loads(meta.read_text())}
inv=B/'h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json'
used={x['source_id'] for x in json.loads(inv.read_text())['items']}
ids=['short_0116','short_0161','short_0362','short_0220','short_0309','short_0394','short_0395','short_0068','short_0167','short_0177','short_0235','short_0120']
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=[]
for sid in ids:
 assert sid not in used
 p=B/'h3-ivebench-subject-candidates-r82-20261018/sources'/f'{sid}.mp4';assert p.exists()
 d=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,r_frame_rate,nb_frames:frame=best_effort_timestamp_time','-show_frames','-of','json',str(p)]));s=d['streams'][0];pts=[float(x['best_effort_timestamp_time']) for x in d['frames']];n=len(pts)
 inds=sorted(set(round(i*(n-1)/11) for i in range(12)))
 target=R/'contacts'/f'{sid}.jpg'
 if not target.exists():
  vf='select='+ '+'.join('eq(n\\,'+str(i)+')' for i in inds)+',scale=384:216:force_original_aspect_ratio=decrease,pad=384:216:(ow-iw)/2:(oh-ih)/2:black,tile=4x3'
  data=subprocess.check_output(['ffmpeg','-v','error','-threads','2','-i',str(p),'-vf',vf,'-vsync','0','-frames:v','1','-threads','1','-f','image2pipe','-c:v','png','pipe:1'])
  tiles=Image.open(io.BytesIO(data)).convert('RGB');im=Image.new('RGB',(1536,750),'black');draw=ImageDraw.Draw(im);font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',16)
  for j,i in enumerate(inds):
   x=j%4*384;y=j//4*250;im.paste(tiles.crop((x,j//4*216,x+384,j//4*216+216)),(x,y));draw.text((x+5,y+220),f'{sid} f{i} {pts[i]:.3f}s',font=font,fill='white')
  im.save(target,quality=88)
 row={'source_id':sid,'metadata':records[sid],'reference_image_used':False,'source_path':str(p),'source_sha256':sha(p),'frames':n,'fps_rational':s['avg_frame_rate'],'width':s['width'],'height':s['height'],'last_pts_s':pts[-1],'estimated_duration_s':pts[-1]+(pts[1]-pts[0]),'contact_path':str(target),'contact_sha256':sha(target),'viewed_frame_indices':inds,'viewed_pts_s':[pts[i] for i in inds]};rows.append(row);print(sid,n,s['avg_frame_rate'],flush=True)
(R/'CANDIDATES.json').write_text(json.dumps({'created_unix':time.time(),'inventory_path':str(inv),'inventory_sha256':sha(inv),'metadata_path':str(meta),'metadata_sha256':sha(meta),'scope':'Source-only 12-frame screen; no generated results used; raw cached bytes retained','candidates':rows},ensure_ascii=False,indent=2))
