"""Same-frame presentation, all97-frame review ledger and official-MF inputs."""
import base64,html,subprocess,time
from common import *
import render_media,full_frame_review
FFMPEG='/opt/homebrew/bin/ffmpeg';FFPROBE='/opt/homebrew/bin/ffprobe'
def decoded_hash(path,cropped=False,frames=97):
 filters=('crop=1280:720:16:8,' if cropped else '')+f'trim=start_frame=0:end_frame={frames},format=rgb24'
 out=subprocess.check_output([FFMPEG,'-v','error','-threads','1','-i',str(path),'-vf',filters,'-an','-f','hash','-hash','sha256','-'],text=True,timeout=180).strip()
 require(out.startswith('SHA256='),'decoded pixel hash absent');return out[7:]
def event_template(ledger):
 old=read(ROOT/'configs/HISTORICAL_NATIVE_REVIEW.json')
 return dict(schema='r118-full97-review-v1',all_frames_inspected=False,viewed_frame_indices=[],frame_ledger=bound(ledger),valid_frames=97,fps=24,historical_annotations=bound(ROOT/'configs/HISTORICAL_NATIVE_REVIEW.json'),annotation_scope='Source and Native intervals inherited from historical R96 visual review; new guided fields await actual full97 review.',task_success={'native_historical':old['task_success'],'forced':{'identity':None,'scene':None,'motion_content':None,'other_changes':None}},events=[dict(event=e['event'],reference_boundary_frames=e['reference_prepared_boundary_frames'],native_historical_boundary_frames=e['native_boundary_frames'],forced_boundary_frames=None,forced_status='PENDING',boundary_uncertainty='visual annotation range; not a confidence interval') for e in old['events']],overall_timing=None)
def publish(show):
 m=read(show/'PRESENTATION.json');video=show/m['videos'][0]['file'];require(sha(video)==m['videos'][0]['sha256'],'presentation changed');uri='data:video/mp4;base64,'+base64.b64encode(video.read_bytes()).decode();p=read(ROOT/'configs/scientific_contract.json')['cases'][0]
 text=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>R118 采访人物替换</title><style>body{{max-width:1800px;margin:32px auto;background:#101010;color:#eee;font:18px system-ui;padding:0 16px}}video{{width:100%}}p{{line-height:1.6}}</style><h1>IVEBench · 采访人物替换</h1><p>任务：将采访男子替换为女子，保持采访场景与手势。输入为参考视频。</p><video controls loop playsinline src="{uri}"></video><p>1.参考视频　2.普通编辑（既有 R96）　3.时序引导（R118）</p><p>完整有效 97 帧，同帧对照，24fps。时序引导在去噪步骤索引 6–14 执行。生成视频、全部逐帧截图及测量记录分别归档。</p><details><summary>提示词</summary><pre style="white-space:pre-wrap">{html.escape(p['prompt'])}</pre></details></html>'''
 out=show/'index.html'
 if not out.exists():out.write_text(text)
 return bound(out)
def prepare(incoming):
 c=verify_static();verify_collection(incoming);show=ROOT/'showcase/long_0047';inputs=[incoming/(x+'.mp4') for x in ('source','native','forced')]
 if not show.exists():
  stage=ROOT/'audit'/('render_'+str(time.time_ns()));stage.mkdir(parents=True);media=render_media.render_files(inputs,stage,107,97,render_media.choose_font(),FFMPEG,FFPROBE)
  save(stage/'PRESENTATION.json',dict(schema='r118-presentation-v1',columns=['source','native','forced'],collection=bound(incoming/'COLLECTION.json'),gate=bound(incoming/'PAIR_RUNTIME_GATE.json'),valid_frames=97,total_frames=107,fps=24,crop_xywh=[16,8,1280,720],historical_native=c['expected_historical_native'],**media));show.parent.mkdir(exist_ok=True);stage.rename(show)
 m=read(show/'PRESENTATION.json');require(m['collection']==bound(incoming/'COLLECTION.json'),'presentation collection differs')
 for v in m['videos']+m['contact_sheets']:require(sha(show/v['file'])==v['sha256'],'presentation artifact differs')
 review=ROOT/'audit/full97_review';ledger=review/'FRAME_LEDGER.json'
 if not ledger.exists():
  pages=full_frame_review.render_files(inputs,review,107,97,render_media.choose_font(),FFMPEG,FFPROBE);save(ledger,dict(valid_frames=97,fps=24,collection=bound(incoming/'COLLECTION.json'),pages=pages,all_frames_prepared=True,all_frames_inspected=False))
 else:
  r=read(ledger);require(r['collection']==bound(incoming/'COLLECTION.json'),'review belongs to other collection')
  for page in r['pages']:require(sha(review/page['file'])==page['sha256'],'review page changed')
 if not (review/'REVIEW_TEMPLATE.json').exists():save(review/'REVIEW_TEMPLATE.json',event_template(ledger))
 dest=ROOT/'prepared/long_0047';manifest=dest/'MF_INPUTS.json'
 if not manifest.exists():
  dest.mkdir(parents=True,exist_ok=True);roles={}
  for role,inp in zip(('source','native','forced'),inputs):
   out=dest/(role+'_score.mp4');require(not out.exists(),'partial MF input exists; preserve for review')
   subprocess.run([FFMPEG,'-v','error','-nostdin','-n','-threads','2','-i',str(inp),'-vf','crop=1280:720:16:8,trim=start_frame=0:end_frame=97,setpts=PTS-STARTPTS','-an','-fps_mode','vfr','-c:v','libx264rgb','-crf','0','-preset','fast','-pix_fmt','rgb24','-threads','2',str(out)],check=True,timeout=240)
   props=render_media.media_info(out,FFPROBE);render_media.check_time(props,97,1280,720);pixels=decoded_hash(inp,True);require(decoded_hash(out)==pixels,'MF pixels differ from exact cropped valid prefix');roles[role]=dict(raw_video=bound(inp),score_video=bound(out),evaluation_indices=list(range(97)),fps=24,properties=props,decoded_rgb_sha256=pixels)
  save(manifest,dict(schema='r118-official-IVE-MF-inputs-v1',benchmark='IVEBench',source_id='long_0047',valid_frames=97,evaluation_fps=24,crop_xywh=[16,8,1280,720],pair_gate=bound(incoming/'PAIR_RUNTIME_GATE.json'),source_provenance=bound(ROOT/c['provenance']['file']),roles=roles,official_protocol='CoTracker3 offline, grid10, window60; preserve official MF implementation',score_state='PENDING_GPU_ALLOCATION',cache_policy='Reuse source and historical Native tracks only on identical score pixels/timebase/checkpoint/protocol binding. Preserve runtime provenance.'))
 else:
  m=read(manifest);require(m['pair_gate']==bound(incoming/'PAIR_RUNTIME_GATE.json'),'MF domain differs')
  for v in m['roles'].values():require(sha(v['score_video']['file'])==v['score_video']['sha256'],'MF media changed')
 return dict(presentation=bound(show/'PRESENTATION.json'),html=publish(show),full97_ledger=bound(ledger),review_template=bound(review/'REVIEW_TEMPLATE.json'),MF_inputs=bound(manifest))
