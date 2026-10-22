"""Local media, provenance and portable-link verification for this gallery."""
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote,urlparse
from zoneinfo import ZoneInfo
from PIL import Image

ROOT=Path(__file__).resolve().parent

class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.ids=set()
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if 'id' in attrs:self.ids.add(attrs['id'])
  for key in ('href','src'):
   if key in attrs:self.links.append(attrs[key])

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
 m=json.loads((ROOT/'manifest.json').read_text());issues=[];videos=[];bindings=[]
 for c in m['cases']:
  for kind in ('rendered','detail_rendered'):
   if c[kind]:videos.extend((v,c['bounds'][1]-c['bounds'][0]+1) for v in c[kind]['videos'])
  videos.extend((v,c['frames']) for v in c['full_clip'])
  av=json.loads((Path(c['archive'])/'analysis/archive_validation.json').read_text())
  expected={x['output_file']:x['output_sha256'] for x in av['formal_runs']}
  for j,b in enumerate(c['inputs']):
   p=Path(b['path']);actual=sha(p);ok=actual==b['sha256']
   if j:ok=ok and actual==expected[p.relative_to(c['archive']).as_posix()]
   bindings.append({'case':c['key'],'role':['SOURCE','A','B'][j],'path':str(p),'sha256':actual,'pass':ok})
   if not ok:issues.append('input hash mismatch: '+str(p))
 def check_media(vn):
  v,n=vn;p=ROOT/v['path'];fps=6 if 'quarter_speed' in p.name else 24
  pr=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames,duration','-of','json',str(p)]))['streams'][0]
  ok=(pr==v['probe'] and int(pr['nb_read_frames'])==n and pr['avg_frame_rate']==f'{fps}/1' and pr['width']==1968 and pr['height']==416 and abs(float(pr['duration'])-n/fps)<0.00001)
  return {'path':v['path'],'probe':pr,'expected_frames':n,'expected_fps':fps,'pass':ok}
 with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(check_media,videos))
 for x in results:
  if not x['pass']:issues.append('media mismatch: '+x['path'])
 if len(results)!=32:issues.append(f'expected32 movies, got{len(results)}')
 image_count=0
 for p in ROOT.rglob('*.jpg'):
  with Image.open(p) as im:im.load();assert im.width==1968 and im.height%416==0
  image_count+=1
 parser=Links();parser.feed((ROOT/'index.html').read_text());local_paths=set()
 for ref in parser.links:
  url=urlparse(ref)
  if url.scheme or url.netloc:continue
  p=ROOT/unquote(url.path) if url.path else ROOT/'index.html';local_paths.add(str(p))
  if not p.exists():issues.append('missingHTML path: '+str(p))
  if url.fragment and p==ROOT/'index.html' and url.fragment not in parser.ids:issues.append('missing anchor: '+url.fragment)
 imported=json.loads((ROOT/'IMPORTED_MEDIA_SHA256.json').read_text());preserved=0
 for rel,h in imported['files'].items():
  if sha(ROOT/rel)!=h or sha(Path(imported['source_root'])/rel)!=h:issues.append('imported asset mismatch: '+rel)
  else:preserved+=1
 report={'status':'pass' if not issues else 'issues','checked_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
         'issues':issues,'cases':len(m['cases']),'media_count':len(results),'media_results':results,
         'image_count_fully_decoded':image_count,'input_bindings':bindings,'input_binding_count':len(bindings),
         'html_reference_count':len(parser.links),'html_unique_local_paths':len(local_paths),
         'imported_assets_preserved':preserved,'new_inference':False,
         'visual_review_file':'VISUAL_VERDICT.json','review_limitations':'Key still images were visually inspected; all movies were frame-count decoded. No native-speed human viewing claimed.',
         'process_note':'Rendering and verification are bounded local child processes; rendering process returned exit0. No SSH, GPU inference, server or background watcher was started.'}
 (ROOT/'QA_FINAL.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ['status','issues','cases','media_count','image_count_fully_decoded','input_binding_count','html_reference_count','html_unique_local_paths','imported_assets_preserved']},indent=2))
 if issues:raise SystemExit(1)

if __name__=='__main__':main()
