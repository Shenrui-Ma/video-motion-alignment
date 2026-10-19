import sys,json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'scripts'))
from render_pair import command,caption_strip,choose_font,media_info,check_time
from common import pair_info,sha
p=pair_info('long_0047');source=R/p['source']['file'];d=R/'audit/cpu_render_smoke';d.mkdir(exist_ok=False)
caption_strip(choose_font()).save(d/'caption.png');out=d/'SYNTHETIC_three_identical_sources.mp4'
cmd=command([source]*3,d/'caption.png',out,p['valid_frames'],'/opt/homebrew/bin/ffmpeg',p['valid_frames']);subprocess.run(cmd,check=True,timeout=300)
info=media_info(out,'/opt/homebrew/bin/ffprobe');check_time(info,p['valid_frames'],3840,808)
subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-i',str(out),'-frames:v','1',str(d/'first_frame.png')],check=True)
(d/'RESULT.json').write_text(json.dumps({'passed':True,'synthetic':True,'all_columns_same_original_source':True,'H3_generated_outputs':False,'video_sha256':sha(out),'video_info':info,'command':cmd},indent=2)+'\n')
print(d)
