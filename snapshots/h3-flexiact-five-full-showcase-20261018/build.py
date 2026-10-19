"""Publish only verified completed FlexiAct outputs as full synchronized comparisons."""
import base64,datetime,hashlib,html,json,subprocess,time
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
B=Path(__file__).resolve().parent
D=Path('/Users/researcher/Downloads')
N=Path('/Users/researcher/DevProjects/h3-timing-flexiact-native-r49-20261017/analysis/postrun/captured/batch')
A=Path('/Users/researcher/DevProjects/h3-timing-flexiact-auto-r50-retry-20261017/analysis/postrun/completed_cases/r50_source_chest_seed2026101701_auto')
AUD=Path('/Users/researcher/DevProjects/h3-timing-flexiact-auto-r50-retry-20261017/analysis/postrun/audit/media_identity/chest/SUMMARY.json')
FONT='/System/Library/Fonts/Supplemental/Songti.ttc'
FF='/opt/homebrew/bin/ffmpeg';FP='/opt/homebrew/bin/ffprobe'
IDS=['chest','crouch','fitness','one_leg','rotate']
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x): p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def bind(p): return {'file':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
def probe(p): return json.loads(subprocess.check_output([FP,'-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,avg_frame_rate,duration','-of','json',str(p)]))['streams'][0]
for name in ['audit','captions','posters']:(B/name).mkdir(exist_ok=True)
records=[]
media=json.loads(AUD.read_text());assert media['proofs']['full158_output']['exact'] is True
for ident in IDS:
 run=f'r49_source_{ident}_seed2026101701_native'
 summary=N/'final'/run/'SUMMARY.json';s=json.loads(summary.read_text());assert s['passed'] is True
 native=N/'output'/Path(s['video']).name;source=N/'inputs'/f'source_{ident}_video.mp4'
 assert sha(native)==s['video_sha256'] and sha(source)==s['source_video_sha256']
 paths=[source,native];evidence=[summary]
 labels=['1. 参考视频','2. 普通编辑视频']
 status='普通编辑已完成；自动干预成片待完成。'
 if ident=='crouch':status='普通编辑已完成；自动运行在第15次观察前因技术故障结束，干预成片待完成。'
 if ident=='chest':
  q=A/'final/r50_source_chest_seed2026101701_auto/SUMMARY.json';v=json.loads(q.read_text());assert v['passed'] is True and v['actual_routed_blocks']==0 and v['active_denoising_indices']==[]
  assert v['observations_replayed']==20
  auto=A/'output'/Path(v['video']).name;assert sha(auto)==v['video_sha256'];paths.append(auto);evidence.extend([q,AUD])
  labels.append('3. 自动策略（本例未触发干预）')
  status='自动策略已完成：20次观察均未触发干预，成片与普通编辑逐帧相同。'
 for p in paths:
  x=probe(p);assert [x['width'],x['height'],int(x['nb_frames']),x['avg_frame_rate']]==[1152,768,158,'24/1'],(p,x)
 out=D/f'FlexiAct_{ident}_完整{len(paths)}栏对比_20261018.mp4'
 assert not out.exists(),out
 filters=[]
 for i in range(len(paths)):filters.append(f'[{i}:v:0]setpts=PTS-STARTPTS,setsar=1[v{i}]')
 filters.append(''.join(f'[v{i}]' for i in range(len(paths)))+f'hstack=inputs={len(paths)}:shortest=1[content]')
 bar=B/'captions'/f'{ident}.png';im=Image.new('RGB',(1152*len(paths),92),'black');draw=ImageDraw.Draw(im);font=ImageFont.truetype(FONT,34);small=ImageFont.truetype(FONT,28)
 for i,label in enumerate(labels):
  text=B/'captions'/f'{ident}_{i}.txt';text.write_text(label)
  draw.text((i*1152+576,46),label,fill='white',font=font,anchor='mm')
 draw.text((20,46),'角色替换',fill='#bbbbbb',font=small,anchor='lm');im.save(bar)
 filters.append(f'[content][{len(paths)}:v]vstack=inputs=2:shortest=1[out]')
 cmd=[FF,'-v','error','-filter_complex_threads','2']
 for p in paths:cmd+=['-threads','2','-i',str(p)]
 cmd+=['-loop','1','-framerate','24','-i',str(bar),'-filter_complex',';'.join(filters),'-map','[out]','-an','-frames:v','147','-r','24','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-threads','2','-movflags','+faststart',str(out)]
 start=time.monotonic();subprocess.run(cmd,check=True,timeout=180)
 x=probe(out);assert int(x['nb_frames'])==147 and x['avg_frame_rate']=='24/1' and x['width']==1152*len(paths) and x['height']==860
 poster=B/'posters'/f'{ident}.jpg'
 subprocess.run([FF,'-y','-v','error','-threads','2','-i',str(out),'-vf',r'select=eq(n\,48)','-frames:v','1','-q:v','2',str(poster)],check=True,timeout=30)
 record={'source_id':ident,'columns':labels,'status':status,'source_and_completed_outputs':[bind(p) for p in paths],'completion_evidence':[bind(p) for p in evidence],'output':bind(out),'poster':bind(poster),'probe':x,'presentation':{'frames':147,'fps':24,'source_input_padding_frames':11,'full_native_output_included':False,'full_official_source_content_included':True,'archived_native_frames':158,'input_padding_excluded_from_presentation':True,'spatial_crop':None,'spatial_rescale':None,'time_shift_frames':0,'audio':'muted comparison','caption_canvas_height':92},'command':cmd,'seconds':time.monotonic()-start}
 records.append(record);write(B/'audit'/f'{ident}.json',record);print(ident,'ready',out.stat().st_size,flush=True)
write(B/'MEDIA_MANIFEST.json',{'schema':'flexiact-completed-five-showcase-v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'native_completed':5,'auto_completed':1,'auto_completed_ids':['chest'],'auto_pending_ids':['crouch','fitness','one_leg','rotate'],'cases':records})
sections=[]
for index,r in enumerate(records,1):
 id=r['source_id'];v='data:video/mp4;base64,'+base64.b64encode(Path(r['output']['file']).read_bytes()).decode();poster='data:image/jpeg;base64,'+base64.b64encode(Path(r['poster']['file']).read_bytes()).decode()
 sections.append(f'''<section id="{id}" class="case"><div class="heading"><h2><span>{index:02}</span> {html.escape(id)}</h2><p class="state {'done' if id=='chest' else ''}">{html.escape(r['status'])}</p></div><video controls playsinline preload="metadata" poster="{poster}" src="{v}"></video><div class="actions"><button onclick="slow(this)">0.5× 慢放</button><button onclick="full(this)">全屏查看</button><a download="{Path(r['output']['file']).name}" onclick="this.href=this.closest('section').querySelector('video').src">下载本组完整横拼视频</a><span>{len(r['columns'])}栏 · 6.125秒</span></div></section>''')
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FlexiAct｜五组完整视频对照</title><style>
:root{color-scheme:dark;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;background:#070809;color:#eee}*{box-sizing:border-box}body{margin:0}main{max-width:1920px;margin:auto;padding:40px 32px 72px}header{margin-bottom:34px}h1{font-size:clamp(25px,3vw,39px);letter-spacing:-.8px;margin:10px 0 16px;font-weight:650}.eyebrow{color:#a6b0ba;font-size:13px;letter-spacing:1.5px}p{color:#aeb4bd;line-height:1.65;margin:6px 0}.summary{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}.summary b{color:#eee;font-size:21px}.summary div{padding:12px 18px;border:1px solid #2b3036;border-radius:10px;color:#aeb4bd}nav{display:flex;gap:18px;margin:22px 0 0;flex-wrap:wrap}a{color:#c7d8ee;text-decoration:none;cursor:pointer}a:hover{text-decoration:underline}.case{margin:36px 0 60px;border-top:1px solid #30343a;padding-top:22px}.heading{display:flex;align-items:baseline;justify-content:space-between;gap:20px;margin-bottom:16px}h2{font-size:23px;margin:0;font-weight:600}h2 span{font-size:13px;color:#838d99;margin-right:12px}.state{font-size:14px;max-width:820px}.done{color:#b7ccb9}video{display:block;width:100%;height:auto;background:#000;border:1px solid #24272c}.actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:12px;font-size:13px}.actions span{color:#89929c;margin-left:auto}button,.actions a{background:#15191e;border:1px solid #303740;border-radius:7px;color:#d7dfe9;font:inherit;padding:9px 13px}button{cursor:pointer}button:hover,.actions a:hover{background:#222932;text-decoration:none}footer{border-top:1px solid #30343a;padding-top:20px;color:#929ba7;font-size:13px;line-height:1.7}@media(max-width:750px){main{padding:24px 12px 40px}.heading{display:block}.state{margin-top:10px}.actions span{margin-left:0}.summary div{padding:9px 12px}}
</style><main><header><div class="eyebrow">H3 · FLEXIACT · 2026.10.18</div><h1>五组完整视频对照</h1><p>参考动作、普通编辑，以及已完成的自动策略成片。</p><div class="summary"><div><b>5 / 5</b> 普通编辑已完成</div><div><b>1 / 5</b> 自动策略成片已完成</div><div><b>0</b> chest 实际干预次数</div></div><p>chest 的自动策略全程未触发干预，与普通编辑的成片逐帧相同。其余4条干预成片待完成。</p><nav>'''+''.join(f'<a href="#{x}">{i+1:02} {x}</a>' for i,x in enumerate(IDS))+'''</nav></header>'''+''.join(sections)+'''<footer>视频和封面已嵌入此 HTML，可单独转发。各栏同步播放完整有效片段（6.125秒）。参考视频原帧率为8fps，按每个原帧重复3次显示为24fps。<br>本页归档：普通编辑5条、自动策略1条。下蹲（crouch）的先前运行因技术故障结束，其余自动成片仍待完成。</footer></main><script>
function slow(b){let v=b.closest('section').querySelector('video');v.playbackRate=v.playbackRate===.5?1:.5;b.textContent=v.playbackRate===.5?'1× 正常速度':'0.5× 慢放';v.play()}
function full(b){let v=b.closest('section').querySelector('video');if(v.requestFullscreen)v.requestFullscreen();else if(v.webkitEnterFullscreen)v.webkitEnterFullscreen()}
document.querySelectorAll('video').forEach(v=>v.addEventListener('play',()=>document.querySelectorAll('video').forEach(o=>{if(o!==v)o.pause()})));
</script></html>'''
output=D/'FlexiAct_五组完整视频对照_20261018_单文件.html';assert not output.exists();output.write_text(page)
write(B/'DELIVERY.json',{'html':bind(output),'mp4':[r['output'] for r in records],'media_manifest':bind(B/'MEDIA_MANIFEST.json'),'native_completed':5,'auto_completed':1})
print('HTML',output,output.stat().st_size,flush=True)
