"""Explicit synthetic media test. Never creates incoming/ or an actual completion."""
import json,subprocess,sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import render_pair as r
R=Path(__file__).resolve().parents[1];O=R/'audit/synthetic_paired_media_fixture';O.mkdir(exist_ok=False)
F='/opt/homebrew/bin/ffmpeg';FP='/opt/homebrew/bin/ffprobe';a=O/'fixture_source.mp4';b=O/'fixture_native.mp4';c=O/'fixture_forced.mp4'
for path,color in [(a,'red'),(b,'blue'),(c,'lime')]:
 subprocess.run([F,'-v','error','-nostdin','-n','-f','lavfi','-i',f'color=c={color}:s=1152x768:r=24','-frames:v','20','-c:v','libx264','-crf','0','-pix_fmt','yuv420p',str(path)],check=True,timeout=90)
result=r.render_files([a,b,c],O,20,18,r.choose_font(),F,FP)
assert result['videos'][0]['properties']['count']==18
assert len(result['contact_sheets'])==2
assert [len(x['physical_frame_indices']) for x in result['contact_sheets']]==[6,12]
# Actual decoded central pixels verify source on left and Native on right; bottom is black.
data=subprocess.check_output([F,'-v','error','-i',str(O/'source_native_guided_full_valid.mp4'),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],timeout=90)
def pixel(x,y):return tuple(data[(y*3456+x)*3:(y*3456+x)*3+3])
left,right,third,bottom=pixel(576,384),pixel(1728,384),pixel(2880,384),pixel(1000,850)
assert left[0]>240 and left[1]<10 and left[2]<10
assert right[2]>240 and right[0]<10 and right[1]<10
assert third[1]>240 and third[0]<10 and third[2]<10
assert max(bottom)<10
report={'scope':'SYNTHETIC FIXTURE ONLY. Three flat color inputs, no model inference. Not actual R105 results.','passed':True,'total_fixture_frames':20,'valid_fixture_frames':18,'central_pixels':{'source_left':left,'native_middle':right,'guided_right':third,'bottom_caption_canvas':bottom},'media':result}
(O/'FIXTURE_RESULT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'fixture_passed':True,'file':str(O/'FIXTURE_RESULT.json')}))
