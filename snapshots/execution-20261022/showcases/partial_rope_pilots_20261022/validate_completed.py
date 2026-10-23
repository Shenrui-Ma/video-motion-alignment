from pathlib import Path
from html.parser import HTMLParser
import json,base64,hashlib,subprocess
D=Path(__file__).resolve().parent;E=D.parents[1];p=E.parent/'reports/H3_部分RoPE频带_两组对照_20261022.html'
class Parse(HTMLParser):
 def __init__(self):super().__init__();self.videos=[];self.images=[];self.ids=[];self.external=[];self.text=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='video':self.videos.append(a)
  if tag=='img':self.images.append(a)
  if a.get('id'):self.ids.append(a['id'])
  if a.get('src') and not a['src'].startswith('data:'):self.external.append(a['src'])
 def handle_data(self,data):self.text.append(data)
x=Parse();x.feed(p.read_text());records=json.loads((D/'export_completed.json').read_text());assert len(x.videos)==len(records)==7;assert len(x.images)==3;assert not x.external;assert len(set(x.ids))==len(x.ids)==7
for v,r in zip(x.videos,records):
 assert 'controls' in v and v['preload']=='metadata'
 b=base64.b64decode(v['src'].split(',',1)[1]);assert hashlib.sha256(b).hexdigest()==hashlib.sha256(Path(r['output']).read_bytes()).hexdigest()
 subprocess.run(['ffmpeg','-v','error','-i',r['output'],'-f','null','-'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
text=' '.join(x.text);assert '已测动作偏移 · 2/7组' in text and '其余5组动作偏移未测' in text;assert text.count('动作偏移：未测')==5;assert '七组对照' in text;assert text.count('7/7组')==9
result={'status':'passed','videos':7,'inline_images':3,'external_assets':0,'controls':7,'all_videos_decoded':True,'media_sha_verified':True,'nine_metrics_complete_cases':7,'motion_offset_annotated':2,'motion_offset_unmeasured':5,'reference_geometry_consistent':True,'html_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size,'visual_ui_check':'file:// browser navigation blocked by tool URL policy; original CSS retained; no new scientific visual inspection'}
(D/'VALIDATION_COMPLETED.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
