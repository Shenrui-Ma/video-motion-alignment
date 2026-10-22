"""CPU checks actual archived input timebases; repeated source smoke is synthetic."""
from pathlib import Path
import ast,json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
from media_utils import *
cfg=validate_static();rows=[]
for role in ['source','native','forced']:
 asset=cfg['assets'][role];p=ROOT/asset['file'];require(sha(p)==asset['sha256'],'asset changed');info=media_info(p,'/opt/homebrew/bin/ffprobe');check_time(info,107,1312,736);rows.append({'role':role,'asset':asset,'properties':info})
save(ROOT/'audit/ACTUAL_INPUT_TIMEBASES.json',{'passed':True,'records':rows,'scope':'Archived source and R73 Native/fixed only; R86 online not generated'})
files=[*ROOT.glob('scripts/*.py'),*ROOT.glob('tests/*.py')]
for p in files:ast.parse(p.read_text(),filename=str(p))
font=choose_font();caption_strip(font).save(ROOT/'audit/caption_preview.png');audit=ROOT/'audit/cpu_render_smoke';audit.mkdir(exist_ok=True);source=ROOT/cfg['assets']['source']['file'];output=audit/'SYNTHETIC_same_source_three_columns.mp4'
cmd=command([source]*3,ROOT/'audit/caption_preview.png',output,98,'/opt/homebrew/bin/ffmpeg',98);start=time.monotonic();subprocess.run(cmd,check=True,timeout=420);info=media_info(output,'/opt/homebrew/bin/ffprobe');check_time(info,98,3840,808)
subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(output),'-frames:v','1',str(audit/'first_frame.png')],check=True,timeout=60)
save(audit/'RESULT.json',{'passed':True,'SYNTHETIC':True,'scope':'Three identical reference columns validate caption/98frame display; not R86 output','video':bound(output),'properties':info,'command':cmd,'seconds':time.monotonic()-start,'GPU_started':False})
print(json.dumps({'passed':True,'timebases':len(rows),'Python_AST':len(files),'smoke':bound(audit/'RESULT.json')}))
