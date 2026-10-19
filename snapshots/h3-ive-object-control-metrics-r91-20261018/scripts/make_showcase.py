"""Single-file display of actual R91 media; keep both tasks and pending outcomes."""
import argparse,base64,html,mimetypes,shutil
from common import *

def data_uri(path):
 mime=mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
 return 'data:'+mime+';base64,'+base64.b64encode(Path(path).read_bytes()).decode()

def summary():
 rows=[]
 for pair in PAIRS:
  p=pair_info(pair);row={'pair':pair,'prompt_version':p['prompt_version'],'original_task':p['original_task'],'display_task':p['display_task'],'reference_image_used':False,'evaluation_scope':p['evaluation_scope'],'clip':p['clip'],'valid_frames':p['valid_frames'],'generation':'PENDING','media':'PENDING','task_success':'UNREVIEWED','timing_effect':'UNREVIEWED','MF':None}
  incoming=ROOT/'incoming'/pair
  if (incoming/'COLLECTION.json').exists():
   g=verify_intake(pair);row['generation']='COMPLETE';row['efficiency']={arm:{k:g['runs'][arm][k] for k in ('NFE','Euler_updates','routed_blocks','job_wall_seconds','capture_seconds')} for arm in METHODS}
  state=ROOT/'audit/status'/f'{pair}.json'
  if state.exists() and read(state).get('status')=='FAILED_GATE':row['generation']='FAILED_GATE'
  presentation=ROOT/'showcase'/pair/'PRESENTATION.json'
  if presentation.exists():
   require(row['generation']=='COMPLETE','presentation without valid intake');d=read(presentation)
   require(d['collection']['sha256']==sha(incoming/'COLLECTION.json'),'presentation collection differs')
   require(d['gate']['sha256']==sha(incoming/'PAIR_RUNTIME_GATE.json'),'presentation gate differs')
   for v in d['videos']:require(sha(presentation.parent/v['file'])==v['sha256'],'presentation video changed')
   for role in ('six_times','poster'):require(sha(presentation.parent/d[role]['file'])==d[role]['sha256'],'presentation image changed')
   row['media']='READY';row['presentation']=bound(presentation)
  review=ROOT/'results'/pair/'HUMAN_REVIEW.json'
  if review.exists():
   r=read(review);require(r['pair']==pair and r['collection_sha256']==sha(incoming/'COLLECTION.json'),'human review binding differs')
   row.update({k:r[k] for k in ['task_success','timing_effect']});row['review']=r
  rows.append(row)
 return {'schema':'r91-media-summary-v1','fixed_denominator':2,'distinct_source_videos':2,'completed_pairs':sum(x['generation']=='COMPLETE' for x in rows),'media_ready_pairs':sum(x['media']=='READY' for x in rows),'method':config()['method'],'rows':rows}

def build(output):
 validate_static();report=summary();blocks=[];output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);assets=[]
 for r in report['rows']:
  pair=r['pair'];p=pair_info(pair);task=p['original_task'];body='<p>本组实际对照待完成。</p>'
  if r['media']=='READY':
   parent=ROOT/'showcase'/pair;pr=read(parent/'PRESENTATION.json');body=''
   for v in pr['videos']:
    src=parent/v['file'];label=f'完整有效视频 · {p["valid_frames"]/24:.3f} 秒' if v['name']=='full_valid' else '前 2 秒'
    body+=f'<h3>{label}</h3><video controls playsinline preload="none" poster="{data_uri(parent/pr["poster"]["file"])}" src="{data_uri(src)}"></video>'
    assets.append({'role':v['name'],'pair':pair,**bound(src)})
    if v['name']=='full_valid':
     dest=output.parent/f'H3_R91_{pair}_完整有效视频_三栏对照_20261018.mp4'
     if not dest.exists():shutil.copy2(src,dest)
     require(sha(dest)==v['sha256'],'export video conflicts with existing file')
   body+=f'<details><summary>六个固定时刻</summary><img class="sheet" src="{data_uri(parent/pr["six_times"]["file"])}"></details>'
   assets.extend({'role':role,'pair':pair,**bound(parent/pr[role]['file'])} for role in ('poster','six_times'))
  quality='任务完成与时序效果待人工检查。' if r['task_success']=='UNREVIEWED' else str(r['task_success'])+'；'+str(r['timing_effect'])
  scope='官方完整源视频' if pair=='short_0114' else 'IVEBench 素材片段探索：原片 0–6 秒'
  blocks.append(f'<section><h2>{html.escape(p["display_task"])}</h2><p>参考图：无；参考视频：1 条。{scope}。{p["valid_frames"]} 有效帧，24 fps。</p><p>生成状态：{r["generation"]}；{html.escape(quality)}</p>{body}<details><summary>官方任务、实际提示词与运行证据</summary><p>任务编号：{pair}；P1-local-v1；完整生成 {p["geometry"]["frames"]} 帧。</p><p>原指令：{html.escape(task["edit_prompt"])}</p><p>Source: {html.escape(task["source_prompt"])}</p><p>Target: {html.escape(task["target_prompt"])}</p><pre>{html.escape(p["prompt"])}</pre><pre>{html.escape(json.dumps(r,ensure_ascii=False,indent=2))}</pre></details></section>')
 document='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>R91 · 两组物体编辑</title><style>body{margin:0;padding:24px;background:#090a0e;color:#eee;font:18px/1.6 system-ui}main{max-width:2200px;margin:auto}h1{font-size:32px}h2{font-size:25px}h3{font-size:18px;color:#ccc}section{padding-top:28px;margin:35px 0;border-top:1px solid #30313b}video,.sheet{display:block;width:100%;background:#000}p{color:#ccc}details{margin-top:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.5 monospace}summary{cursor:pointer}</style></head><body><main><h1>两组物体编辑 · 参考与时序引导对照</h1><p>三列依次为参考视频、普通编辑、时序引导。每组使用相同提示词、输入与初始噪声；固定引导作用于去噪索引 6–14，全部 50 个 Block，alpha=1。</p><p>三列按相同 24 fps 帧索引展示，统一裁去输入附加边框，展示覆盖全部有效帧。篮球使用完整官方源视频；取书使用原片 0–6 秒。这份页面展示实际结果，任务完成和时序收益由后续人工审阅登记。</p>'+''.join(blocks)+'</main></body></html>'
 output.write_text(document);report['embedded_assets']=assets;report['embedded_video_count']=sum(x['role'] in ('full_valid','first2seconds') for x in assets)
 save(output.with_suffix('.json'),report,replace=True);save(ROOT/'results/SUMMARY.json',report,replace=True)
 from verify_showcase import verify
 verify(output)
 return {'html':bound(output),'completed_pairs':report['completed_pairs'],'media_ready_pairs':report['media_ready_pairs'],'fixed_denominator':2,'embedded_video_count':report['embedded_video_count']}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(build(a.output)))
