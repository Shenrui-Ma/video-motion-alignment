"""Collect the actual R110 ordinary prompt control and create its three-column comparison."""
import argparse,base64,hashlib,html,json,shutil,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PRODUCER=ROOT.parent/'h3-timing-ive-basketball-boundprompt-r110-20261019'
REMOTE='/data5/researcher/h3_runs/timing_ive_basketball_boundprompt_r110_20261019'
RUN='r110_short_0114_seed2026101701_native'
ATTEMPT='root_boundprompt_attempt1'
INC=ROOT/'incoming';SHOW=ROOT/'showcase';AUDIT=ROOT/'audit'
DOWNLOAD=Path('/Users/researcher/Downloads')
OLD=ROOT.parent/'h3-ive-basketball-shortprompt-metrics-r109-20261019/incoming/plain.mp4'
OLD_SHA='928fc92ff2140b6ff6656b82fa18260a93cdcd78a9111749616f60da7b1e7a94'
SOURCE_SHA='fb72c036dbc574c645531f80b352196f36680875d74a6a5810203702aa58b68f'
TITLE='H3_R110_篮球_简短提示词与显式参考提示词_20261019'
LABELS=['1.参考视频','2.一句话普通编辑','3.显式参考普通编辑']
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
    p=Path(rel);require(not p.is_absolute() and '..' not in p.parts,'unsafe remote relative path')
    dest.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['scp','-q','H3_SERVER_A:'+REMOTE+'/'+rel,str(dest)],check=True,timeout=300)
def validate_gate(gate,complete,released,started):
    require(gate['schema']=='r110-p1-native-runtime-gate-v1' and gate['passed'] is True and all(gate['checks'].values()),'actual gate failed')
    require(gate['run_id']==RUN and gate['valid_frames']==105 and gate['NFE']==20 and gate['routed_blocks']==0,'actual scientific execution differs')
    require(complete['passed'] and complete['jobs']==[RUN] and complete['GPU_released'],'completion differs')
    require(released['passed'] and released['process_absent'] and released['CUDA_allocation_absent'],'exact release pending')
    require(released['owner']==started['owner'],'service generation differs')
    expected=REMOTE+'/output/'+RUN+'_00001_.mp4'
    require(gate['video']['file']==expected,'unexpected video file')
    require(gate['runtime_profile']['gpu_uuid']==started['owner']['gpu_uuid'],'actual device mismatch')
    return expected[len(REMOTE)+1:]
def collect():
    require(not (INC/'COLLECTION.json').exists(),'actual result already collected; use --build-only')
    require(sha(OLD)==OLD_SHA,'actual R109 ordinary video changed')
    source=PRODUCER/'inputs/short_0114_video.mp4';require(sha(source)==SOURCE_SHA,'source changed')
    for name,rel in {'gate.json':'analysis/postrun/NATIVE_RUNTIME_GATE.json','COMPLETE.json':f'audit/{ATTEMPT}/COMPLETE.json','ROOT_EXIT_RECEIPT.json':f'audit/{ATTEMPT}/ROOT_EXIT_RECEIPT.json','STARTED.json':f'audit/{ATTEMPT}/STARTED.json','history.json':f'logs/{RUN}_history.json','job.json':f'logs/{RUN}_job.json','deploy_manifest.json':'deploy_manifest.json'}.items():fetch(rel,INC/name)
    gate=read(INC/'gate.json');complete=read(INC/'COMPLETE.json')
    rel=validate_gate(gate,complete,read(INC/'ROOT_EXIT_RECEIPT.json'),read(INC/'STARTED.json'))
    require(complete['runtime_gate_sha256']==sha(INC/'gate.json'),'gate completion hash differs')
    require(sha(INC/'deploy_manifest.json')==sha(PRODUCER/'deploy_manifest.json'),'producer seal differs')
    h=read(INC/'history.json');job=read(INC/'job.json');graph=read(PRODUCER/'configs/graphs'/f'{RUN}.json')
    require(h['status']['completed'] and h['status']['status_str']=='success' and h['prompt'][2]==graph and h['prompt'][1]==job['prompt_id'],'actual prompt/history differs')
    fetch(rel,INC/'plain.mp4');require(sha(INC/'plain.mp4')==gate['video']['sha256'],'downloaded output hash differs')
    shutil.copy2(OLD,INC/'p1.mp4');shutil.copy2(source,INC/'source.mp4')
    with tempfile.TemporaryDirectory() as temp:
        fresh=Path(temp)/'gate.json';fetch('analysis/postrun/NATIVE_RUNTIME_GATE.json',fresh);require(sha(fresh)==sha(INC/'gate.json'),'gate changed during collection')
    put(INC/'COLLECTION.json',{'passed':True,'files':{p.name:sha(p) for p in INC.iterdir() if p.is_file()},'scope':'Source, actual R109 short ordinary, R110 reference-bound ordinary. Both0guidance.','created_unix':time.time()})
def inspect(path):
    q=json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(path)]))
    s=q['streams'][0];times=[float(f['best_effort_timestamp_time']) for f in q['frames']]
    require(len(q['streams'])==1 and len(times)==107 and s['width']==1312 and s['height']==736 and s['avg_frame_rate']=='24/1','media geometry differs')
    require(all(abs(t-i/24)<1e-6 for i,t in enumerate(times)),'physical PTS differs')
    return {'stream':s,'all107PTS_checked':True,'sha256':sha(path)}
def validate_comparison_time(value):
    s=value['streams'][0];times=[float(f['best_effort_timestamp_time']) for f in value['frames']]
    require(len(value['streams'])==1 and (s['width'],s['height'],s['avg_frame_rate'],len(times))==(3840,808,'24/1',105),'comparison geometry differs')
    require(all(abs(t-i/24)<1e-6 for i,t in enumerate(times)),'comparison physical PTS differs')
    return {**s,'count':len(times),'pts_s':times}
def build():
    from PIL import Image,ImageDraw,ImageFont
    for name,digest in read(INC/'COLLECTION.json')['files'].items():require(sha(INC/name)==digest,'collected file changed: '+name)
    SHOW.mkdir(parents=True,exist_ok=True);AUDIT.mkdir(parents=True,exist_ok=True)
    keys=['source','p1','plain'];properties={k:inspect(INC/(k+'.mp4')) for k in keys}
    label_font=ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc',30)
    cap=Image.new('RGB',(3840,88),'black');draw=ImageDraw.Draw(cap)
    draw.text((20,10),'主体编辑',font=label_font,fill='#d8d8d8')
    for i,label in enumerate(LABELS):draw.text((i*1280+640,43),label,font=label_font,fill='white',anchor='mm')
    cap.save(SHOW/'caption.png')
    video=SHOW/'source_p1_plain_full_valid.mp4'
    if not video.exists():
        cmd=['/opt/homebrew/bin/ffmpeg','-v','error','-y']
        for k in keys:cmd+=['-threads','1','-i',str(INC/(k+'.mp4'))]
        cmd+=['-loop','1','-framerate','24','-i',str(SHOW/'caption.png'),'-filter_complex',';'.join([f'[{i}:v]trim=end_frame=105,setpts=PTS-STARTPTS,crop=1280:720:16:8[v{i}]' for i in range(3)])+';[v0][v1][v2]hstack=inputs=3[top];[top][3:v]vstack=inputs=2[out]','-map','[out]','-an','-frames:v','105','-r','24','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-threads','4','-movflags','+faststart',str(video)]
        subprocess.run(cmd,check=True,timeout=600)
    ff=validate_comparison_time(json.loads(subprocess.check_output(['/opt/homebrew/bin/ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,avg_frame_rate:frame=best_effort_timestamp_time','-of','json',str(video)])))
    # Full-frame evidence keeps every valid physical frame in the same row.
    W,H=480,270;frames={}
    for k in keys:
        raw=subprocess.check_output(['/opt/homebrew/bin/ffmpeg','-v','error','-threads','1','-i',str(INC/(k+'.mp4')),'-an','-vf',f'crop=1280:720:16:8,scale={W}:{H}:flags=lanczos','-frames:v','105','-threads','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
        size=W*H*3;require(len(raw)==105*size,'decoded evidence frame count differs');frames[k]=[Image.frombytes('RGB',(W,H),raw[i*size:(i+1)*size]) for i in range(105)]
    font=ImageFont.truetype('/System/Library/Fonts/Menlo.ttc',17);pages=[]
    for start in range(0,105,6):
        stop=min(start+6,105);im=Image.new('RGB',(1440,(H+28)*(stop-start)+30),'#0c0d10');d=ImageDraw.Draw(im)
        for col,label in enumerate(['SOURCE','SHORT PROMPT','REFERENCE-BOUND PROMPT']):d.text((col*W+8,5),label,font=font,fill='white')
        for row,i in enumerate(range(start,stop)):
            y=30+row*(H+28);d.text((8,y+3),f'Frame {i:03d} | {i/24:.3f}s',font=font,fill='#eadca1')
            for col,k in enumerate(keys):im.paste(frames[k][i],(col*W,y+28))
        path=SHOW/f'frames_{start:03d}-{stop-1:03d}.jpg';im.save(path,quality=94);pages.append({'file':str(path),'frames':list(range(start,stop)),'sha256':sha(path)})
    uri=lambda p,m:'data:'+m+';base64,'+base64.b64encode(Path(p).read_bytes()).decode()
    pictures=''.join('<details><summary>帧 '+str(p['frames'][0])+'–'+str(p['frames'][-1])+'</summary><img src="'+uri(p['file'],'image/jpeg')+'"></details>' for p in pages)
    document='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>篮球提示词对照</title><style>body{background:#101114;color:#eee;font-family:system-ui;margin:24px auto;max-width:1600px;padding:0 20px;line-height:1.65}video,img{width:100%;background:#000}p{max-width:1050px}details{margin:16px 0}code{color:#cbd9ff}</style><h1>篮球替换：一句话提示词与明确绑定原视频的提示词</h1><p>任务：将篮球替换为霓虹发光篮球，保留球员、运球动作与原球场构图。左：参考视频；中：R109一句话提示词普通编辑；右：R110明确绑定原视频的普通编辑。</p><p>新提示词：<code>Edit &lt;Video 1&gt; by changing only the basketball into a neon-lit basketball. Keep the original player, dribbling actions, camera framing, scene, and timing.</code></p><p>同一参考输入、种子、原始噪声、模型和20步Euler；两版均为普通编辑。全105有效帧，24fps，三列按相同物理时刻展示。两次均使用.9 GPU3。检查球的外观、人物裁切、相机俯仰及运球顺序。</p><video controls loop playsinline preload="metadata" src="'''+uri(video,'video/mp4')+'"></video><p>完整逐帧对照：</p>'+pictures+'</html>'
    output=DOWNLOAD/(TITLE+'.html');output.write_text(document);movie=DOWNLOAD/(TITLE+'.mp4');shutil.copy2(video,movie)
    put(SHOW/'PRESENTATION.json',{'input_properties':properties,'comparison':{'file':str(video),'sha256':sha(video),'properties':ff},'valid_frames':105,'fps':24,'column_order':keys,'column_labels':LABELS,'crop_xywh':[16,8,1280,720],'all_frame_pages':pages,'html':str(output),'html_sha256':sha(output),'download_video':str(movie),'evidence_gate_sha256':sha(INC/'gate.json'),'visual_review':'pending'})
    print(json.dumps({'html':str(output),'video':str(movie),'pages':len(pages),'valid_frames':105},ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build-only',action='store_true');args=p.parse_args()
    if not args.build_only:collect()
    build()
