from pathlib import Path
import csv,hashlib,io,json,shutil,subprocess,time,urllib.request
from PIL import Image,ImageDraw,ImageFont
B=Path(__file__).resolve().parent
M=Path('/Users/researcher/DevProjects/h3-ivebench-body-candidates-20261018')
REV='1e6cb655c0a537f6093edcf18e2607fb03e76734'
IDS=['short_0362','short_0144','short_0166']
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
for n in ['sources','metadata','six_frames','audit']:(B/n).mkdir(exist_ok=True)
a=json.loads((M/'metadata/ivebenchdb_prompt_short.json').read_text());tasks=[next(x for x in a if x['src_video_name']==i+'.mp4') for i in IDS]
plan={'schema':'ive-source-only-review-v1','source_ids':IDS,'six_frame_rule':'round(i*(N-1)/5),i=0..5,original decoded physical indices','official_revision':REV,'official_tasks_verbatim':tasks,'generated_outputs_consulted':0,'inference_queued':False,'metadata_sha256':sha(M/'metadata/ivebenchdb_prompt_short.json'),'scope':'source-scene-preserving local edits; inspect visible action, occlusion and shot changes'}
if not (B/'PREFILTER.json').exists():save(B/'PREFILTER.json',plan)
else:assert json.loads((B/'PREFILTER.json').read_text())==plan
# Prior exclusion is imported as evidence, not reinterpreted as a fresh source selection.
oldpath=M/'CANDIDATES_MANIFEST.json';old=json.loads(oldpath.read_text())
def find(o):
 if isinstance(o,dict):
  if o.get('source_id')=='short_0395' and 'source_review' in o:return o
  for v in o.values():
   z=find(v)
   if z:return z
 elif isinstance(o,list):
  for v in o:
   z=find(v)
   if z:return z
oldrow=find(old);assert oldrow['source_review']['status']=='EXCLUDE'
save(B/'EXISTING_0395_EXCLUSION.json',{'original_manifest':str(oldpath),'original_manifest_sha256':sha(oldpath),'original_row':oldrow,'decision':'retain existing exclusion; no new interpretation'})
paths=['ivebenchdb_mp4_short/'+i+'.mp4' for i in IDS]
req=urllib.request.Request('https://huggingface.co/api/datasets/Coraxor/IVEBench/paths-info/'+REV,data=json.dumps({'paths':paths,'expand':True}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req,timeout=60) as f:info=json.load(f)
save(B/'metadata/OFFICIAL_FILES_INFO.json',info);assert {x['path'] for x in info}==set(paths) and sum(x['size'] for x in info)<100_000_000
records=[]
for sid in IDS:
 spec=next(x for x in info if x['path'].endswith('/'+sid+'.mp4'));dest=B/'sources'/(sid+'.mp4');url='https://huggingface.co/datasets/Coraxor/IVEBench/resolve/'+REV+'/'+spec['path'];start=time.monotonic()
 if not dest.exists():
  prior=Path('/Users/researcher/DevProjects/h3-ivebench-pilot-20261017/inputs_selection/candidate_sources')/(sid+'.mp4')
  if prior.exists():shutil.copyfile(prior,dest)
  else:
   with urllib.request.urlopen(url,timeout=120) as src,dest.with_suffix('.part').open('wb') as out:shutil.copyfileobj(src,out)
   dest.with_suffix('.part').rename(dest)
 assert dest.stat().st_size==spec['size'] and sha(dest)==spec['lfs']['oid']
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(dest)]));save(B/'audit'/(sid+'_probe.json'),probe)
 pts=[float(f['best_effort_timestamp_time']) for f in probe['frames']];assert len(pts)>5 and all(y>x for x,y in zip(pts,pts[1:]));v=probe['streams'][0];frames=[round(i*(len(pts)-1)/5) for i in range(6)]
 canvas=Image.new('RGB',(1920,780),'black');draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',20)
 for j,n in enumerate(frames):
  cmd=['ffmpeg','-v','error','-threads','1','-i',str(dest),'-map','0:v:0','-vf',f'select=eq(n\\,{n}),scale=640:360:force_original_aspect_ratio=decrease:flags=lanczos,pad=640:360:(ow-iw)/2:(oh-ih)/2:black','-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','-']
  img=Image.open(io.BytesIO(subprocess.check_output(cmd))).convert('RGB');x=j%3*640;y=j//3*390;canvas.paste(img,(x,y));draw.text((x+10,y+364),f'{sid}  frame {n}  {pts[n]:.3f}s',font=font,fill='white')
 out=B/'six_frames'/(sid+'.jpg');canvas.save(out,quality=94)
 # Raw pixel scene-difference trace is auxiliary evidence only, not an automatic cut label.
 cut=subprocess.run(['ffmpeg','-hide_banner','-nostats','-threads','1','-i',str(dest),'-map','0:v:0','-vf','select=gt(scene\\,0.25),showinfo','-an','-f','null','-'],capture_output=True,text=True,check=True)
 (B/'audit'/(sid+'_scene_candidates.log')).write_text(cut.stderr)
 records.append({'id':sid,'official_task':next(t for t in tasks if t['src_video_name']==sid+'.mp4'),'source':str(dest),'url':url,'source_sha256':sha(dest),'bytes':dest.stat().st_size,'geometry':[v['width'],v['height']],'frame_count':len(pts),'avg_frame_rate':v['avg_frame_rate'],'original_pts_s':pts,'six_frame_indices':frames,'six_frame_pts_s':[pts[i] for i in frames],'six_frame_contact_sheet':str(out),'contact_sheet_sha256':sha(out),'wall_seconds':time.monotonic()-start})
 save(B/'INPUT_RECORDS.json',records);print(sid,len(pts),v['avg_frame_rate'],dest.stat().st_size,flush=True)
print('COMPLETE',flush=True)
