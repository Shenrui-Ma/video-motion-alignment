import base64,hashlib,json,subprocess
from html.parser import HTMLParser
from pathlib import Path
B=Path(__file__).resolve().parent
class Page(HTMLParser):
 def __init__(self):super().__init__();self.videos=[];self.images=[];self.srcs=[];self.scripts=[];self.in_script=False
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='video':self.videos.append(a)
  if 'src' in a:self.srcs.append(a['src'])
  if tag=='script':self.in_script=True
 def handle_endtag(self,tag):
  if tag=='script':self.in_script=False
 def handle_data(self,data):
  if self.in_script:self.scripts.append(data)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
d=json.loads((B/'DELIVERY.json').read_text());m=json.loads((B/'MEDIA_MANIFEST.json').read_text());h=Path(d['html']['file']);parser=Page();parser.feed(h.read_text());assert len(parser.videos)==5
assert all(x.startswith('data:') for x in parser.srcs)
for v,r in zip(parser.videos,m['cases']):
 p=Path(r['output']['file']);raw=base64.b64decode(v['src'].split(',',1)[1],validate=True)
 assert hashlib.sha256(raw).hexdigest()==sha(p)==r['output']['sha256']
 assert hashlib.sha256(base64.b64decode(v['poster'].split(',',1)[1],validate=True)).hexdigest()==r['poster']['sha256']
 assert r['presentation']['frames']==147 and r['probe']['nb_frames']=='147'
 assert r['probe']['duration']=='6.125000'
 for x in r['source_and_completed_outputs']+r['completion_evidence']:
  assert sha(Path(x['file']))==x['sha256']
 subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','2','-i',str(p),'-f','null','-'],capture_output=True,check=True,timeout=60)
script=B/'audit/page_script.js';script.write_text('\n'.join(parser.scripts));subprocess.run(['node','--check',str(script)],check=True,capture_output=True,timeout=10)
record={'pass':True,'video_count':5,'embedded_video_bytes_match_downloads':True,'embedded_posters_match':True,'external_src_dependencies':0,'every_video_full_decode_pass':True,'javascript_parse_pass':True,'presentation_frames_per_video':147,'presentation_duration_s':6.125,'input_and_completed_originals_frames':158,'native_completed':5,'auto_completed':1,'auto_ids':['chest'],'auto_chest_actual_interventions':0,'full158_showcase_archive':str(B/'archive158'),'browser_preview':'UNAVAILABLE: cua.createBrowserTab(iab) returned Browser is not available; cua.listBrowsers returned empty. No browser-policy fallback attempted.','html_sha256':sha(h)}
(B/'audit/VERIFICATION.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(json.dumps(record,ensure_ascii=False))
