"""CPU-only source timeline checks and clearly synthetic presentation smoke."""
from pathlib import Path
import ast,json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
from render_pair import *
validate_static();rows=[]
for pair in PAIRS:
 p=pair_info(pair);info=media_info(ROOT/p['source']['file'],'/opt/homebrew/bin/ffprobe');check_time(info,p['geometry']['frames'],1312,736)
 rows.append({'source_id':pair,'source':p['source'],'original':p['source_original'],'provenance':p['provenance'],'valid_frames':p['valid_frames'],'prepared_info':info,'passed':True})
save(ROOT/'audit/INPUT_TIMELINES.json',{'passed':True,'sources':rows,'scope':'all7actualpreparedreferencevideos; no H3 output yet'})
for p in [*ROOT.glob('scripts/*.py'),*ROOT.glob('tests/*.py')]:ast.parse(p.read_text(),filename=str(p))
font=choose_font();caption_strip(font).save(ROOT/'audit/caption_preview.png');audit=ROOT/'audit/cpu_render_smoke';audit.mkdir(exist_ok=True)
p=pair_info(PAIRS[0]);source=ROOT/p['source']['file'];out=audit/'SYNTHETIC_three_identical_sources.mp4';cmd=command([source]*3,ROOT/'audit/caption_preview.png',out,p['valid_frames'],'/opt/homebrew/bin/ffmpeg',p['valid_frames']);start=time.monotonic();subprocess.run(cmd,check=True,timeout=420)
info=media_info(out,'/opt/homebrew/bin/ffprobe');check_time(info,43,3840,808)
subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(out),'-frames:v','1',str(audit/'first_frame.png')],check=True,timeout=60)
save(audit/'RESULT.json',{'passed':True,'SYNTHETIC':True,'meaning':'Same real source placed in all3columns to verify CPU renderer; not three generated results.','video':bound(out),'properties':info,'command':cmd,'seconds':time.monotonic()-start,'GPU_started':False})
print(json.dumps({'passed':True,'source_count':len(rows),'syntax_files':len(list(ROOT.glob('scripts/*.py')))+len(list(ROOT.glob('tests/*.py'))),'smoke':bound(audit/'RESULT.json')}))
