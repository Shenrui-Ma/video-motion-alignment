"""Collect two actual fresh ordinary solver runs and make a local single-file comparison."""
import argparse,base64,hashlib,html,json,shutil,subprocess,tempfile,time,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PRODUCER=ROOT.parent/'h3-timing-sampler-control-r106-20261019'
REMOTE='/home/researcher/h3_runs/timing_sampler_control_r106_20261019'
ARMS=('euler','res_multistep')
RUNS=['r106_short_0252_seed2026101701_'+a for a in ARMS]
INC=ROOT/'incoming';SHOW=ROOT/'showcase';AUDIT=ROOT/'audit'
DOWNLOAD=Path('/Users/researcher/Downloads')
SOURCE_SHA='1cb246924154d0344a7d198436477cad0b3af533f5297ebbcebf3f5f990c32d5'
TITLE='H3_R106_机舱人物替换_Euler与res_multistep_20261019'
LABELS=['1.参考视频','2.Euler普通编辑','3.res_multistep普通编辑']
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def require(ok,msg):
 if not ok:raise ValueError(msg)
def fetch(rel,dest):
 p=Path(rel);require(not p.is_absolute() and '..' not in p.parts,'unsafe remote relative path');dest.parent.mkdir(parents=True,exist_ok=True)
 subprocess.run(['scp','-q','H3_SERVER_A:'+REMOTE+'/'+rel,str(dest)],check=True,timeout=300)
def validate_gate(gate,complete,released,started):
 require(gate['schema']=='r106-fresh-native-solver-pair-runtime-gate-v1' and gate['passed'] is True and bool(gate['checks']) and all(v is True for v in gate['checks'].values()),'actual gate failed')
 require(gate['source_id']=='short_0252' and gate['valid_frames']==98 and gate['evaluation_indices']==list(range(98)) and gate['frame_rate']==24 and gate['evaluation_crop_xywh']==[16,8,1280,720],'scientific geometry differs')
 require(complete['passed'] is True and complete['jobs']==RUNS and complete['GPU_released'] is True,'completion differs')
 require(released['passed'] is True and released['process_absent'] is True and released['CUDA_allocation_absent'] is True,'exact release pending')
 require(released['owner']==started['owner']==gate['service_owner'],'service generation differs')
 require(set(gate['runs'])==set(ARMS) and gate['equal_prefix_steps']==[0,1],'solver registry/prefix differs')
 require(gate['runtime_profile']['remote_root']==REMOTE and gate['runtime_profile']['gpu_uuid']==started['owner']['gpu_uuid'],'actual runtime differs')
 results={}
 for arm,run in zip(ARMS,RUNS):
  value=gate['runs'][arm]
  require(value['run_id']==run and value['solver']==arm and value['sampler_function']=='sample_'+arm and value['NFE']==value['solver_updates']==20 and value['routed_blocks']==0 and value['valid_frames']==98,'solver execution differs')
  for step in (0,1):
   for kind,keys in [('raw',('state_video','state_audio','prediction_video','prediction_audio')),('normalized',('video','audio'))]:
    for key in keys:require(gate['checks'].get(f'step{step}_{kind}_{key}') is True,'actual prefix equality missing')
  file=Path(value['video']['file']);base=Path(REMOTE)/'output';require(file.is_relative_to(base) and '..' not in file.parts and file.suffix=='.mp4' and file.name.startswith(run+'_'),'unsafe actual video')
  results[arm]=str(file.relative_to(Path(REMOTE)))
 return results

def collect(attempt):
 require(re.fullmatch(r'[A-Za-z0-9_-]+',attempt) is not None,'unsafe actual attempt')
 require(not (INC/'COLLECTION.json').exists(),'already collected; use build-only')
 frozen=read(ROOT/'CONSUMER_FREEZE.json')
 for path,row in frozen['files'].items():require(sha(ROOT/path)==row['sha256'],'consumer changed')
 source=PRODUCER/'inputs/short_0252_video.mp4';require(sha(source)==SOURCE_SHA,'source changed')
 files={'gate.json':'analysis/postrun/PAIR_RUNTIME_GATE.json','COMPLETE.json':f'audit/{attempt}/COMPLETE.json','ROOT_EXIT_RECEIPT.json':f'audit/{attempt}/ROOT_EXIT_RECEIPT.json','STARTED.json':f'audit/{attempt}/STARTED.json','deploy_manifest.json':'deploy_manifest.json'}
 for arm,run in zip(ARMS,RUNS):
  files[arm+'_history.json']=f'logs/{run}_history.json';files[arm+'_job.json']=f'logs/{run}_job.json'
 for name,rel in files.items():fetch(rel,INC/name)
 gate=read(INC/'gate.json');complete=read(INC/'COMPLETE.json');started=read(INC/'STARTED.json')
 rels=validate_gate(gate,complete,read(INC/'ROOT_EXIT_RECEIPT.json'),started)
 require(complete['runtime_gate_sha256']==sha(INC/'gate.json'),'completion gate hash differs')
 require(sha(INC/'deploy_manifest.json')==sha(PRODUCER/'deploy_manifest.json')==gate['producer_seal_sha256']==frozen['producer_seal_sha256'],'producer seal differs')
 for arm,run in zip(ARMS,RUNS):
  h=read(INC/(arm+'_history.json'));j=read(INC/(arm+'_job.json'));g=read(PRODUCER/'configs/graphs'/(run+'.json'))
  require(h['status']['completed'] is True and h['status']['status_str']=='success' and h['prompt'][2]==g and h['prompt'][1]==j['prompt_id'] and j['status']=='success' and j['service_pid']==started['owner']['pid'] and j['service_identity']==started['owner']['identity'],'actual history/generation differs')
  require(sha(INC/(arm+'_history.json'))==gate['runs'][arm]['history_sha256'],'history gate binding differs')
  fetch(rels[arm],INC/(arm+'.mp4'));require(sha(INC/(arm+'.mp4'))==gate['runs'][arm]['video']['sha256'],'downloaded output differs')
 shutil.copy2(source,INC/'source.mp4')
 with tempfile.TemporaryDirectory() as d:
  p=Path(d)/'gate.json';fetch('analysis/postrun/PAIR_RUNTIME_GATE.json',p);require(sha(p)==sha(INC/'gate.json'),'gate changed during collection')
 put(INC/'COLLECTION.json',{'passed':True,'attempt':attempt,'files':{p.name:sha(p) for p in INC.iterdir() if p.is_file()},'consumer_freeze_sha256':sha(ROOT/'CONSUMER_FREEZE.json'),'scope':'Source plus two fresh ordinary solver edits.','created_unix':time.time()})

def prepare_mf_inputs():
 files={}
 for key in ('source',)+ARMS:
  p=ROOT/'prepared'/(key+'.mp4');p.parent.mkdir(exist_ok=True)
  if not p.exists():subprocess.run(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',str(INC/(key+'.mp4')),'-an','-vf','trim=end_frame=98,setpts=PTS-STARTPTS,crop=1280:720:16:8','-frames:v','98','-r','24','-c:v','libx264','-crf','0','-preset','fast','-pix_fmt','yuv420p','-threads','2',str(p)],check=True,timeout=300)
  def md5(path,filtered):
   cmd=['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',str(path),'-an']
   if filtered:cmd+=['-vf','trim=end_frame=98,crop=1280:720:16:8']
   cmd+=['-frames:v','98','-threads','1','-f','framemd5','-']
   return [line.rsplit(',',1)[1].strip() for line in subprocess.check_output(cmd,text=True).splitlines() if line and not line.startswith('#')]
  hashes=md5(p,False);require(len(hashes)==98 and hashes==md5(INC/(key+'.mp4'),True),'metric crop must preserve exact decoded pixels')
  files[key]={'file':str(p),'sha256':sha(p),'frame_count':98,'fps':24,'decoded_frame_md5':hashes}
 put(ROOT/'prepared/MF_INPUTS.json',{'schema':'r106-official-ive-mf-inputs-v1','benchmark':'IVEBench','grid_size':10,'frame_count':98,'fps':24,'crop_xywh':[16,8,1280,720],'files':files,'actual_gate_sha256':sha(INC/'gate.json'),'collection_sha256':sha(INC/'COLLECTION.json'),'status':'READY_FOR_OFFICIAL_TRACKER_BINDING','scores':None})
def inspect(path):
    q=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(path)]))
    s=q['streams'][0];times=[float(f['best_effort_timestamp_time']) for f in q['frames']]
    require(len(q['streams'])==1 and len(times)==107 and s['width']==1312 and s['height']==736 and s['avg_frame_rate']=='24/1','media geometry differs')
    require(all(abs(t-i/24)<1e-6 for i,t in enumerate(times)),'physical PTS differs')
    return {'stream':s,'all107PTS_checked':True,'sha256':sha(path)}
def validate_comparison_time(value):
    s=value['streams'][0];times=[float(f['best_effort_timestamp_time']) for f in value['frames']]
    require(len(value['streams'])==1 and (s['width'],s['height'],s['avg_frame_rate'],len(times))==(3840,808,'24/1',98),'comparison geometry differs')
    require(all(abs(t-i/24)<1e-6 for i,t in enumerate(times)),'comparison physical PTS differs')
    return {**s,'count':len(times),'pts_s':times}
def validate_collected():
    collection=read(INC/'COLLECTION.json');require(collection['passed'] is True,'collection failed')
    frozen=read(ROOT/'CONSUMER_FREEZE.json');require(collection['consumer_freeze_sha256']==sha(ROOT/'CONSUMER_FREEZE.json'),'consumer freeze changed')
    for path,row in frozen['files'].items():require(sha(ROOT/path)==row['sha256'],'consumer changed')
    for name,digest in collection['files'].items():require(sha(INC/name)==digest,'collected file changed')
    gate=read(INC/'gate.json');complete=read(INC/'COMPLETE.json')
    validate_gate(gate,complete,read(INC/'ROOT_EXIT_RECEIPT.json'),read(INC/'STARTED.json'))
    require(complete['runtime_gate_sha256']==sha(INC/'gate.json'),'collected gate differs')
    require(sha(INC/'deploy_manifest.json')==sha(PRODUCER/'deploy_manifest.json')==frozen['producer_seal_sha256']==gate['producer_seal_sha256'],'producer seal changed')

def build():
    validate_collected()
    from PIL import Image,ImageDraw,ImageFont
    for name,digest in read(INC/'COLLECTION.json')['files'].items():require(sha(INC/name)==digest,'collected file changed: '+name)
    SHOW.mkdir(parents=True,exist_ok=True);AUDIT.mkdir(parents=True,exist_ok=True)
    keys=['source','euler','res_multistep'];properties={k:inspect(INC/(k+'.mp4')) for k in keys}
    label_font=ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc',30)
    cap=Image.new('RGB',(3840,88),'black');draw=ImageDraw.Draw(cap)
    draw.text((20,10),'主体编辑',font=label_font,fill='#d8d8d8')
    for i,label in enumerate(LABELS):draw.text((i*1280+640,43),label,font=label_font,fill='white',anchor='mm')
    cap.save(SHOW/'caption.png')
    video=SHOW/'source_euler_res_multistep_full_valid.mp4'
    if not video.exists():
        cmd=['/opt/homebrew/bin/ffmpeg','-v','error','-y']
        for k in keys:cmd+=['-threads','1','-i',str(INC/(k+'.mp4'))]
        cmd+=['-loop','1','-framerate','24','-i',str(SHOW/'caption.png'),'-filter_complex',';'.join([f'[{i}:v]trim=end_frame=98,setpts=PTS-STARTPTS,crop=1280:720:16:8[v{i}]' for i in range(3)])+';[v0][v1][v2]hstack=inputs=3[top];[top][3:v]vstack=inputs=2[out]','-map','[out]','-an','-frames:v','98','-r','24','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-threads','4','-movflags','+faststart',str(video)]
        subprocess.run(cmd,check=True,timeout=600)
    ff=validate_comparison_time(json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(video)])))
    # Full-frame evidence keeps every valid physical frame in the same row.
    W,H=480,270;frames={}
    for k in keys:
        raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',str(INC/(k+'.mp4')),'-an','-vf',f'crop=1280:720:16:8,scale={W}:{H}:flags=lanczos','-frames:v','98','-threads','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
        size=W*H*3;require(len(raw)==98*size,'decoded evidence frame count differs');frames[k]=[Image.frombytes('RGB',(W,H),raw[i*size:(i+1)*size]) for i in range(98)]
    font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',17);pages=[]
    for start in range(0,98,6):
        stop=min(start+6,98);im=Image.new('RGB',(1440,(H+28)*(stop-start)+30),'#0c0d10');d=ImageDraw.Draw(im)
        for col,label in enumerate(['SOURCE','EULER','RES MULTISTEP']):d.text((col*W+8,5),label,font=font,fill='white')
        for row,i in enumerate(range(start,stop)):
            y=30+row*(H+28);d.text((8,y+3),f'Frame {i:03d} | {i/24:.3f}s',font=font,fill='#eadca1')
            for col,k in enumerate(keys):im.paste(frames[k][i],(col*W,y+28))
        path=SHOW/f'frames_{start:03d}-{stop-1:03d}.jpg';im.save(path,quality=94);pages.append({'file':str(path),'frames':list(range(start,stop)),'sha256':sha(path)})
    uri=lambda p,m:'data:'+m+';base64,'+base64.b64encode(Path(p).read_bytes()).decode()
    pictures=''.join('<details><summary>帧 '+str(p['frames'][0])+'–'+str(p['frames'][-1])+'</summary><img src="'+uri(p['file'],'image/jpeg')+'"></details>' for p in pages)
    document='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>H3 采样器对照</title><style>body{background:#101114;color:#eee;font-family:system-ui;margin:24px auto;max-width:1800px;padding:0 20px;line-height:1.65}video,img{width:100%;background:#000}p{max-width:1100px}details{margin:16px 0}</style><h1>机舱人物替换：Euler 与 res_multistep</h1><p>任务：将手持氧气面罩的男人替换为年长女人，保留男孩、机舱和原动作。左：参考视频；中：Euler 普通编辑；右：res_multistep 普通编辑。</p><p>两版使用相同原始噪声、参考条件、完整提示词和 20 步 ManualSigmas，均执行普通编辑。展示全部 98 个有效帧，24fps；三列对应同一物理时刻。实际执行记录保存前两步原始状态与预测的一致性证据，以及后续采样器产生的自然差异。</p><video controls loop playsinline preload="metadata" src="'+uri(video,'video/mp4')+'"></video><p>完整逐帧对照：</p>'+pictures+'</html>'
    output=DOWNLOAD/(TITLE+'.html');output.write_text(document);movie=DOWNLOAD/(TITLE+'.mp4');shutil.copy2(video,movie)
    put(SHOW/'PRESENTATION.json',{'input_properties':properties,'comparison':{'file':str(video),'sha256':sha(video),'properties':ff},'valid_frames':98,'fps':24,'column_order':keys,'column_labels':LABELS,'crop_xywh':[16,8,1280,720],'all_frame_pages':pages,'html':str(output),'html_sha256':sha(output),'download_video':str(movie),'evidence_gate_sha256':sha(INC/'gate.json'),'visual_review':'pending'})
    prepare_mf_inputs()
    print(json.dumps({'html':str(output),'video':str(movie),'pages':len(pages),'valid_frames':98},ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--build-only',action='store_true');p.add_argument('--attempt');a=p.parse_args()
 if not a.build_only:
  require(a.attempt is not None,'actual completed attempt required');collect(a.attempt)
 build()
