"""Embed actual completed comparisons, retaining all seven task denominators."""
import argparse,base64,html,mimetypes,shutil
from common import *
def data_uri(path):
 mime=mimetypes.guess_type(str(path))[0] or 'application/octet-stream';return 'data:'+mime+';base64,'+base64.b64encode(Path(path).read_bytes()).decode()
def summary():
 rows=[]
 for pair in PAIRS:
  p=pair_info(pair);row={'pair':pair,'prompt_version':p['prompt_version'],'original_task':p['original_task'],'valid_frames':p['valid_frames'],'generation':'PENDING','media':'PENDING','task_success':'UNREVIEWED','timing_effect':'UNREVIEWED','MF':None}
  incoming=ROOT/'incoming'/pair
  if (incoming/'COLLECTION.json').exists():verify_intake(pair);row['generation']='COMPLETE'
  state=ROOT/'audit/watcher'/f'{pair}_STATUS.json'
  if state.exists() and read(state).get('status')=='FAILED_GATE':row['generation']='FAILED_GATE'
  presentation=ROOT/'showcase'/pair/'PRESENTATION.json'
  if presentation.exists():
   require(row['generation']=='COMPLETE','presentation without valid intake');d=read(presentation);require(d['collection']['sha256']==sha(incoming/'COLLECTION.json'),'presentation source differs')
   for v in d['videos']:require(sha(presentation.parent/v['file'])==v['sha256'],'presentation video changed')
   require(sha(presentation.parent/d['six_times']['file'])==d['six_times']['sha256'],'figure changed');row['media']='READY';row['presentation']=bound(presentation)
  review=ROOT/'results'/pair/'HUMAN_REVIEW.json'
  if review.exists():
   r=read(review);require(r['pair']==pair and r['collection_sha256']==sha(incoming/'COLLECTION.json'),'human review binding differs');row.update({k:r[k] for k in ['task_success','timing_effect']});row['review']=r
  rows.append(row)
 return {'schema':'r89-media-summary-v1','fixed_denominator':7,'distinct_source_videos':7,'completed_pairs':sum(x['generation']=='COMPLETE' for x in rows),'media_ready_pairs':sum(x['media']=='READY' for x in rows),'method':config()['method'],'rows':rows}
def build(output):
 validate_static();report=summary();blocks=[];downloads=Path(output).parent
 for r in report['rows']:
  pair=r['pair'];p=pair_info(pair);task=p['original_task'];body='<p>本组实际成片对照待完成。</p>'
  if r['media']=='READY':
   parent=ROOT/'showcase'/pair;pr=read(parent/'PRESENTATION.json');body=''
   for v in pr['videos']:
    src=parent/v['file'];label=f'完整有效片段 · {p["valid_frames"]/24:.3f}秒' if v['name']=='full_valid' else '前2秒'
    body+=f'<h3>{label}</h3><video controls playsinline preload="metadata" src="{data_uri(src)}"></video>'
    if v['name']=='full_valid':
     dest=downloads/f'H3_IVEBench_R89_{pair}_完整有效片段_三栏对照_20261018.mp4'
     if not dest.exists():shutil.copy2(src,dest)
     require(sha(dest)==v['sha256'],'Downloads video conflicts with existing file')
   body+=f'<details><summary>六个固定时刻</summary><img class="sheet" src="{data_uri(parent/pr["six_times"]["file"])}"></details>'
  quality='任务完成与时序效果：待人工检查。' if r['task_success']=='UNREVIEWED' else str(r['task_success'])+'；'+str(r['timing_effect'])
  blocks.append(f'<section><h2>{html.escape(pair)} · {html.escape(task["edit_prompt"])}</h2><p>生成状态：{r["generation"]}；{html.escape(quality)}</p>{body}<details><summary>官方任务与实际提示词</summary><p>Source: {html.escape(task["source_prompt"])}</p><p>Edit: {html.escape(task["edit_prompt"])}</p><p>Target: {html.escape(task["target_prompt"])}</p><pre>{html.escape(p["prompt"])}</pre></details></section>')
 document='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>IVEBench R89 七组固定时序引导</title><style>body{margin:0;padding:24px;background:#090a0e;color:#eee;font:18px/1.6 system-ui}main{max-width:2200px;margin:auto}h1{font-size:32px}h2{font-size:25px}h3{font-size:18px;color:#ccc}section{padding-top:28px;margin:35px 0;border-top:1px solid #30313b}video,.sheet{display:block;width:100%;background:#000}p{color:#ccc}details{margin-top:20px}pre{white-space:pre-wrap;font:14px/1.5 monospace}summary{cursor:pointer}</style><main><h1>IVEBench · 七组主体与外观编辑对照</h1><p>三列依次为参考视频、普通编辑、时序引导。两次推理使用相同的 P1-local-v1 提示词、输入和初始噪声；时序引导固定作用于去噪索引6–14，全部50个Block，alpha=1。online observer 关闭。</p><p>三列按相同24fps帧索引展示，统一裁去输入外加的边框；完整有效片段覆盖原片物理时长，尾部padding保留在完整成片归档。官方原视频及原片帧索引映射一并保存。固定分母为7；编辑完成、场景与动作保留、时序变化分别检查，待完成和失败结果均保留。</p>'+''.join(blocks)+'</main></html>'
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(document);save(output.with_suffix('.json'),report,replace=True);save(ROOT/'results/SUMMARY.json',report,replace=True)
 return {'html':bound(output),'completed_pairs':report['completed_pairs'],'media_ready_pairs':report['media_ready_pairs'],'fixed_denominator':7}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(build(a.output)))
