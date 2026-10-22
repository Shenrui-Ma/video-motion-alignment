from pathlib import Path
import json,hashlib,subprocess
from PIL import Image,ImageFont,ImageDraw
r=Path(__file__).resolve().parent;inc=Path('/Users/researcher/DevProjects/h3-flexiact-forced-metrics-r65-20261018/incoming/fitness');ins=inc.parent.parent/'inputs';media=r/'media';media.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
gate=json.loads((inc/'PAIR_RUNTIME_GATE.json').read_text());assert gate['passed'] and all(x is True for x in gate['checks'].values());ev={'gate':{'file':str(inc/'PAIR_RUNTIME_GATE.json'),'sha256':sha(inc/'PAIR_RUNTIME_GATE.json')},'videos':{},'checks':{},'scope':'CPU actual paired visual inspection'}
for arm in ['native','forced']:
 run=gate['runs'][arm];j=json.loads((inc/f'{arm}_job.json').read_text());h=json.loads((inc/f'{arm}_history.json').read_text());g=json.loads((inc/f'{arm}_graph.json').read_text())
 assert sha(inc/f'{arm}.mp4')==run['video']['sha256']
 assert sha(inc/f'{arm}_job.json')==run['job_sha256'] and sha(inc/f'{arm}_history.json')==run['history_sha256'] and sha(inc/f'{arm}_router.json')==run['router_file_sha256']
 assert j['status']=='success' and h['status']['status_str']=='success' and h['status']['completed']
 assert j['prompt_id']==h['prompt'][1] and h['prompt'][2]==g and sha(inc/f'{arm}_graph.json')==j['graph_sha256']
 assert h['outputs']['14']['images'][0]['filename']==Path(run['video']['file']).name
 assert sha(ins/'source_fitness_video.mp4')==j['case_binding']['case']['video_sha256']
 assert sha(ins/'source_fitness_portrait.webp')==j['case_binding']['case']['portrait_sha256']
 ev['checks'][arm+'_input_output_actual_binding']=True
videos={'source':ins/'source_fitness_video.mp4','native':inc/'native.mp4','forced':inc/'forced.mp4'}
for arm,p in videos.items():
 out=media/arm;out.mkdir(exist_ok=True)
 q=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(p)]));pts=[float(x['best_effort_timestamp_time']) for x in q['frames']]
 assert len(pts)==158 and all(abs(t-i/24)<1e-5 for i,t in enumerate(pts))
 subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-y','-i',str(p),'-vf','select=not(mod(n\\,3))*lte(n\\,144)','-fps_mode','passthrough','-start_number','0',str(out/'original_%03d.png')],check=True)
 files=sorted(out.glob('original_*.png'));assert len(files)==49
 ev['videos'][arm]={'file':str(p),'sha256':sha(p),'actual_frame_count':len(pts),'fps':24,'valid_frames':147,'extracted_indices':list(range(0,147,3)),'extracted_frame_sha256':[sha(x) for x in files]}
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf',20)
labels=['参考视频','编辑后视频','编辑＋时序引导后视频'];arms=['source','native','forced']
def sheet(indices,name,width=480):
 height=width*2//3;cap=34;c=Image.new('RGB',(width*3,len(indices)*(height+cap)),'black');d=ImageDraw.Draw(c)
 for row,i in enumerate(indices):
  for col,arm in enumerate(arms):
   im=Image.open(media/arm/f'original_{i:03d}.png').convert('RGB');assert im.size==(1152,768);c.paste(im.resize((width,height),Image.Resampling.LANCZOS),(col*width,row*(height+cap)));d.text((col*width+8,row*(height+cap)+height+5),f'{labels[col]} | {i/8:.3f}s',font=font,fill='white')
 c.save(media/name)
sheet([0,4,8,12,16,20],'six_times_0_to_2p5s.png')
sheet([24,28,32,36,40,44,48],'later_3_to_6s.png')
for start in range(0,49,7):sheet(list(range(start,start+7)),f'all49_page_{start:02d}_{start+6:02d}.png')
# caption PNG serves ffmpeg overlay without the unavailable drawtext filter.
cap=Image.new('RGB',(3456,54),'black');d=ImageDraw.Draw(cap);vf=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf',30)
for col,label in enumerate(labels):
 b=d.textbbox((0,0),label,font=vf);d.text((col*1152+(1152-(b[2]-b[0]))/2,11),label,font=vf,fill='white')
cap.save(media/'caption.png')
(r/'ACTUAL_BINDING.json').write_text(json.dumps(ev,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':True,'six':str(media/'six_times_0_to_2p5s.png'),'later':str(media/'later_3_to_6s.png')}))
