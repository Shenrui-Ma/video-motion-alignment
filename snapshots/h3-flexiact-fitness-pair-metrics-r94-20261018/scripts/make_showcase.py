"""Embed all available real comparisons, retaining the fixed denominator of one."""
import argparse,base64,html,mimetypes,shutil
from common import *
def data_uri(path):
 mime=mimetypes.guess_type(str(path))[0] or 'application/octet-stream';return 'data:'+mime+';base64,'+base64.b64encode(Path(path).read_bytes()).decode()
def summary():
 rows=[]
 for pair in PAIRS:
  row={'pair':pair,'prompt_version':pair_info(pair)['prompt_version'],'generation':'PENDING','media':'PENDING','task_success':'UNREVIEWED','timing_effect':'UNREVIEWED','MF':None}
  incoming=ROOT/'incoming'/pair
  if (incoming/'COLLECTION.json').exists():verify_intake(pair);row['generation']='COMPLETE'
  state=ROOT/'audit/watcher'/f'{pair}_STATUS.json'
  if state.exists() and read(state).get('status')=='FAILED_GATE':row['generation']='FAILED_GATE'
  presentation=ROOT/'showcase'/pair/'PRESENTATION.json'
  if presentation.exists():
   require(row['generation']=='COMPLETE','presentation without valid intake');d=read(presentation)
   require(d['collection']['sha256']==sha(incoming/'COLLECTION.json'),'presentation source differs')
   for v in d['videos']:require(sha(presentation.parent/v['file'])==v['sha256'],'presentation video changed')
   require(sha(presentation.parent/d['six_times']['file'])==d['six_times']['sha256'],'figure changed');row['media']='READY';row['presentation']=bound(presentation)
  review=ROOT/'results'/pair/'HUMAN_REVIEW.json'
  if review.exists():
   r=read(review);require(r['pair']==pair and r['collection_sha256']==sha(incoming/'COLLECTION.json'),'human review binding differs')
   row.update({k:r[k] for k in ['task_success','timing_effect']});row['review']=r
  rows.append(row)
 return {'schema':'r94-media-summary-v1','fixed_denominator':1,'distinct_motion_sources':1,'new_motion_sources':0,'completed_pairs':sum(x['generation']=='COMPLETE' for x in rows),'media_ready_pairs':sum(x['media']=='READY' for x in rows),'method':'fixed steps6..14; no online observer','rows':rows}

def build(output):
 validate_static();report=summary();blocks=[];downloads=Path(output).parent
 for r in report['rows']:
  pair=r['pair'];p=pair_info(pair);target=ROOT/p['target']['file'];require(sha(target)==p['target']['sha256'],'target changed')
  body='<p>本组实际成片对照待完成。</p>'
  if r['media']=='READY':
   parent=ROOT/'showcase'/pair;pr=read(parent/'PRESENTATION.json');body=''
   for v in pr['videos']:
    src=parent/v['file'];label='完整有效片段 · 6.125秒' if v['name']=='full_valid' else '前2秒'
    body+=f'<h3>{label}</h3><video controls playsinline preload="metadata" src="{data_uri(src)}"></video>'
    if v['name']=='full_valid':
     dest=downloads/f'H3_FlexiAct_R94_{pair}_完整有效片段_三栏对照_20261018.mp4'
     if not dest.exists():shutil.copy2(src,dest)
     require(sha(dest)==v['sha256'],'Downloads video conflicts with existing file')
   body+=f'<details><summary>六个固定时刻</summary><img class="sheet" src="{data_uri(parent/pr["six_times"]["file"])}"></details>'
  quality='<p>任务完成与时序效果：待人工检查。</p>' if r['task_success']=='UNREVIEWED' else '<p>'+html.escape(str(r['task_success']))+'；'+html.escape(str(r['timing_effect']))+'</p>'
  blocks.append(f'<section><h2>{html.escape(pair)} · {r["prompt_version"]}</h2><div class="target"><img src="{data_uri(target)}"><div>目标人物参考图<br>生成状态：{r["generation"]}<br>{quality}</div></div>{body}<details><summary>本组实际提示词</summary><pre>{html.escape(p["prompt"])}</pre></details></section>')
 document='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FlexiAct R94 fitness 固定时序引导</title><style>body{margin:0;padding:24px;background:#090a0e;color:#eee;font:18px/1.6 system-ui}main{max-width:2200px;margin:auto}h1{font-size:32px}h2{font-size:25px}h3{font-size:18px;color:#ccc}section{padding-top:28px;margin:35px 0;border-top:1px solid #30313b}video,.sheet{display:block;width:100%;background:#000}p{color:#ccc}.target{display:flex;gap:24px;align-items:center;margin-bottom:22px}.target img{max-width:230px;max-height:190px;object-fit:contain}details{margin-top:20px}pre{white-space:pre-wrap;font:14px/1.5 monospace}summary{cursor:pointer}</style><main><h1>FlexiAct · fitness 固定时序引导对照</h1><p>三列依次为参考视频、普通编辑、时序引导。同组两次推理使用相同提示词、输入和初始噪声；时序引导固定作用于去噪索引6–14。本组使用同一P1提示词，两条均为本轮新生成。</p><p>每列展示相同的147帧有效片段，24fps、6.125秒。参考动作原为49帧、8fps，经重复原帧转换到24fps，原动作时间精度为125毫秒。本组完整结果与待完成状态均保留；完整158帧成片另存于归档。</p>'+''.join(blocks)+'</main></html>'
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(document);save(output.with_suffix('.json'),report,replace=True);save(ROOT/'results/SUMMARY.json',report,replace=True)
 return {'html':bound(output),'completed_pairs':report['completed_pairs'],'media_ready_pairs':report['media_ready_pairs'],'fixed_denominator':1}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(build(a.output)))
