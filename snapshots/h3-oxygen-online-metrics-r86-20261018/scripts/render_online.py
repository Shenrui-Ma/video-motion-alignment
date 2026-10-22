"""Actual source/R73 Native/R86 online display, plus separate historical fixed control."""
import argparse,io,subprocess,time
from PIL import Image,ImageDraw,ImageFont
from common import *
from media_utils import media_info,check_time,choose_font,caption_strip,command,six_frames,LABELS
FIXED_LABELS=('1.参考视频','2.普通编辑','3.固定时序引导')
def render(ffmpeg,ffprobe,font):
 cfg=validate_static();gate,case=verify_intake();dest=ROOT/'showcase';require(not dest.exists(),'existing media retained');staging=ROOT/'audit/render_staging'/str(time.time_ns());staging.mkdir(parents=True)
 assets=cfg['assets'];source=ROOT/assets['source']['file'];native=ROOT/assets['native']['file'];fixed=ROOT/assets['forced']['file'];online=ROOT/'incoming/online.mp4';paths=[source,native,online];infos={}
 for name,path in [('source',source),('native',native),('online',online),('fixed_control',fixed)]:
  info=media_info(path,ffprobe);check_time(info,107,1312,736);infos[name]={'file':str(path),'sha256':sha(path),'properties':info}
 caption=staging/'online_caption.png';caption_strip(font).save(caption);fixedcaption=staging/'fixed_caption.png';caption_strip(font,FIXED_LABELS).save(fixedcaption);videos=[]
 for name,count,inputs,cap in [('online_full_valid',98,paths,caption),('online_first2seconds',48,paths,caption),('r73_fixed_full_valid',98,[source,native,fixed],fixedcaption)]:
  output=staging/(name+'.mp4');cmd=command(inputs,cap,output,count,ffmpeg,98);subprocess.run(cmd,check=True,timeout=420);info=media_info(output,ffprobe);check_time(info,count,3840,808)
  videos.append({'name':name,'file':output.name,'sha256':sha(output),'frame_interval_inclusive':[0,count-1],'fps':24,'columns':['source','R73_native','R73_fixed' if name.startswith('r73_') else 'R86_online'],'properties':info,'command':cmd})
 frames=six_frames(98);im=Image.new('RGB',(1440,6*316),'black');draw=ImageDraw.Draw(im);ft=ImageFont.truetype(str(font),18)
 for row,frame in enumerate(frames):
  for col,path in enumerate(paths):
   data=subprocess.check_output([ffmpeg,'-v','error','-threads','1','-i',str(path),'-vf',f'select=eq(n\\,{frame}),crop=1280:720:16:8,scale=480:270:flags=lanczos','-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','-'],timeout=90);im.paste(Image.open(io.BytesIO(data)).convert('RGB'),(col*480,row*316));label=LABELS[col];draw.text((col*480+(480-draw.textlength(label,font=ft))/2,row*316+290),label,font=ft,fill='white')
  draw.text((8,row*316+272),f'frame {frame} | {frame/24:.3f}s',font=ImageFont.truetype(str(font),13),fill='#bbb')
 im.save(staging/'six_times.jpg',quality=94)
 save(staging/'PRESENTATION.json',{'schema':'r86-online-media-presentation-v1','gate':bound(ROOT/'incoming/ONLINE_RUNTIME_GATE.json'),'collection':bound(ROOT/'incoming/COLLECTION.json'),'actual_decisions':bound(ROOT/'incoming/ACTUAL_DECISIONS.json'),'inputs':infos,'videos':videos,'six_times':{'file':'six_times.jpg','sha256':sha(staging/'six_times.jpg'),'physical_frame_indices':frames},'valid_frames':98,'full_frames':107,'display_fps':24,'evaluation_crop_xywh':[16,8,1280,720],'original_mapping':assets['provenance'],'manual_spatial_actor_bounds':[.4,.75],'automatic_scope':'online temporal windows/start/stop','fixed_control':'historical R73 fixed steps6..14, shown separately','planned_denominator':1,'quality_status':'UNREVIEWED'})
 staging.rename(dest);return bound(dest/'PRESENTATION.json')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--ffmpeg',default='ffmpeg');p.add_argument('--ffprobe',default='ffprobe');p.add_argument('--font');a=p.parse_args();print(json.dumps(render(a.ffmpeg,a.ffprobe,choose_font(a.font))))
