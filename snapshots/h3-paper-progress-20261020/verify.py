"""Verify offline report bindings, markup, local media and script syntax."""
from pathlib import Path
from html.parser import HTMLParser
import base64, hashlib, json, re, subprocess, tempfile, xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
class Report(HTMLParser):
    def __init__(self):
        super().__init__();self.resources=[];self.ids=[];self.links=[];self.svg=0;self.scripts=[];self.in_script=False
    def handle_starttag(self,t,attrs):
        a=dict(attrs)
        if 'id' in a and t!='marker':self.ids.append(a['id'])
        if t=='a':self.links.append(a.get('href',''))
        for k in ('src','poster'):
            if a.get(k):self.resources.append((t,k,a[k]))
        if t=='svg':self.svg+=1
        if t=='script':self.in_script=True
    def handle_endtag(self,t):
        if t=='script':self.in_script=False
    def handle_data(self,s):
        if self.in_script:self.scripts.append(s)

def main():
    text=(ROOT/'index.html').read_text();p=Report();p.feed(text)
    receipt=json.loads((ROOT/'evidence/BUILD_RECEIPT.json').read_text())
    assert Path(receipt['output']).read_bytes()==(ROOT/'index.html').read_bytes()
    assert '@@' not in text and len(p.ids)==len(set(p.ids))
    assert len(re.findall(r'<video\b', text))==8
    assert '角色替换：更换随机种子' not in text and '相邻时间特征匹配</h3><span>IVEBench' not in text
    assert p.svg==9
    assert all(not x.startswith('#') or x[1:] in p.ids for x in p.links)
    assert all(v.startswith('data:') for _,_,v in p.resources)
    resources=[];checked=set()
    with tempfile.TemporaryDirectory(prefix='h3-paper-verify-') as tmp:
        for tag,attr,value in p.resources:
            header,payload=value.split(',',1);data=base64.b64decode(payload,validate=True)
            digest=hashlib.sha256(data).hexdigest()
            if digest in checked:continue
            checked.add(digest);row={'kind':tag,'sha256':digest,'bytes':len(data)}
            if 'video/mp4' in header:
                file=Path(tmp)/(digest+'.mp4');file.write_bytes(data)
                probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=codec_type,width,height,nb_frames,r_frame_rate:format=duration','-of','json',str(file)]))
                streams=[s for s in probe['streams'] if s['codec_type']=='video'];assert len(streams)==1 and int(streams[0]['nb_frames'])>90
                row['probe']=probe
            else:
                from PIL import Image
                from io import BytesIO
                image=Image.open(BytesIO(data));image.verify();row['image_size']=image.size
            resources.append(row)
        script=Path(tmp)/'inline.js';script.write_text('\n'.join(p.scripts))
        subprocess.run(['/Users/researcher/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node','--check',str(script)],check=True)
    for svg in (ROOT/'assets').glob('*.svg'): ET.fromstring(svg.read_text())
    from build import sha
    for path,digest in receipt['evidence'].items():assert sha(path)==digest,path
    assert all(x in text for x in ['2.2　参考视频 Attention','2.3　基于预测视频','3.5　自动决策','4　结论','0.802678','0.857115','0.877733','0.862660','112 版本','0.800240','UNKNOWN','FlexiAct 官方 MF','25–30 帧','0.879379','0.803720','RefGAP','RefDrop','Vidu S2-Editing','Wan-Animate-2','log Z'])
    result={'passed':True,'file_sha256':hashlib.sha256(text.encode()).hexdigest(),'offline_resources':True,'unique_resources':resources,'inline_figures':p.svg,'JavaScript_syntax':'pass','evidence_files_verified':len(receipt['evidence']),'HTML_browser_render':'not performed; local file browser access restricted','scientific_SVGs':'standalone figures visually reviewed: original seven via sharp; aligned RoPE and reference branch via QuickLook'}
    (ROOT/'evidence/VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='unique_resources'},ensure_ascii=False))
if __name__=='__main__':main()
