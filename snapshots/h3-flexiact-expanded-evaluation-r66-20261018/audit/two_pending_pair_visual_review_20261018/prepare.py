from pathlib import Path
import json,hashlib,subprocess
from PIL import Image,ImageDraw,ImageFont
O=Path(__file__).resolve().parent; R=O.parents[1]
I=json.loads(Path('/Users/researcher/DevProjects/h3-benchmark-all-results-showcase-20261018/inventory/flexiact.json').read_text())['items']
F='/opt/homebrew/bin/ffmpeg'; FP='/opt/homebrew/bin/ffprobe'; w,h=384,256
font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',18)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for pair in json.loads((O/'PLAN.json').read_text())['pairs']:
 item=next(x for x in I if x['id']=='flex_r66_'+pair);out=O/pair;out.mkdir(exist_ok=True)
 gate=R/'incoming'/pair/'PAIR_RUNTIME_GATE.json';assert json.loads(gate.read_text())['passed'] is True
 roles=['参考视频','普通编辑','时序引导'];raws=[];evidence=[]
 for key in ['reference_video_path','ordinary_video_path','guided_video_path']:
  p=Path(item[key]);assert sha(p)==item['media_sha256'][key]
  info=json.loads(subprocess.check_output([FP,'-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(p)]));pts=[float(f['best_effort_timestamp_time']) for f in info['frames']]
  assert len(pts)==158 and info['streams'][0]['avg_frame_rate']=='24/1' and all(abs(t-i/24)<1e-6 for i,t in enumerate(pts))
  raw=subprocess.check_output([F,'-v','error','-threads','1','-i',str(p),'-vf',f'scale={w}:{h}:flags=lanczos','-frames:v','147','-f','rawvideo','-pix_fmt','rgb24','-threads','1','-']);assert len(raw)==147*w*h*3
  raws.append(raw);evidence.append({'file':str(p),'sha256':sha(p),'frames':158,'pts_seconds':pts,'stream':info['streams'][0]})
 def sheet(indices,name):
  im=Image.new('RGB',(w*3,len(indices)*(h+30)),'black');d=ImageDraw.Draw(im)
  for row,i in enumerate(indices):
   for col,raw in enumerate(raws):
    im.paste(Image.frombytes('RGB',(w,h),raw[i*w*h*3:(i+1)*w*h*3]),(w*col,row*(h+30)))
    d.text((col*w+5,row*(h+30)+h+3),f'{roles[col]} | f{i:03d} | {i/24:.3f}s',font=font,fill='white')
  p=out/name;im.save(p,quality=96);return {'file':str(p),'sha256':sha(p),'indices':indices}
 indices=list(range(0,147,3));pages=[sheet(indices[j:j+7],f'grid_{j:02d}.jpg') for j in range(0,len(indices),7)]
 # All generated in-between frames retained in diagnostic sheets for follow-up.
 dense=[sheet(list(range(j,min(j+7,147))),f'dense_{j:03d}.jpg') for j in range(0,147,7)]
 ledger={'pair':pair,'plan_sha256':sha(O/'PLAN.json'),'videos':evidence,'gate':{'file':str(gate),'sha256':sha(gate)},'reference_image':{'file':item['reference_image_path'],'sha256':sha(item['reference_image_path'])},'initial_grid_pages':pages,'dense_pages':dense,'generated_frames':158,'valid_frames':147,'fps':24,'source_time_precision_seconds':.125}
 (out/'LEDGER.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n')
 print(pair,len(pages),len(dense),flush=True)
