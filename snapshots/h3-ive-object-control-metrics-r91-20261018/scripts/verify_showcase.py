"""Static embedded-byte verification; this does not certify browser layout."""
import argparse,base64,hashlib
from html.parser import HTMLParser
from common import *

class MediaParser(HTMLParser):
 def __init__(self):super().__init__();self.videos=[];self.images=[];self.external=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='video':self.videos.append(a)
  if tag=='img':self.images.append(a)
  for key in ('src','poster','href'):
   if key in a and not a[key].startswith(('data:','#')):self.external.append(a[key])

def validate_embedded(document,manifest):
 p=MediaParser();p.feed(document);require(not p.external,'external/local-only media reference found')
 require(len(p.videos)==manifest['embedded_video_count'],'embedded video count differs')
 video_hashes=[x['sha256'] for x in manifest['embedded_assets'] if x['role'] in ('full_valid','first2seconds')]
 images={x['sha256'] for x in manifest['embedded_assets'] if x['role'] in ('poster','six_times')}
 def digest(uri,prefix):
  require(uri.startswith('data:'+prefix) and ';base64,' in uri,'missing embedded media')
  return hashlib.sha256(base64.b64decode(uri.split(';base64,',1)[1],validate=True)).hexdigest()
 got=[]
 for a in p.videos:
  require('controls' in a and a.get('preload')=='none','video playback settings differ')
  got.append(digest(a['src'],'video/'));require(digest(a['poster'],'image/') in images,'poster hash differs')
 require(sorted(got)==sorted(video_hashes),'embedded video bytes differ')
 for a in p.images:require(digest(a['src'],'image/') in images,'embedded figure differs')
 return {'passed':True,'embedded_videos':len(p.videos),'embedded_figures':len(p.images),'external_urls':0,'UI_layout':'NOT_ASSESSED'}

def verify(path):
 p=Path(path);return validate_embedded(p.read_text(),read(p.with_suffix('.json')))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('html');a=p.parse_args();print(json.dumps(verify(a.html)))
