"""Optional bounded synthetic video gate; no source/target model or scientific metrics."""
import tempfile,subprocess,shutil,json
from pathlib import Path
from contract import HERE,read,require
from presentation import render_layout

def main():
 import cv2
 cv2.setNumThreads(1);p=read(HERE/'PROTOCOL.json');ffmpeg=shutil.which('ffmpeg');require(ffmpeg is not None,'ffmpeg required')
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp);v=root/'synthetic.mp4'
  subprocess.run([ffmpeg,'-v','error','-f','lavfi','-i','color=c=0x345678:s=1312x736:r=24','-frames:v','141','-an','-c:v','libx264','-threads','1','-preset','ultrafast','-pix_fmt','yuv420p',str(v)],check=True,timeout=30)
  vids={k:v for k in ('SOURCE','Native','Auto','Manual')};layout=p['presentation']['layouts']['source_native_manual'];r=render_layout(vids,root/'rendered',p,layout)
  require(len(r['RGB_frame_sha256']['SOURCE'])==141 and all(r['RGB_frame_sha256'][k]==r['RGB_frame_sha256']['SOURCE'] for k in layout['keys']),'synthetic shared input mapping')
  bar=cv2.imread(str(HERE/layout['asset']));frame=cv2.imread(str(root/'rendered/frame000.png'));require(frame.shape==(416,1968,3) and (frame[368:]==bar).all(),'bottom caption PNG geometry/value')
  probe=json.loads(subprocess.check_output([shutil.which('ffprobe'),'-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=width,height,nb_read_frames,r_frame_rate','-of','json',str(root/'rendered/comparison_141frames.mp4')],timeout=30));s=probe['streams'][0];require((s['width'],s['height'],s['nb_read_frames'],s['r_frame_rate'])==(1968,416,'141','24/1'),'presentation encoded output geometry/rate/count')
 print('PASS synthetic141frame three-column Chinese presentation; source hash mapping/bottom PNG/exact frame count/24fps; no model/GPU')
if __name__=='__main__':main()
