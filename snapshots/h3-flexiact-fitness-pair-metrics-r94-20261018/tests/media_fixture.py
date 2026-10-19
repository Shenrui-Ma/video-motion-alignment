"""Synthetic flat-color triptych only; never creates actual intake or success."""
from pathlib import Path
import sys,json,subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from render_pair import command,caption_strip,choose_font,media_info,check_time
R=Path(__file__).resolve().parents[1];O=R/'audit/synthetic_media_fixture';O.mkdir(exist_ok=False)
F='/opt/homebrew/bin/ffmpeg';FP='/opt/homebrew/bin/ffprobe';paths=[]
for i,color in enumerate(['red','lime','blue']):
 p=O/f'fixture_{i}.mp4';subprocess.run([F,'-v','error','-nostdin','-n','-f','lavfi','-i',f'color=c={color}:s=1152x768:r=24','-frames:v','158','-c:v','libx264','-crf','0','-pix_fmt','yuv420p',str(p)],check=True,timeout=90);paths.append(p)
cap=O/'caption.png';caption_strip(choose_font()).save(cap);output=O/'synthetic_triptych_147.mp4';subprocess.run(command(paths,cap,output,147,F),check=True,timeout=180)
info=media_info(output,FP);check_time(info,147,3456,856)
raw=subprocess.check_output([F,'-v','error','-i',str(output),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],timeout=90)
def px(x,y):return tuple(raw[(y*3456+x)*3:(y*3456+x)*3+3])
colors=[px(576,384),px(1728,384),px(2880,384)];assert colors[0][0]>240 and colors[0][1]<10 and colors[0][2]<10;assert colors[1][1]>240 and colors[1][0]<10 and colors[1][2]<10;assert colors[2][2]>240 and colors[2][0]<10 and colors[2][1]<10;assert max(px(900,853))<10
subprocess.run([F,'-v','error','-i',str(output),'-frames:v','1','-y',str(O/'synthetic_first_frame.png')],check=True,timeout=90)
(O/'FIXTURE_RESULT.json').write_text(json.dumps({'scope':'SYNTHETIC ONLY: flat colors; no model, tracker or actual generated result','passed':True,'full_fixture_frames':158,'valid_fixture_frames':147,'display_fps':24,'pixels_left_middle_right':colors,'properties':info},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'synthetic_media_passed':True,'file':str(O/'FIXTURE_RESULT.json')}))
