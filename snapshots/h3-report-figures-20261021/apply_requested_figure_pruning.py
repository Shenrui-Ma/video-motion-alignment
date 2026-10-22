from pathlib import Path
import re,json,hashlib,os,xml.etree.ElementTree as ET
from publish_figures import assets,abstract,sha
ROOT=Path(__file__).resolve().parent
report=Path('/Users/researcher/DevProjects/video-motion-alignment/reports/视频编辑中动作时间对齐-研究进展v1.html')
s=report.read_text();pat=r'<figure class="fig">.*?</figure>';items=list(re.finditer(pat,s,re.S));assert len(items)==6
out=s
for i,m in reversed(list(enumerate(items,1))):
 q=m.group()
 if i==2:
  svg=(ROOT/'redrawn/02_time_coordinates.svg').read_text().strip()
  q=re.sub(r'<svg\b.*?</svg>',lambda _:svg,q,flags=re.S)
 elif i==4:q=''
 elif i==5:q=q.replace('图 5  /','图 4  /').replace('图 5．','图 4．')
 elif i==6:q=q.replace('图 6  /','图 5  /').replace('图 6．','图 5．')
 out=out[:m.start()]+q+out[m.end():]
assert abstract(out)==abstract(s)
assert assets(out)==assets(s)
assert re.sub(pat,'',out,flags=re.S)==re.sub(pat,'',s,flags=re.S)
for t in ['网格与 token 数量为示意','当前覆盖：全部有效视频时间 bins','参考 Attention 的时间分布与同 bin 重分配']:
 assert t not in out,t
svgs=re.findall(r'<svg\b.*?</svg>',out,re.S);assert len(svgs)==5
for q in svgs:ET.fromstring(q)
caps=re.findall(r'<figure class="fig">.*?<figcaption>(.*?)</figcaption></figure>',out,re.S)
assert [re.match(r'图 (\d)',c).group(1) for c in caps]==['1','2','3','4','5']
assert report.read_text()==s
p=report.with_suffix('.figure-pruning-tmp.html');p.write_text(out);assert report.read_text()==s;os.replace(p,report)
record={'report':str(report),'old_sha256':sha(s),'new_sha256':sha(out),'removed':'Former Figure 4 measured Attention distribution','figure2_removed_lines':2,'figure_count':5,'captions':caps,'abstract_preserved':True,'body_and_media_preserved':True}
(ROOT/'FIGURE_PRUNING.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
state=Path('/Users/researcher/DevProjects/video-motion-alignment/.omx/state/h3-report-figures/ralph-progress.json')
state.write_text(json.dumps({'score':95,'verdict':'pass','category_match':True,'differences':[],'suggestions':[],'reasoning':'图2删除两句及背景条后结构清楚；旧图4已移除，后续图号连续为1至5。摘要、正文与媒体逐项一致。'},ensure_ascii=False,indent=2))
print(json.dumps(record,ensure_ascii=False,indent=2))
