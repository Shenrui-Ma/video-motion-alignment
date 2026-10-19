"""CPU-only synthetic media regression; all outputs explicitly labelled fixture."""
import json,subprocess,sys,tempfile
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from render import render_files,choose_font,media_info,check_time,publish
from common import save,sha
ff='/opt/homebrew/bin/ffmpeg';fp='/opt/homebrew/bin/ffprobe'
with tempfile.TemporaryDirectory(prefix='r98-media-fixture-') as temp:
 r=Path(temp);inputs=[]
 for i,color in enumerate(['red','green','blue']):
  p=r/f'{color}.mp4';subprocess.run([ff,'-v','error','-f','lavfi','-i',f'color={color}:size=96x64:rate=24','-frames:v','158','-an','-c:v','libx264','-pix_fmt','yuv420p','-threads','1',str(p)],check=True,timeout=60);inputs.append(p)
 out=r/'render';out.mkdir();report=render_files(inputs,out,choose_font(),ff,fp,width=96,height=64,sample_width=96)
 s=report['video']['properties'];check_time(s,147,288,152)
 raw=subprocess.check_output([ff,'-v','error','-i',str(out/report['video']['file']),'-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-'],timeout=30)
 def rgb(x,y):i=(y*288+x)*3;return tuple(raw[i:i+3])
 colors=[rgb(48,32),rgb(144,32),rgb(240,32)];assert all(v[i]>max(v[(i+1)%3],v[(i+2)%3])+70 for i,v in enumerate(colors)),colors
 assert rgb(5,90)==(0,0,0)
 assert [n for x in report['contact_sheets'] for n in x['original_frame_indices']]==list(range(49))
 for x in report['contact_sheets']:assert Image.open(out/x['file']).size==(288,770)
 save(out/'PRESENTATION.json',{'gate':{'sha256':'synthetic-fixture-only'},**report})
 manifest=publish(out,r/'fixture_only.html');assert manifest['embedded_unique_videos']==1 and manifest['embedded_video_instances']==1 and manifest['contact_sheet_pages']==7
 import re
 js=re.search(r'<script>(.*?)</script>',(r/'fixture_only.html').read_text(),re.S).group(1);(r/'page.js').write_text(js)
 subprocess.run(['node','--check',str(r/'page.js')],check=True,timeout=30)
 save(ROOT/'audit/MEDIA_FIXTURE_VERIFIED.json' ,{'passed':True,'synthetic_only':True,'video':{k:v for k,v in s.items() if k!='pts_s'},'first_frame_three_column_rgb':colors,'caption_black_pixel':rgb(5,90),'page_count':7,'HTML_embedded_media_verified':True,'JavaScript_syntax_verified':True,'original_indices':list(range(49)),'GPU_started':False},replace=True)
 print('synthetic media:147frames24fps, 3 equal columns, black caption, 49 times/7pages PASS')
