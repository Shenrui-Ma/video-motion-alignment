"""Self-contained actual-output showcase; all five clip outcomes remain visible."""
import argparse,base64,html,mimetypes,shutil
from fractions import Fraction
from common import *

def data_uri(path):
 mime=mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
 return 'data:'+mime+';base64,'+base64.b64encode(Path(path).read_bytes()).decode()

def summary():
 rows=[]
 for pair in PAIRS:
  p=pair_info(pair)
  row={'pair':pair,'prompt_version':p['prompt_version'],'original_task':p['original_task'],'clip':p['clip'],'valid_frames':p['valid_frames'],'generation':'PENDING','media':'PENDING','task_success':'UNREVIEWED','scene_retention':'UNREVIEWED','timing_effect':'UNREVIEWED','MF':None,'efficiency':None}
  incoming=ROOT/'incoming'/pair
  if (incoming/'COLLECTION.json').exists():
   gate=verify_intake(pair);row['generation']='COMPLETE';row['efficiency']={a:{k:gate['runs'][a][k] for k in ['NFE','routed_blocks','job_wall_seconds','capture_seconds']} for a in METHODS}
  state=ROOT/'audit/watcher'/f'{pair}_STATUS.json'
  if state.exists() and read(state).get('status') in ('FAILED_GATE','GENERATION_FAILED'):
   row['generation']=read(state)['status'];row['failure']=read(state)
  presentation=ROOT/'showcase'/pair/'PRESENTATION.json'
  if presentation.exists():
   require(row['generation']=='COMPLETE','presentation without valid intake');d=read(presentation)
   require(d['collection']['sha256']==sha(incoming/'COLLECTION.json'),'presentation source differs')
   for v in d['videos']:require(sha(presentation.parent/v['file'])==v['sha256'],'presentation video changed')
   for k in ['first_frame','six_times']:require(sha(presentation.parent/d[k]['file'])==d[k]['sha256'],'figure changed')
   row['media']='READY';row['presentation']=bound(presentation)
  review=ROOT/'results'/pair/'HUMAN_REVIEW.json'
  if review.exists():
   r=read(review);require(r['pair']==pair and r['collection_sha256']==sha(incoming/'COLLECTION.json'),'human review binding differs')
   row.update({k:r[k] for k in ['task_success','scene_retention','timing_effect']});row['review']=r
  rows.append(row)
 return {'schema':'r88-media-summary-v1','evaluation_scope':'IVEBench素材片段探索','full_official_benchmark_score':False,'fixed_denominator':5,'distinct_original_files':5,'completed_pairs':sum(x['generation']=='COMPLETE' for x in rows),'media_ready_pairs':sum(x['media']=='READY' for x in rows),'method':config()['method'],'rows':rows}

def build(output):
 validate_static();report=summary();blocks=[];downloads=Path(output).parent;downloads.mkdir(parents=True,exist_ok=True)
 for r in report['rows']:
  pair=r['pair'];p=pair_info(pair);task=p['original_task'];clip=p['clip'];start=Fraction(clip['start_pts_rational']);end=Fraction(clip['end_exclusive_rational'])
  body='<p>本组实际成片对照待完成。</p>'
  if r['media']=='READY':
   parent=ROOT/'showcase'/pair;pr=read(parent/'PRESENTATION.json');body=''
   for v in pr['videos']:
    src=parent/v['file'];count=v['frame_interval_inclusive'][1]+1
    label=f'完整有效片段 · {count/24:.3f} 秒' if v['name']=='full_valid' else f'前 5 秒预览 · 实际 {count/24:.3f} 秒'
    body+=f'<h3>{label}</h3><video controls playsinline preload="metadata" src="{data_uri(src)}"></video>'
    suffix='完整有效片段' if v['name']=='full_valid' else '前5秒预览'
    dest=downloads/f'H3_IVE素材片段_R88_{pair}_{suffix}_三栏对照_20261018.mp4'
    if not dest.exists():shutil.copy2(src,dest)
    require(sha(dest)==v['sha256'],'Downloads video conflicts with existing file')
   body+=f'<details open><summary>首帧：编辑对象与场景检查</summary><img class="sheet" src="{data_uri(parent/pr["first_frame"]["file"])}"></details>'
   body+=f'<details><summary>六个固定时刻</summary><img class="sheet" src="{data_uri(parent/pr["six_times"]["file"])}"></details>'
  quality='编辑任务、原场景与时序效果：待人工检查。' if r['task_success']=='UNREVIEWED' else '；'.join(str(r[k]) for k in ['task_success','scene_retention','timing_effect'])
  failure='' if 'failure' not in r else '<pre>'+html.escape(json.dumps(r['failure'],ensure_ascii=False,indent=2))+'</pre>'
  efficiency=''
  if r['efficiency'] is not None:
   efficiency='<p>推理耗时：'+ '；'.join(f'{label} {r["efficiency"][a]["job_wall_seconds"]/60:.1f} 分钟' for a,label in [('native','普通编辑'),('forced','时序引导')])+'。两次均为 20 次模型预测。</p>'
  blocks.append(f'<section><h2>{html.escape(pair)} · {html.escape(task["edit_prompt"])}</h2><p>原片区间 [{float(start):.6f}, {float(end):.6f}) 秒；原始帧 {clip["start_frame"]}–{clip["end_frame_inclusive"]}。有效输出 {p["valid_frames"]} 帧。</p><p>生成状态：{r["generation"]}；{html.escape(quality)}</p>{failure}{body}{efficiency}<details><summary>官方任务、提示词与时间映射</summary><p>Source: {html.escape(task["source_prompt"])}</p><p>Edit: {html.escape(task["edit_prompt"])}</p><p>Target: {html.escape(task["target_prompt"])}</p><p>原始有理时间区间 [{start}, {end})；原片逐帧映射随归档保存。提示协议：P1-local-v1。</p><pre>{html.escape(p["prompt"])}</pre></details></section>')
 document='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>IVEBench 素材片段探索 · R88</title><style>body{margin:0;padding:24px;background:#090a0e;color:#eee;font:18px/1.6 system-ui}main{max-width:2200px;margin:auto}h1{font-size:32px}h2{font-size:25px}h3{font-size:18px;color:#ccc}section{padding-top:28px;margin:35px 0;border-top:1px solid #30313b}video,.sheet{display:block;width:100%;background:#000}p{color:#ccc}details{margin-top:20px}pre{white-space:pre-wrap;font:14px/1.5 monospace}summary{cursor:pointer}</style><main><h1>IVEBench 素材片段探索 · 五组视频编辑对照</h1><p>三列依次为参考视频、普通编辑、时序引导。每对使用相同的输入、提示词与初始噪声；引导作用于去噪步骤6–14，参考时序对应关系由固定策略指定。</p><p>连续片段按原视频内容预先选择。三列按相同24fps帧索引展示，统一裁去输入外加边框；尾部补帧排除。全部五组及失败状态保留。先检查任务和原场景保留，再比较动作时序。本页记录素材片段探索，完整官方 benchmark 分数尚未测量。</p>'+''.join(blocks)+'</main></html>'
 output=Path(output);output.write_text(document);save(output.with_suffix('.json'),report,replace=True);save(ROOT/'results/SUMMARY.json',report,replace=True)
 return {'html':bound(output),'completed_pairs':report['completed_pairs'],'media_ready_pairs':report['media_ready_pairs'],'fixed_denominator':5}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(build(a.output)))
