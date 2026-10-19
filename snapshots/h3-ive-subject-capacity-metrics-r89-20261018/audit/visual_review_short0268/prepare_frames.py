from pathlib import Path
import json,subprocess,sys,hashlib
from PIL import Image,ImageDraw,ImageFont
O=Path(__file__).resolve().parent; R=O.parents[1]
sys.path.insert(0,str(R/'scripts'))
from common import validate_static, verify_intake
P=json.loads((O/'REVIEW_PLAN.json').read_text()); pair=P['pair']
validate_static();verify_intake(pair)
assert (R/'audit/watcher'/f'{pair}_MEDIA_READY.json').is_file(), 'wait for existing watcher MEDIA_READY'
manifest=R/'showcase'/pair/'PRESENTATION.json'; M=json.loads(manifest.read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bound(p):return {'file':str(p),'sha256':sha(p)}
assert sha(M['collection']['file'])==M['collection']['sha256']
assert sha(M['gate']['file'])==M['gate']['sha256'] and json.loads(Path(M['gate']['file']).read_text())['passed'] is True
F='/opt/homebrew/bin/ffmpeg'; FP='/opt/homebrew/bin/ffprobe'; w,h=P['display_wh'];N=P['valid_frames'];roles=['参考视频','普通编辑','时序引导'];streams=[];frames=[]
for b in M['inputs']:
 path=Path(b['file']);assert sha(path)==b['sha256']
 info=json.loads(subprocess.check_output([FP,'-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(path)],timeout=90))
 pts=[float(x['best_effort_timestamp_time']) for x in info['frames']];assert len(pts)==P['total_frames'] and info['streams'][0]['avg_frame_rate']=='24/1';assert all(abs(t-i/24)<1e-6 for i,t in enumerate(pts))
 filters=[]
 if P['crop_xywh']:
  x,y,cw,ch=P['crop_xywh'];filters.append(f'crop={cw}:{ch}:{x}:{y}')
 filters.append(f'scale={w}:{h}:flags=lanczos')
 raw=subprocess.check_output([F,'-v','error','-threads','1','-i',str(path),'-vf',','.join(filters),'-frames:v',str(N),'-f','rawvideo','-pix_fmt','rgb24','-threads','1','-'],timeout=120)
 assert len(raw)==N*w*h*3;frames.append(raw);streams.append({'video':bound(path),'pts_s':pts,'properties':info['streams'][0]})
font=ImageFont.truetype('/System/Library/Fonts/STHeiti Light.ttc',19)
def sheet(indices,path):
 im=Image.new('RGB',(3*w,len(indices)*(h+34)),'black');draw=ImageDraw.Draw(im)
 for row,i in enumerate(indices):
  assert 0<=i<N
  for col,raw in enumerate(frames):
   im.paste(Image.frombytes('RGB',(w,h),raw[i*w*h*3:(i+1)*w*h*3]),(col*w,row*(h+34)))
   draw.text((col*w+7,row*(h+34)+h+6),f'{roles[col]} | f{i:03d} | {i/24:.3f}s',font=font,fill='white')
 im.save(path,quality=96)
files=[]
for start in range(0,N,5):
 path=O/f'all_frames_{start:03d}_{min(start+4,N-1):03d}.jpg';sheet(list(range(start,min(start+5,N))),path);files.append(bound(path))
sheet(P['key_frame_indices'],O/'key_events.jpg')
ledger={'pair':pair,'review_plan':bound(O/'REVIEW_PLAN.json'),'presentation':bound(manifest),'videos':streams,'all_physical_frame_indices':list(range(N)),'key_frame_indices':P['key_frame_indices'],'key_events':bound(O/'key_events.jpg'),'pages':files,'scope':'All valid decoded frames at unchanged physical index; equal spatial scaling/cropping only. Diagnostic sheets are not new generated outcomes.'}
(O/'FRAME_LEDGER.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'pair':pair,'key_events':str(O/'key_events.jpg'),'pages':len(files)},ensure_ascii=False))
