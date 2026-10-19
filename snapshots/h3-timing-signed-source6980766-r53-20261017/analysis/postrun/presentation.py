"""Labelled presentation only. Fixed same-frame content, frozen Chinese bottom strips."""
from contract import *
import subprocess,shutil

def layout_keys(videos,layout):
 keys=layout['keys'];require(len(keys)==3 and len(set(keys))==len(keys),'presentation columns duplicate/count')
 require(len(layout['labels'])==len(keys) and all(k in videos for k in keys),'presentation actual dictionary keys missing')
 require(keys==['SOURCE','native','AUTO'],'presentation method order')
 return keys

def render_layout(videos,folder,p,layout):
 import cv2,numpy as np
 keys=layout_keys(videos,layout);caption=HERE/layout['asset'];require(sha(caption)==layout['asset_sha256'],'caption asset changed');bar=cv2.imread(str(caption));require(bar is not None and bar.shape==(48,656*len(keys),3),'caption geometry');folder.mkdir()
 ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe');require(ffmpeg and ffprobe,'existing ffmpeg/probe required');playback={}
 for key in keys:
  q=subprocess.check_output([ffprobe,'-v','error','-select_streams','v:0','-show_streams','-show_frames','-show_entries','stream=width,height,r_frame_rate,avg_frame_rate,duration,time_base:frame=best_effort_timestamp_time','-of','json',str(videos[key])],timeout=30)
  playback[key]=dict(check_playback_probe(json.loads(q)),video_sha256=sha(videos[key]))
 save(folder/'PLAYBACK_GATE.json',{'passed':True,'same_physical_frame_grid':True,'videos':playback})
 caps={};writer=None;hashes={k:[] for k in keys};cv2.setNumThreads(1)
 try:
  for key in keys:
   cap=cv2.VideoCapture(str(videos[key]),cv2.CAP_FFMPEG,[cv2.CAP_PROP_N_THREADS,1]);require(cap.isOpened(),'presentation decode failed');caps[key]=cap
  width=656*len(keys);height=416;dest=folder/'comparison_141frames.mp4'
  cmd=[ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-f','rawvideo','-pixel_format','bgr24','-video_size',f'{width}x{height}','-framerate','24','-i','pipe:0','-an','-c:v','libx264','-threads','1','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)]
  with (folder/'ffmpeg.log').open('x') as log:
   writer=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=log,stderr=log)
   for i in range(141):
    canvas=np.zeros((height,width,3),np.uint8);canvas[368:]=bar
    for j,key in enumerate(keys):
     ok,bgr=caps[key].read();require(ok and bgr.shape==(736,1312,3),'presentation exact frame/geometry');hashes[key].append(hashlib.sha256(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB).tobytes()).hexdigest());canvas[:368,j*656:(j+1)*656]=cv2.resize(bgr,(656,368),interpolation=cv2.INTER_AREA)
    if i in p['fixed_visual_frames']:require(cv2.imwrite(str(folder/f'frame{i:03d}.png'),canvas),'presentation PNG failure')
    writer.stdin.write(canvas.tobytes())
   require(all(not c.read()[0] for c in caps.values()),'presentation extra frame');writer.stdin.close();require(writer.wait(timeout=60)==0,'presentation encoder error')
 finally:
  for cap in caps.values():cap.release()
  if writer is not None and writer.poll() is None:writer.terminate();writer.wait(timeout=10)
 result={'keys':keys,'captions':layout['labels'],'caption_asset_sha256':sha(caption),'frames':141,'fps':24,'fixed_frames':p['fixed_visual_frames'],'RGB_frame_sha256':hashes,'method':'same-frame full canvas scaled656x368; black48px caption below; no top text','video_sha256':sha(dest),'quality_verdict':'PENDING'};save(folder/'PRESENTATION.json',result);return result
