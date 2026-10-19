#!/usr/bin/env python3
"""Independently decode embedded base64 and validate it against the source manifest."""
import argparse,base64,hashlib,json,mmap,re,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def h(data):return hashlib.sha256(data).hexdigest()
def run(manifest_path):
 m=json.loads(manifest_path.read_text());records=[];posters=[];refs=[]
 with open(m['output'],'rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as page:
  assert h(page)==m['output_sha256']
  patterns=list(re.finditer(rb'<source src="data:([^;]+);base64,([^"]+)"',page))
  assert len(patterns)==len(m['embedded_videos'])
  for match,expected in zip(patterns,m['embedded_videos']):
   raw=base64.b64decode(match.group(2),validate=True)
   assert h(raw)==expected['sha256'],expected['video_id']
   with tempfile.NamedTemporaryFile(suffix='.mp4') as tmp:
    tmp.write(raw);tmp.flush()
    p=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height,r_frame_rate,nb_frames:format=duration','-of','json',tmp.name],capture_output=True,text=True,check=True,timeout=60)
    info=json.loads(p.stdout);assert info.get('streams')
    subprocess.run(['ffmpeg','-v','error','-i',tmp.name,'-frames:v','1','-f','null','-'],capture_output=True,check=True,timeout=60)
   records.append({'video_id':expected['video_id'],'source_sha256':expected['sha256'],'embedded_sha256':h(raw),'decode_first_frame':'passed','probe':info})
  for match,expected in zip(re.finditer(rb'poster="data:image/jpeg;base64,([^"]+)"',page),m['embedded_videos']):
   value=h(base64.b64decode(match.group(1),validate=True));assert value==expected['poster_sha256'];posters.append(value)
  allowed_refs={item['media']['reference_image_path']['sha256'] for item in m['items'] if item.get('reference_image_used') is True}
  for match in re.finditer(rb'<img src="data:image/[^;]+;base64,([^"]+)"',page):
   value=h(base64.b64decode(match.group(1),validate=True));assert value in allowed_refs;refs.append(value)
  assert len(posters)==len(records)
  assert len(refs)==sum(i.get('reference_image_used') is True for i in m['items'])
  assert len(list(re.finditer(b'<article class="card"',page)))==m['display_count']
  assert len(list(re.finditer(b'preload="none"',page)))==len(records)
  assert not re.search(rb'(?:src|href)=["\'](?:https?://|file:|/Users/|/data[0-9]/)',page)
 result={'passed':True,'output':m['output'],'output_sha256':m['output_sha256'],'video_count':len(records),'poster_count':len(posters),'reference_image_count':len(refs),'cards':m['display_count'],'every_embedded_video_sha_matches':True,'every_embedded_video_first_frame_decoded':True,'external_media_dependencies':0,'videos':records,'browser_layout_assessment':'not_assessed; local browser disabled in Work settings'}
 (ROOT/'audit/EMBEDDED_MEDIA_VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps({k:v for k,v in result.items() if k!='videos'},ensure_ascii=False,indent=2))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,default=ROOT/'audit/SHOWCASE_MANIFEST.json');args=ap.parse_args();run(args.manifest)
