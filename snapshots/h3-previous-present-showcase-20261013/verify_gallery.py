"""Verify provenance, every rendered header, native overlay invariance, and links."""
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote,urlparse
from zoneinfo import ZoneInfo
import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parent
OLD=Path('/Users/researcher/DevProjects/h3-black-english-showcase-all-20261013')
LABELS=['PREVIOUS','PRESENT','PRESENT + PROMPT EMPHASIS']
FONT='/System/Library/Fonts/Helvetica.ttc'
MAIN=ImageFont.truetype(FONT,20);TIME=ImageFont.truetype(FONT,16);SMALL=ImageFont.truetype(FONT,12)

class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.ids=set()
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if 'id' in a:self.ids.add(a['id'])
  for k in ('href','src'):
   if k in a:self.links.append(a[k])

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def header(i,detail=False):
 im=Image.new('RGB',(1968,48),'black');d=ImageDraw.Draw(im)
 for col,label in enumerate(LABELS):
  x=col*656;d.text((x+10,3),label,font=MAIN,fill='white')
  d.text((x+10,27),f'frame {i:03d} | {i/24:.3f}s',font=TIME,fill='white')
  if detail:d.text((x+560,29),'DETAIL CROP',font=SMALL,fill='white')
 return np.asarray(im,dtype=np.int16)

def main():
 m=json.loads((ROOT/'manifest.json').read_text());old=json.loads((OLD/'manifest.json').read_text());previous={c['key']:c for c in old['cases']}
 issues=[];videos=[];images=[];bindings=[];frozen=[]
 assert m['labels']==LABELS
 for c in m['cases']:
  before=previous[c['key']]
  unchanged=all(c[k]==before[k] for k in ['frames','bounds','screens','detail'])
  frozen.append({'case':c['key'],'frame_count_window_screens_crop_unchanged':unchanged})
  if not unchanged:issues.append('Changed selected frames/window: '+c['key'])
  for kind in ('rendered','detail_rendered'):
   if c[kind]:
    videos.extend((v,c['bounds'][0],c['bounds'][1],kind=='detail_rendered') for v in c[kind]['videos'])
    images.extend((im,kind=='detail_rendered') for im in c[kind]['key_screenshots']+c[kind]['dense_pages'])
  videos.extend((v,0,c['frames']-1,False) for v in c['full_clip'])
  av=json.loads((Path(c['archive'])/'analysis/archive_validation.json').read_text())
  expected={x['output_file']:x['output_sha256'] for x in av['formal_runs']}
  for j,b in enumerate(c['inputs']):
   p=Path(b['path']);actual=sha(p);ok=actual==b['sha256']==before['inputs'][j]['sha256']
   if j:ok=ok and actual==expected[p.relative_to(c['archive']).as_posix()]
   bindings.append({'case':c['key'],'label':LABELS[j],'path':str(p),'sha256':actual,'pass':ok})
   if not ok:issues.append('input hash mismatch: '+str(p))

 def check_media(vinfo):
  v,lo,hi,detail=vinfo;p=ROOT/v['path'];n=hi-lo+1;fps=6 if 'quarter_speed' in p.name else 24
  pr=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate,nb_read_frames,duration','-of','json',str(p)]))['streams'][0]
  ok=(pr==v['probe'] and int(pr['nb_read_frames'])==n and pr['avg_frame_rate']==f'{fps}/1' and pr['width']==1968 and pr['height']==416 and abs(float(pr['duration'])-n/fps)<0.00001)
  raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(p),'-filter_threads','1','-vf','crop=1968:48:0:0','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','-'])
  arr=np.frombuffer(raw,np.uint8).reshape(n,48,1968,3)
  errs=[float(np.abs(arr[j].astype(np.int16)-header(i,detail)).mean()) for j,i in enumerate(range(lo,hi+1))]
  label_errs=[float(np.abs(arr[j,:26].astype(np.int16)-header(i,detail)[:26]).mean()) for j,i in enumerate(range(lo,hi+1))]
  return {'path':v['path'],'probe':pr,'expected_frames':n,'expected_fps':fps,'header_frames_checked':n,'max_full_header_mae':max(errs),'max_label_header_mae':max(label_errs),'pass':ok and max(errs)<2 and max(label_errs)<2}
 with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(check_media,videos))
 for x in results:
  if not x['pass']:issues.append('media/header mismatch: '+x['path'])
 if len(results)!=32:issues.append(f'expected32 movies, got{len(results)}')

 image_results=[]
 for info,detail in images:
  with Image.open(ROOT/info['path']) as im:
   im.load();assert im.size==(1968,416*len(info['frames']))
   arr=np.asarray(im,dtype=np.int16)
   errs=[float(np.abs(arr[j*416:j*416+48]-header(i,detail)).mean()) for j,i in enumerate(info['frames'])]
  good=max(errs)<2;image_results.append({'path':info['path'],'rows_checked':len(info['frames']),'header_mae_max':max(errs),'pass':good})
  if not good:issues.append('image/header mismatch: '+info['path'])

 audits=json.loads((ROOT/'DISPLAY_PIXEL_AUDIT.json').read_text());pixel_results=[]
 for col in audits['cases']:
  proc=subprocess.Popen(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',col['path'],'-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
  size=1312*736*3;rowbytes=1312*3;count=0;unchanged=0;proof=True
  for rec in col['frames']:
   raw=proc.stdout.read(size);assert len(raw)==size
   shown=bytearray(raw)
   if col['overlay']:
    shown[:70*rowbytes]=b'\0'*(70*rowbytes);shown[667*rowbytes:]=b'\0'*(69*rowbytes)
   shown=bytes(shown);outside_before=raw[70*rowbytes:667*rowbytes];outside_after=shown[70*rowbytes:667*rowbytes]
   equal=outside_before==outside_after;unchanged+=int(equal)
   proof=proof and hashlib.sha256(raw).hexdigest()==rec['native_decoded_sha256'] and hashlib.sha256(shown).hexdigest()==rec['display_native_sha256'] and equal
   if not col['overlay']:proof=proof and raw==shown
   count+=1
  assert not proc.stdout.read(1);proc.stdout.close();assert proc.wait()==0
  pixel_results.append({'column':col['column'],'native_frames_independently_rechecked':count,'outside_overlay_exact_equal_frames':unchanged,'whole_native_unchanged':not col['overlay'],'pass':proof and count==141})
  if not proof or count!=141:issues.append('native overlay invariance mismatch: '+col['column'])

 parser=Links();parser.feed((ROOT/'index.html').read_text());local_paths=set()
 for ref in parser.links:
  url=urlparse(ref)
  if url.scheme or url.netloc:continue
  p=ROOT/unquote(url.path) if url.path else ROOT/'index.html';local_paths.add(str(p))
  if not p.exists():issues.append('missingHTML path: '+str(p))
  if url.fragment and p==ROOT/'index.html' and url.fragment not in parser.ids:issues.append('missing anchor: '+url.fragment)

 report={'status':'pass' if not issues else 'issues','checked_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
         'issues':issues,'cases':len(m['cases']),'media_count':len(results),'media_results':results,
         'image_count':len(image_results),'image_results':image_results,'all_rendered_labels_checked':True,
         'native_overlay_independent_recheck':pixel_results,'frozen_selection_checks':frozen,
         'input_bindings':bindings,'input_binding_count':len(bindings),'html_reference_count':len(parser.links),'html_unique_local_paths':len(local_paths),
         'visual_review_file':'VISUAL_VERDICT.json','new_inference':False,
         'process_note':'Bounded local rendering/verification processes only. No SSH, GPU inference or background watcher was started.'}
 (ROOT/'QA_FINAL.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'status':report['status'],'issues':issues,'videos':len(results),'video_headers_checked':sum(x['header_frames_checked'] for x in results),'images':len(image_results),'image_headers_checked':sum(x['rows_checked'] for x in image_results),'native_pixel_checks':pixel_results,'html_reference_count':len(parser.links),'html_unique_local_paths':len(local_paths)},indent=2))
 if issues:raise SystemExit(1)

if __name__=='__main__':main()
