from pathlib import Path
import json,hashlib,urllib.request,subprocess,os
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parent;B=Path('/Users/researcher/DevProjects');rev='1e6cb655c0a537f6093edcf18e2607fb03e76734'
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();rows=[]
infos=json.loads((R/'OFFICIAL_FILES_INFO.json').read_text());info={Path(r['path']).stem:r for r in infos}
inv=B/'h3-benchmark-all-results-showcase-20261018/inventory/ivebench.json';used={r['source_id'] for r in json.loads(inv.read_text())['items']}
assert sum(info[s]['size'] for s in ['long_0035','long_0075'])<150000000
for sid in ['long_0035','long_0075','short_0132']:
 assert sid not in used
 typ=sid.split('_')[0];mp=B/f'h3-ivebench-next-candidates-20261018/metadata/ivebenchdb_prompt_{typ}.json';task=next(r for r in json.loads(mp.read_text()) if r['src_video_name']==sid+'.mp4')
 p=R/(sid+'.mp4');url=f'https://huggingface.co/datasets/Coraxor/IVEBench/resolve/{rev}/ivebenchdb_mp4_{typ}/{sid}.mp4'
 if sid=='short_0132':
  cache=B/'h3-ivebench-subject-candidates-r82-20261018/sources'/p.name
  if not p.exists():os.link(cache,p)
  expected=h(cache);origin='existing_cache_hardlink'
 else:
  expected=info[sid]['lfs']['oid'];origin='fixed_official_revision_download'
  if not p.exists():
   with urllib.request.urlopen(url,timeout=40) as f,p.open('wb') as out:
    while chunk:=f.read(1048576):out.write(chunk)
 assert h(p)==expected
 probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(p)]));n=len(probe['frames']);inds=[round(i*(n-1)/23) for i in range(24)];pts=[float(f['best_effort_timestamp_time']) for f in probe['frames']]
 frames=R/sid;frames.mkdir(exist_ok=True)
 vf='+'.join(f'eq(n\\,{i})' for i in inds)
 subprocess.run(['/opt/homebrew/bin/ffmpeg','-y','-v','error','-threads','2','-i',str(p),'-vf',f'select={vf},scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2','-fps_mode','vfr','-q:v','3',str(frames/'%03d.jpg')],check=True)
 font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',17);sheets=[]
 for page in range(2):
  im=Image.new('RGB',(1440,1200),'black');d=ImageDraw.Draw(im)
  for j in range(12):
   k=page*12+j;x=(j%3)*480;y=(j//3)*300;im.paste(Image.open(frames/f'{k+1:03d}.jpg'),(x,y));d.text((x+5,y+274),f'{sid} f{inds[k]} t={pts[inds[k]]:.3f}s',fill='white',font=font)
  dst=R/f'{sid}_sheet{page+1}.jpg';im.save(dst,quality=88);sheets.append({'file':str(dst),'sha256':h(dst)})
 rows.append({'source_id':sid,'official_task':task,'source':{'file':str(p),'sha256':h(p),'bytes':p.stat().st_size},'metadata':{'file':str(mp),'sha256':h(mp)},'origin':origin,'official_url':url,'official_revision':rev,'frames':n,'fps':probe['streams'][0]['avg_frame_rate'],'sample_indices':inds,'sample_pts_s':[pts[i] for i in inds],'sheets':sheets});print(sid,n,flush=True)
(R/'INPUTS.json').write_text(json.dumps({'inventory':{'file':str(inv),'sha256':h(inv)},'source_only':True,'new_gpu_jobs':0,'downloaded_bytes':sum(info[s]['size'] for s in ['long_0035','long_0075']),'records':rows},ensure_ascii=False,indent=2)+'\n')
