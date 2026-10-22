"""Bounded CPU media preparation for the already selected IVE source."""
from pathlib import Path
from fractions import Fraction
import hashlib,json,os,subprocess,time
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parents[1]
S='short_0177';src=Path('/Users/researcher/DevProjects/h3-ivebench-subject-candidates-r82-20261018/sources/short_0177.mp4')
meta=Path('/Users/researcher/DevProjects/h3-ivebench-next-candidates-20261018/metadata/ivebenchdb_prompt_short.json')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
task=next(v for v in json.loads(meta.read_text()) if v['src_video_name']==S+'.mp4')
for d in ['inputs','design','audit/source_review']:(R/d).mkdir(exist_ok=True,parents=True)
orig=R/'inputs'/f'{S}_original.mp4'
if not orig.exists():os.link(src,orig)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(src)],text=True))
pts=[Fraction(f['best_effort_timestamp_time']) for f in probe['frames']]
assert len(pts)==62 and pts==[Fraction(i,25) for i in range(62)]
mapping=[min(range(62),key=lambda j:abs(pts[j]-Fraction(i,24))) for i in range(60)]+[61]*13
clip={'start_frame':0,'end_frame_inclusive':61,'start_pts_rational':'0','end_pts_rational_inclusive':'61/25','end_exclusive_rational':'62/25','duration_rational':'62/25'}
plan={'schema':'r131-source-input-plan-v1','source_id':S,'official_task':task,'source':{'file':str(src),'sha256':sha(src),'frame_count':62,'fps':'25/1'},'clip':clip,'geometry':[1312,736],'h3_frames':73,'valid_frames':60,'fps':24,'input_to_original_frame':mapping,'metadata_evidence':{'file':str(meta),'sha256':sha(meta)},'GPU_started':False}
put(R/'design/INPUT_PLAN.json',plan)
decode=['ffmpeg','-v','error','-threads','2','-i',str(src),'-an','-vf','scale=1280:720:flags=lanczos,pad=1312:736:16:8:black,setsar=1','-fps_mode','passthrough','-pix_fmt','yuv420p','-threads','2','-f','rawvideo','-']
raw=subprocess.check_output(decode);size=1312*736*3//2;assert len(raw)==size*62
frames=[raw[i*size:(i+1)*size] for i in range(62)];original_md5=[hashlib.md5(x).hexdigest() for x in frames]
video=R/'inputs'/f'{S}_video.mp4'
encode=['ffmpeg','-v','error','-nostdin','-n','-f','rawvideo','-pix_fmt','yuv420p','-s:v','1312x736','-r','24','-i','pipe:0','-an','-c:v','libx264','-crf','0','-preset','fast','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(video)]
if not video.exists():subprocess.run(encode,input=b''.join(frames[j] for j in mapping),check=True)
decoded=subprocess.check_output(['ffmpeg','-v','error','-i',str(video),'-an','-pix_fmt','yuv420p','-f','rawvideo','-']);assert len(decoded)==size*73
md5=[hashlib.md5(decoded[i*size:(i+1)*size]).hexdigest() for i in range(73)];assert md5==[original_md5[j] for j in mapping]
prov={'schema':'r122-source-only-media-provenance-v1','source_id':S,'selection_file':str(R/'design/INPUT_PLAN.json'),'selection_sha256':sha(R/'design/INPUT_PLAN.json'),'source_original_file':str(src),'source_sha256':sha(src),'video_file':str(video),'video_sha256':sha(video),'geometry':[1312,736],'content_rectangle_xywh':[16,8,1280,720],'frames':73,'effective_frame_count':60,'fps':24,'evaluate_indices':list(range(60)),'padding_indices':list(range(60,73)),'clip':clip,'input_to_original_frame':mapping,'original_pts_rational':[str(x) for x in pts],'original_pts':[float(x) for x in pts],'original_transformed_frame_md5':original_md5,'input_frame_md5':md5,'decoded_pixel_mapping_exact':True,'decode_command':decode,'encode_command':encode,'official_edit_prompt':task['edit_prompt'],'reference_images':[]}
put(R/'inputs'/f'{S}_provenance.json',prov)
rgb=subprocess.check_output(['ffmpeg','-v','error','-i',str(video),'-an','-vf','crop=1280:720:16:8,scale=384:216','-pix_fmt','rgb24','-f','rawvideo','-'])
pages=[]
for start in range(0,60,15):
 end=min(start+15,60);page=Image.new('RGB',(384*3,240*5),'black');draw=ImageDraw.Draw(page)
 for k,i in enumerate(range(start,end)):
  im=Image.frombytes('RGB',(384,216),rgb[i*384*216*3:(i+1)*384*216*3]);x=k%3*384;y=k//3*240;page.paste(im,(x,y));draw.text((x+4,y+219),f'prepared {i:03} | original {mapping[i]:03} | {i/24:.3f}s',fill='white')
 file=R/'audit/source_review'/f'frames_{start:03}_{end-1:03}.jpg';page.save(file,quality=90);pages.append({'file':str(file),'sha256':sha(file),'frames':[start,end-1]})
put(R/'audit/source_review/PAGES.json',{'pages':pages,'covered_frames':list(range(60)),'source_only':True,'video_sha256':sha(video)})
put(R/'audit/CPU_MEDIA_READY.json',{'passed':True,'source_id':S,'valid':60,'total':73,'pixel_mapping_exact':True,'video_sha256':sha(video),'provenance_sha256':sha(R/'inputs'/f'{S}_provenance.json'),'GPU_started':False})
print(json.dumps({'passed':True,'video_sha256':sha(video),'valid':60,'total':73}))
