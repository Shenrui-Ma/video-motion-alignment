from pathlib import Path
from fractions import Fraction
import subprocess,json,hashlib,io,time,math
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parent;B=R.parent;OUT=R/'selected';OUT.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
metadata={}
for kind in ['short','long']:
 p=B/f'h3-ivebench-next-candidates-20261018/metadata/ivebenchdb_prompt_{kind}.json'
 for x in json.loads(p.read_text()):metadata[x['src_video_name'][:-4]]=(x,str(p),sha(p))
rowspec=[('short_0362',B/'h3-ivebench-subject-candidates-r82-20261018/sources/short_0362.mp4',0,66),('long_0031',B/'h3-ivebench-next-candidates-20261018/sources/long_0031.mp4',0,149),('long_0091',B/'h3-timing-architecture-r2-20261016/audit/ive_geometry_action_sources_20261018/sources/long_0091.mp4',381,530),('long_0161',B/'h3-timing-architecture-r2-20261016/audit/ive_action_candidate_expansion_20261018/sources/long_0161.mp4',0,149)]
rows=[]
for sid,p,start,end in rowspec:
 d=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_streams','-of','json',str(p)]));s=d['streams'][0];tb=Fraction(s['time_base']);pts=[Fraction(x['best_effort_timestamp'])*tb for x in d['frames']];n=len(pts);startpts=pts[start];endpts=pts[end+1] if end+1<n else (int(s['start_pts'])+int(s['duration_ts']))*tb
 duration=endpts-startpts;valid=math.ceil(duration*24);total=5+17*math.ceil((valid-5)/17)
 mapping=[min(range(start,end+1),key=lambda k:(abs(pts[k]-startpts-Fraction(i,24)),k)) for i in range(valid)]+[end]*(total-valid)
 inds=sorted(set(round(start+i*(end-start)/23) for i in range(24)));target=OUT/f'{sid}_selected_contact.jpg'
 if not target.exists():
  vf='select='+ '+'.join('eq(n\\,'+str(i)+')' for i in inds)+',scale=384:216:force_original_aspect_ratio=decrease,pad=384:216:(ow-iw)/2:(oh-ih)/2:black,tile=4x6'
  raw=subprocess.check_output(['ffmpeg','-v','error','-threads','2','-i',str(p),'-vf',vf,'-vsync','0','-frames:v','1','-threads','1','-f','image2pipe','-c:v','png','pipe:1']);tiles=Image.open(io.BytesIO(raw)).convert('RGB');im=Image.new('RGB',(1536,1500),'black');draw=ImageDraw.Draw(im);font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',16)
  for j,i in enumerate(inds):
   x=j%4*384;y=j//4*250;im.paste(tiles.crop((x,j//4*216,x+384,j//4*216+216)),(x,y));draw.text((x+5,y+220),f'{sid} f{i} {float(pts[i]):.3f}s',font=font,fill='white')
  im.save(target,quality=89)
 official,mp,mh=metadata[sid]
 row={'source_id':sid,'pair_id':sid,'source':{'file':str(p),'sha256':sha(p),'bytes':p.stat().st_size,'frame_count':n,'original_size':[s['width'],s['height']],'fps_rational':s['avg_frame_rate'],'time_base':s['time_base'],'actual_pts_rational':[str(x) for x in pts],'actual_pts_s':[float(x) for x in pts]},'clip':{'start_frame':start,'end_frame_inclusive':end,'start_pts_rational':str(startpts),'end_pts_rational_inclusive':str(pts[end]),'end_exclusive_rational':str(endpts),'duration_rational':str(duration)},'input_protocol':{'h3_frame_count':total,'effective_frame_count':valid,'input_to_original_frame':mapping,'fps':24,'geometry':[1312,736],'content_rectangle_xywh':[16,8,1280,720]},'edit_prompt':official['edit_prompt'],'official_task':official,'metadata_evidence':{'path':mp,'sha256':mh},'reference_image_used':False,'evaluation_scope':'IVEBench完整短片探索' if sid.startswith('short') else 'IVEBench素材片段探索','source_review':{'path':str(target),'sha256':sha(target),'original_frames':inds,'coverage':'24 original source frames, source-only selection; all valid frames will be reviewed upon Native'}}
 rows.append(row);print(sid,valid,total,float(startpts),float(endpts),flush=True)
(R/'INPUT_PLAN_DRAFT.json').write_text(json.dumps({'schema':'ive-official-human-event-source-selection-v1','created_unix':time.time(),'status':'CPU_PLAN_NO_GPU_LAUNCH','pairs':rows},ensure_ascii=False,indent=2))
