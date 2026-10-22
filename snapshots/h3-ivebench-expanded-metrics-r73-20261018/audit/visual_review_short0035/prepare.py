from pathlib import Path
import hashlib,json,subprocess
from PIL import Image,ImageDraw,ImageFont
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
F='/opt/homebrew/bin/ffmpeg';P='/opt/homebrew/bin/ffprobe'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bound(p):return {'file':str(p),'sha256':sha(p)}
meta=json.loads((R/'prepared/short_0035/METRIC_INPUTS.json').read_text());gate=R/'incoming/short_0035/PAIR_RUNTIME_GATE.json';assert sha(gate)==meta['producer_runtime_gate']['sha256'] and json.loads(gate.read_text())['passed'] is True
roles=['source','native','forced'];videos=[R/'prepared/short_0035'/f'{role}_score.mp4' for role in roles];expected=[meta['source_score_video']]+[meta['edited'][role]['score_video'] for role in roles[1:]]
streams=[];frames=[]
for p,e in zip(videos,expected):
 assert sha(p)==e['sha256'];info=json.loads(subprocess.check_output([P,'-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(p)]));s=info['streams'][0];pts=[float(x['best_effort_timestamp_time']) for x in info['frames']];assert (s['width'],s['height'],len(pts),s['avg_frame_rate'])==(1280,720,70,'24/1');assert all(abs(t-i/24)<1e-6 for i,t in enumerate(pts));streams.append({'file':bound(p),'properties':s,'pts_s':pts})
 data=subprocess.check_output([F,'-v','error','-threads','1','-i',str(p),'-vf','scale=480:270:flags=lanczos','-f','rawvideo','-pix_fmt','rgb24','-threads','1','-']);assert len(data)==70*480*270*3;frames.append(data)
font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',19)
for start in range(0,70,5):
 im=Image.new('RGB',(1440,5*300),'black');d=ImageDraw.Draw(im)
 for j in range(5):
  i=start+j
  for col,data in enumerate(frames):
   raw=data[i*480*270*3:(i+1)*480*270*3];im.paste(Image.frombytes('RGB',(480,270),raw),(480*col,300*j));d.text((480*col+6,300*j+275),f'{roles[col]}  frame {i:02d} | {i/24:.3f}s',fill='white',font=font)
 im.save(O/f'all70_page_{start//5+1:02d}.jpg',quality=95)
(O/'INPUTS_AND_FRAME_LEDGER.json').write_text(json.dumps({'gate':bound(gate),'prepared_manifest':bound(R/'prepared/short_0035/METRIC_INPUTS.json'),'videos':streams,'all_reviewed_physical_frame_indices':list(range(70)),'input_to_original_frame':meta['input_to_original_frame'][:70],'sheet_scope':'all70 frames, fixed same physical time, whole frame scaled equally480x270; no interpolation or temporal alignment','pages':[bound(p) for p in sorted(O.glob('all70_page*.jpg'))]},indent=2)+'\n')
print(O)
