"""Replace only the five technical SVGs in the latest manually edited report."""
from pathlib import Path
import hashlib,json,re,os
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parent
REPORT=Path('/Users/researcher/DevProjects/video-motion-alignment/reports/视频编辑中动作时间对齐-研究进展v1.html')
FILES=['01_denoising_architecture.svg','02_time_coordinates.svg','03_reference_attention.svg','05_bidirectional_attention.svg','06_auxiliary_phase.svg']
PAT=r'<svg\b.*?</svg>'
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def outside(s):return re.sub(PAT,'[TECHNICAL_FIGURE]',s,flags=re.S)
def abstract(s):return re.search(r'<section id="abstract".*?</section>',s,re.S).group()
class Assets(HTMLParser):
 def __init__(self):super().__init__();self.assets=[]
 def handle_starttag(self,t,a):
  attrs=dict(a)
  if t in ['img','video','source'] and attrs.get('src'):self.assets.append([t,sha(attrs['src'])])
def assets(s):p=Assets();p.feed(s);return p.assets

def main():
 original=REPORT.read_text(); parts=list(re.finditer(PAT,original,re.S));assert len(parts)==len(FILES)
 figures=[]; allids=[]
 for name in FILES:
  s=(ROOT/'redrawn'/name).read_text();tree=ET.fromstring(s)
  ids=re.findall(r'\bid="([^"]+)"',s);assert len(ids)==len(set(ids))
  allids+=ids
  for url in re.findall(r'url\(#([^\)]+)\)',s):assert url in ids,(name,url)
  assert '<script' not in s and 'http://' not in s.replace('http://www.w3.org/2000/svg','')
  assert 'https://' not in s
  figures.append(s.strip())
 assert len(allids)==len(set(allids)), 'Duplicate SVG IDs'
 modified=original
 for match,new in reversed(list(zip(parts,figures))):modified=modified[:match.start()]+new+modified[match.end():]
 assert outside(modified)==outside(original),'Unrequested content changes'
 assert abstract(modified)==abstract(original),'User abstract changed'
 assert assets(modified)==assets(original),'Media assets changed'
 # Store only the replaced SVG fragments, not another large media copy.
 recovery=ROOT/'pre_publish_svgs';recovery.mkdir(exist_ok=True)
 for i,m in enumerate(parts,1):(recovery/f'{i}.svg').write_text(m.group())
 stamp={'report':str(REPORT),'original_report_sha256':sha(original),'new_report_sha256':sha(modified),'non_svg_sha256':sha(outside(original)),'abstract_sha256':sha(abstract(original)),'media_assets':assets(original),'figures':[{'file':name,'sha256':sha(s)} for name,s in zip(FILES,figures)],'checks':{'svg_count':len(FILES),'svg_xml_valid':True,'unique_svg_ids':True,'prose_css_js_captions_unchanged':True,'live_abstract_unchanged':True,'all_media_unchanged':True,'measured_heatmap_removed_by_user_request':True},'source_renderer':'/Users/researcher/DevProjects/h3-method-options-20261020/build_figures.py:current_method'}
 assert REPORT.read_text()==original,'Report changed during figure replacement; rerun with live content'
 temp=REPORT.with_suffix('.figures-tmp.html');temp.write_text(modified)
 assert REPORT.read_text()==original,'Concurrent report edit detected'
 os.replace(temp,REPORT)
 final=REPORT.read_text();assert final==modified
 (ROOT/'PUBLICATION.json').write_text(json.dumps(stamp,ensure_ascii=False,indent=2))
 print(json.dumps({'report':str(REPORT),'bytes':REPORT.stat().st_size,'checks':stamp['checks']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
