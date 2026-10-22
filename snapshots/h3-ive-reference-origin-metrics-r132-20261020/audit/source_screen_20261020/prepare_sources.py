from pathlib import Path
import json,hashlib,urllib.request,os,subprocess
R=Path(__file__).resolve().parent;revision='1e6cb655c0a537f6093edcf18e2607fb03e76734';meta=Path('/Users/researcher/DevProjects/h3-ivebench-next-candidates-20261018/metadata');old=Path('/Users/researcher/DevProjects/h3-ivebench-expanded-metrics-r73-20261018/audit/benchmark_task_scope_20261018/source_candidate_review')
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();records=[]
for key,typ in [('long_0143','long'),('short_0144','short')]:
 mp=meta/f'ivebenchdb_prompt_{typ}.json';task=next(x for x in json.loads(mp.read_text())if x['src_video_name']==key+'.mp4');p=R/(key+'.mp4');url=f'https://huggingface.co/datasets/Coraxor/IVEBench/resolve/{revision}/ivebenchdb_mp4_{typ}/{key}.mp4';entry={}
 if key=='short_0144':
  source=old/'sources/short_0144.mp4';expected='5763a26cb4fd873708e9a8e1465f3b966f64e3c9cf269226a3d121501b3e67f0';assert h(source)==expected
  if not p.exists():os.link(source,p)
  entry={'origin':'existing_official_cache_hardlink','original_cache_path':str(source),'prior_review':{'file':str(old/'SOURCE_REVIEW.json'),'sha256':h(old/'SOURCE_REVIEW.json')}}
 else:
  req=urllib.request.Request(f'https://huggingface.co/api/datasets/Coraxor/IVEBench/paths-info/{revision}',data=json.dumps({'paths':[f'ivebenchdb_mp4_long/{key}.mp4'],'expand':True}).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=40)as f:info=json.load(f)
  (R/'long_0143_OFFICIAL_INFO.json').write_text(json.dumps(info,indent=2)+'\n');row=info[0];expected=row['lfs']['oid'];assert row['size']==104278142
  if not p.exists():
   with urllib.request.urlopen(url,timeout=40)as f, p.open('wb')as out:
    while b:=f.read(1048576):out.write(b)
  entry={'origin':'official_frozen_revision_download','official_file_info':{'file':str(R/'long_0143_OFFICIAL_INFO.json'),'sha256':h(R/'long_0143_OFFICIAL_INFO.json')}}
 assert h(p)==expected
 probe=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_streams','-of','json',str(p)],text=True));(R/f'{key}_PROBE.json').write_text(json.dumps(probe)+'\n');n=len(probe['frames']);indices=[round(i*(n-1)/23)for i in range(24)]
 frames=R/key;frames.mkdir(exist_ok=True);vf='+'.join(f'eq(n\\,{i})'for i in indices)
 subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(p),'-vf',f'select={vf},scale=640:-2','-fps_mode','vfr','-q:v','2',str(frames/'%03d.jpg')],check=True)
 records.append({'source_id':key,'official_task':task,'metadata':{'file':str(mp),'sha256':h(mp)},'source':{'file':str(p),'sha256':h(p),'bytes':p.stat().st_size},'url':url,'official_revision':revision,'frame_count':n,'fps':probe['streams'][0]['avg_frame_rate'],'sample_indices':indices,'sample_pts_s':[float(probe['frames'][i]['best_effort_timestamp_time'])for i in indices],**entry})
(R/'INPUTS.json').write_text(json.dumps({'scope':'source-only full-duration uniform24 snapshots; no generated output or inference queue','records':records},ensure_ascii=False,indent=2)+'\n');print(json.dumps([{'source_id':x['source_id'],'count':x['frame_count'],'fps':x['fps'],'bytes':x['source']['bytes']}for x in records]))
