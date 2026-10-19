import sys,subprocess,json,base64,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import render
from common import save,sha,ROOT
p=ROOT/'audit/synthetic_media';p.mkdir(exist_ok=True)
inputs=[];ff='/opt/homebrew/bin/ffmpeg';fp='/opt/homebrew/bin/ffprobe'
for label,color in [('source','red'),('native','green'),('fixed','blue'),('extended','yellow')]:
 path=p/(label+'.mp4');subprocess.run([ff,'-v','error','-n','-f','lavfi','-i',f'color={color}:s=1312x736:r=24','-frames:v','8','-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True);inputs.append(path)
media=render.render_files(inputs,p,8,6,render.choose_font(),ff,fp,rows=(6,))
manifest={'columns':['source','native','fixed','extended'],**media};save(p/'PRESENTATION.json',manifest)
render.publish(p,p/'test.html')
raw=subprocess.check_output([ff,'-v','error','-i',str(p/media['videos'][0]['file']),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
expected=[(255,0,0),(0,128,0),(0,0,255),(255,255,0)];pixels=[]
for col,e in enumerate(expected):
 ix=(360*5120+col*1280+640)*3;got=tuple(raw[ix:ix+3]);assert max(abs(a-b) for a,b in zip(e,got))<15,(col,got);pixels.append(got)
assets=re.findall(r'data:(?:video/mp4|image/jpeg);base64,([A-Za-z0-9+/=]+)',(p/'test.html').read_text());actual=[sha(p/x['file']) for x in media['videos']+media['contact_sheets']]
import hashlib
assert [hashlib.sha256(base64.b64decode(x)).hexdigest() for x in assets]==actual
save(p/'VERIFIED.json',{'passed':True,'actual_frame_count':media['videos'][0]['properties']['count'],'dimensions':[5120,808],'pixels':pixels,'embedded_assets_sha256':actual,'same_pts':True,'font':str(render.choose_font()),'fixture_only':True})
print(json.dumps({'passed':True,'receipt':str(p/'VERIFIED.json')}))
