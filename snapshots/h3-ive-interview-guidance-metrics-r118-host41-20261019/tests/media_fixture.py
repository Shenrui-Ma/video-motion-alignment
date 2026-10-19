"""CPU synthetic frames exercise the reused renderer; these are not experiment results."""
import sys,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import *
import render_media,full_frame_review,prepare
p=ROOT/'audit/synthetic_media_fixture';p.mkdir(exist_ok=False);ff='/opt/homebrew/bin/ffmpeg';fp='/opt/homebrew/bin/ffprobe';inputs=[]
for role,color in [('source','red'),('native','green'),('forced','blue')]:
 q=p/(role+'.mp4');subprocess.run([ff,'-v','error','-nostdin','-n','-f','lavfi','-i',f'color={color}:s=1312x736:r=24','-frames:v','14','-c:v','libx264','-pix_fmt','yuv420p',str(q)],check=True);inputs.append(q)
r=render_media.render_files(inputs,p,14,12,render_media.choose_font(),ff,fp,rows=(6,12));pages=full_frame_review.render_files(inputs,p/'full',14,12,render_media.choose_font(),ff,fp);require([ix for row in pages for ix in row['physical_frame_indices']]==list(range(12)),'fixture frame coverage differs')
crop=p/'crop.mp4';subprocess.run([ff,'-v','error','-nostdin','-n','-i',str(inputs[0]),'-vf','crop=1280:720:16:8,trim=end_frame=12','-an','-c:v','libx264rgb','-crf','0','-pix_fmt','rgb24',str(crop)],check=True);require(prepare.decoded_hash(inputs[0],True,12)==prepare.decoded_hash(crop,False,12),'lossless crop pixels differ')
save(p/'RESULT.json',dict(passed=True,synthetic_only=True,actual_generated_results=False,presentation=r,full_frame_pages=pages,crop_rgb_sha256=prepare.decoded_hash(crop,False,12)))
print(json.dumps(bound(p/'RESULT.json')))
