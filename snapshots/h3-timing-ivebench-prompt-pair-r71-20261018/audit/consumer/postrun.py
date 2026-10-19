"""CPU-only collection and exact-frame presentation of the frozen R71 prompt pair."""
import argparse,base64,hashlib,html,io,json,os,shutil,subprocess,time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']=''
PRODUCER=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
ARMS=('p0','p1');SOURCE='short_0210';VALID=87;TOTAL=90
LABELS=('1.参考视频','2.原始提示词编辑','3.H3格式提示词编辑')
def read(path):return json.loads(Path(path).read_text())
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1024**2),b''):h.update(b)
 return h.hexdigest()
def check(ok,msg):
 if not ok:raise ValueError(msg)
def save(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def bound(path):return {'file':str(path),'sha256':sha(path),'bytes':Path(path).stat().st_size}
def validate_gate(gate):
 check(gate.get('schema')=='r71-paired-runtime-gate-v1' and gate.get('passed') is True and gate.get('source_id')==SOURCE and gate.get('prompt_versions')==['P0','P1'],'actual prompt pair gate incomplete')
 checks=gate.get('checks',{});check(checks and all(v is True for v in checks.values()),'unsuccessful gate checks')
 for key in ['producer_seal','actual_runtime_device','input_video_equal','native_vae_calls_equal','qwen_presentation_equal','target_latent_shapes_equal','actual_initial_AV_noise_equal','independent_prompt_conditioning']:
  check(checks.get(key) is True,'missing actual check: '+key)
 check(set(gate['runs'])==set(ARMS),'wrong prompt arms')
 for arm,item in gate['runs'].items():
  check(item['run_id']==f'r71_{SOURCE}_seed2026101701_{arm}' and item['valid_frames']==VALID and item['routed_blocks']==0 and item['NFE']==item['Euler_updates']==20,'wrong run/geometry/routing')
  p=item['video']['properties'];check((p['width'],p['height'],int(p['nb_read_frames']),p['avg_frame_rate'])==(1312,736,TOTAL,'24/1'),'wrong video geometry')
 return gate

def collect():
 receipt=PRODUCER/'analysis/postrun'/SOURCE/'PAIR_RUNTIME_GATE.json';gate=validate_gate(read(receipt));out=HERE/'incoming'
 check(not out.exists(),'preserve existing intake');out.mkdir()
 shutil.copy2(receipt,out/'PAIR_RUNTIME_GATE.json')
 files=[]
 for arm in ARMS:
  row=gate['runs'][arm];path=Path(row['video']['file']);check(path.resolve().is_relative_to(PRODUCER/'output') and sha(path)==row['video']['sha256'],'output bytes changed')
  shutil.copy2(path,out/(arm+'.mp4'))
  run=row['run_id']
  for folder,suffix,key in [('logs','_history.json','history_sha256'),('logs','_job.json','job_sha256'),('audit/router','.json','router_file_sha256')]:
   p=PRODUCER/folder/(run+suffix);check(sha(p)==row[key],'runtime evidence changed');shutil.copy2(p,out/(arm+'_'+Path(folder).name+suffix))
  for folder,suffix in [('configs/graphs','.json'),('audit','_conditioning.json'),('audit','_noise.json')]:
   p=PRODUCER/folder/(run+suffix);shutil.copy2(p,out/(arm+'_'+Path(folder).name+suffix))
 shutil.copy2(PRODUCER/'configs/scientific_contract.json',out/'scientific_contract.json');shutil.copy2(PRODUCER/'deploy_manifest.json',out/'deploy_manifest.json')
 save(out/'COLLECTION.json',{'schema':'r71-actual-prompt-pair-collection-v1','producer':str(PRODUCER),'receipt':bound(receipt),'files':{p.name:bound(p) for p in out.iterdir() if p.is_file()},'created_unix':time.time()})
 return out

def probe(path):
 out=subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(path)],timeout=120)
 value=json.loads(out);s=value['streams'][0];s['pts']=[float(x['best_effort_timestamp_time']) for x in value['frames']];return s

def render():
 from PIL import Image,ImageFont,ImageDraw
 incoming=HERE/'incoming';receipt=incoming/'PAIR_RUNTIME_GATE.json';gate=validate_gate(read(receipt));collection=read(incoming/'COLLECTION.json')
 for name,b in collection['files'].items():check(sha(incoming/name)==b['sha256'],'intake changed')
 science=read(incoming/'scientific_contract.json');expected=read(PRODUCER/'configs/scientific_contract.json');check(science==expected,'prompt science changed')
 paths=[PRODUCER/'inputs/short_0210_video.mp4']+[incoming/(a+'.mp4') for a in ARMS]
 check(sha(paths[0])==science['cases'][0]['video_sha256'],'reference input changed')
 for arm,path in zip(ARMS,paths[1:]):check(sha(path)==gate['runs'][arm]['video']['sha256'],'final video changed')
 for path in paths:
  s=probe(path);check((s['width'],s['height'],s['avg_frame_rate'],len(s['pts']))==(1312,736,'24/1',90),'source/output timeline differs');check(all(abs(t-i/24)<1e-6 for i,t in enumerate(s['pts'])),'nonuniform input time')
 output=HERE/'presentation';check(not output.exists(),'preserve existing presentation');output.mkdir()
 font=Path('/System/Library/Fonts/STHeiti Light.ttc');check(font.exists(),'Chinese font missing')
 caption=Image.new('RGB',(3840,88),'black');d=ImageDraw.Draw(caption);large=ImageFont.truetype(str(font),32);small=ImageFont.truetype(str(font),22)
 d.text((14,9),'角色替换',font=small,fill='white')
 for i,label in enumerate(LABELS):d.text((1280*i+(1280-d.textlength(label,font=large))/2,42),label,font=large,fill='white')
 strip=output/'caption.png';caption.save(strip)
 dest=output/'source_p0_p1_full87.mp4';cmd=['ffmpeg','-v','error','-nostdin','-n']
 for path in paths:cmd+=['-threads','2','-i',str(path)]
 cmd+=['-framerate','24','-loop','1','-i',str(strip)]
 filters=[f'[{i}:v]trim=end_frame=87,setpts=PTS-STARTPTS,crop=1280:720:16:8,setsar=1[v{i}]' for i in range(3)]+['[v0][v1][v2]hstack=inputs=3:shortest=1[images]','[images][3:v]vstack=inputs=2:shortest=1[out]']
 cmd+=['-filter_complex',';'.join(filters),'-map','[out]','-frames:v','87','-an','-fps_mode','vfr','-c:v','libx264','-crf','17','-preset','fast','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(dest)]
 subprocess.run(cmd,check=True,timeout=360)
 s=probe(dest);check((s['width'],s['height'],s['avg_frame_rate'],len(s['pts']))==(3840,808,'24/1',87),'presentation shape/time differs');check(all(abs(t-i/24)<1e-6 for i,t in enumerate(s['pts'])),'presentation time changed')
 indices=[round(i*(VALID-1)/5) for i in range(6)];canvas=Image.new('RGB',(1920,408*6),'black');draw=ImageDraw.Draw(canvas);sm=ImageFont.truetype(str(font),18);tiny=ImageFont.truetype(str(font),13)
 for row,index in enumerate(indices):
  for col,path in enumerate(paths):
   raw=subprocess.check_output(['ffmpeg','-v','error','-threads','1','-i',str(path),'-vf',f'select=eq(n\\,{index}),crop=1280:720:16:8,scale=640:360:flags=lanczos','-frames:v','1','-threads','1','-f','image2pipe','-vcodec','png','-'],timeout=90)
   canvas.paste(Image.open(io.BytesIO(raw)).convert('RGB'),(col*640,row*408));label=LABELS[col];draw.text((col*640+(640-draw.textlength(label,font=sm))/2,row*408+374),label,font=sm,fill='white')
  draw.text((6,row*408+362),f'{index/24:.3f}s',font=tiny,fill='#bbb')
 fig=output/'six_times.png';canvas.save(fig)
 record={'schema':'r71-presentation-v1','gate':bound(receipt),'videos':[bound(p) for p in paths],'video':bound(dest),'figure':bound(fig),'frame_indices':indices,'valid_frames':87,'fps':24,'crop_xywh':[16,8,1280,720],'selection':'six uniform physical indices over fixed valid prefix, selected before result inspection','audio':'presentation muted; no reference audio was a model input','labels':LABELS,'quality_review':'PENDING'}
 save(output/'PRESENTATION.json',record);return record

def document():
 p=HERE/'presentation';record=read(p/'PRESENTATION.json');v=p/'source_p0_p1_full87.mp4';f=p/'six_times.png';check(sha(v)==record['video']['sha256'] and sha(f)==record['figure']['sha256'],'media changed')
 science=read(HERE/'incoming/scientific_contract.json');review=read(p/'HUMAN_REVIEW.json') if (p/'HUMAN_REVIEW.json').exists() else {'summary':'视觉核查待完成。'}
 source='source_p0_p1_full87.mp4';paragraph=html.escape(review['summary'])
 prompts=''.join('<details><summary>'+c['prompt_version']+' · '+('原始编辑指令' if c['arm']=='p0' else '此前冻结的 H3 格式提示词')+'</summary><pre>'+html.escape(c['prompt'])+'</pre></details>' for c in science['cases'])
 text='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>H3 提示适配对照</title><style>body{margin:0;background:#0b0c10;color:#eee;padding:24px;font:18px/1.65 system-ui}main{max-width:1800px;margin:auto}h1{font-size:30px}video,img{display:block;width:100%;background:#000;margin:20px 0}pre{white-space:pre-wrap;font:15px/1.6 monospace;background:#161820;padding:20px}details{margin:20px 0}p{color:#c9cbd0}</style><main><h1>H3 · 原始指令与提示适配的对照</h1><p>任务：把原视频中的女性替换为男性。三列依次为参考视频、原始指令编辑、H3 格式提示词编辑。两版使用同一参考视频、种子、采样和初始噪声；保留 87 个有效帧，共 3.625 秒。</p><p>'+paragraph+'</p><video controls preload="metadata" src="data:video/mp4;base64,'+base64.b64encode(v.read_bytes()).decode()+'"></video><h2>6 个固定时刻</h2><img alt="6个均匀时刻的参考、P0和P1对照" src="data:image/png;base64,'+base64.b64encode(f.read_bytes()).decode()+'"><h2>实际提示词</h2>'+prompts+'<p>该实验检查提示适配。适配包含参考标签、源与目标描述、保留要求和分节格式。两版均使用普通 H3 编辑，时序引导调用均为 0。</p></main></html>'
 dest=Path('/Users/researcher/Downloads/H3_IVEBench_P0_P1提示适配对照_20261018.html');dest.write_text(text);video_dest=dest.with_suffix('.mp4');shutil.copy2(v,video_dest)
 save(p/'DELIVERY.json',{'html':bound(dest),'video':bound(video_dest),'embedded_media':{'videos':1,'images':1},'scientific_gate':record['gate'],'human_review':review});return {'html':str(dest),'video':str(video_dest)}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['collect','render','document']);a=p.parse_args();print(json.dumps(globals()[a.action](),default=str,ensure_ascii=False))
