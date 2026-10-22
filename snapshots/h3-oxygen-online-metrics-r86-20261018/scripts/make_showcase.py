"""One actual online task; quality and runtime integrity reported separately."""
import argparse,base64,html,shutil
from common import *
def data_uri(p,mime):return 'data:'+mime+';base64,'+base64.b64encode(Path(p).read_bytes()).decode()
def summary():
 cfg=validate_static();row={'source':SOURCE,'run_id':RUN,'planned_denominator':1,'historical_Native_reused':True,'historical_fixed_control_reused':True,'generation':'PENDING','GPU_validation':'PENDING','media':'PENDING','task_success':'UNREVIEWED','timing_effect':'UNREVIEWED','actual_ON_indices':None,'spatial_actor_selection':'manual source-specified bbox center x in.40-.75','automatic_scope':'online temporal windows/start/stop','attention_spatial_support':'all spatial queries of selected time bins','MF':None}
 state=ROOT/'audit/watcher/STATUS.json'
 if state.exists() and read(state).get('status')=='FAILED_ATTEMPT':row.update(generation='FAILED_ATTEMPT',GPU_validation='INCOMPLETE')
 if (ROOT/'incoming/COLLECTION.json').exists():
  gate,case=verify_intake();audit=read(ROOT/'incoming/counterfactual.json');actual=read_decisions(audit,case);require(actual==read(ROOT/'incoming/ACTUAL_DECISIONS.json'),'actual summary differs');row.update(generation='COMPLETE',GPU_validation='ACTUAL_ROOT_GATE_PASS',actual_ON_indices=case['mask'],actual_decisions=actual,efficiency=gate['efficiency'],causal_prefix_count=len(case['independent_native_prefix']),all_OFF_final_latents_exact=case['all_OFF_final_exact'])
 if (ROOT/'showcase/PRESENTATION.json').exists():
  require(row['generation']=='COMPLETE','media without validated result');p=read(ROOT/'showcase/PRESENTATION.json');require(p['collection']['sha256']==sha(ROOT/'incoming/COLLECTION.json'),'media intake differs')
  for v in p['videos']:require(sha(ROOT/'showcase'/v['file'])==v['sha256'],'media changed')
  require(sha(ROOT/'showcase'/p['six_times']['file'])==p['six_times']['sha256'],'six times changed');row['media']='READY'
 review=ROOT/'results/HUMAN_REVIEW.json'
 if review.exists():
  r=read(review);require(r['source']==SOURCE and r['collection_sha256']==sha(ROOT/'incoming/COLLECTION.json'),'human review binding differs');row.update({k:r[k] for k in ['task_success','timing_effect']})
 return row

def build(output):
 cfg=validate_static();r=summary();body='<p>在线推理与 GPU 验证待完成；实际介入步骤和窗口将在完成收据通过后显示。</p>';table='';downloads=Path(output).parent
 if r['media']=='READY':
  record=read(ROOT/'showcase/PRESENTATION.json');body=''
  for v in record['videos']:
   path=ROOT/'showcase'/v['file'];tag='<video controls playsinline preload="metadata" src="'+data_uri(path,'video/mp4')+'"></video>'
   if v['name']=='r73_fixed_full_valid':body+='<details><summary>单独对照：R73 固定步骤6–14时序引导</summary>'+tag+'</details>'
   else:body+='<h2>'+('完整有效片段 · 4.083秒' if v['name']=='online_full_valid' else '前2秒')+'</h2>'+tag
   if v['name']=='online_full_valid':
    dest=downloads/'H3_R86氧气罩_在线时序引导_完整有效片段_20261018.mp4'
    if not dest.exists():shutil.copy2(path,dest)
    require(sha(dest)==v['sha256'],'Downloads media conflict')
  body+='<details><summary>六个固定时刻</summary><img src="'+data_uri(ROOT/'showcase'/record['six_times']['file'],'image/jpeg')+'"></details>'
  actual=r['actual_decisions'];mask=actual['actual_ON_indices'];table='<h2>实际在线介入记录</h2><p>ON索引：'+html.escape(str(mask))+'。实际模型前向 '+str(actual['NFE'])+' 次，Euler 更新20次。连续介入区间：'+html.escape(str(actual['actual_ON_denoising_intervals_inclusive']))+'。</p><table><thead><tr><th>去噪索引</th><th>是否介入</th><th>视频帧区间（闭区间）</th><th>秒区间</th><th>观测状态</th><th>记录原因</th></tr></thead><tbody>'
  for row in actual['rows']:
   table+='<tr><td>'+str(row['denoising_index'])+'</td><td>'+('ON' if row['ON'] else 'OFF')+'</td><td>'+html.escape(str(row['physical_intervals']))+'</td><td>'+html.escape(str([[round(a,3),round(b,3)] for a,b in row['seconds_inclusive']]))+'</td><td>'+html.escape(str(row['measurement_status']))+'</td><td>'+html.escape(row['reason'])+'</td></tr>'
  table+='</tbody></table>'
 quality='任务完成与时序效果待人工检查。' if r['task_success']=='UNREVIEWED' else str(r['task_success'])+' '+str(r['timing_effect'])
 document='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>R86 氧气罩在线时序引导</title><style>body{margin:0;padding:24px;background:#090a0e;color:#eee;font:18px/1.6 system-ui}main{max-width:2200px;margin:auto}h1{font-size:32px}h2{font-size:24px;margin-top:32px}video,img{display:block;width:100%;background:#000}p{color:#ccc}details{margin-top:25px}summary{cursor:pointer}pre{white-space:pre-wrap;font:14px/1.5 monospace}table{border-collapse:collapse;width:100%;font-size:15px}th,td{padding:10px;border-bottom:1px solid #333;text-align:left}</style><main><h1>氧气罩人物替换 · 在线检测与时序引导</h1><p>任务：'+html.escape(cfg['case']['original_task']['edit_prompt'])+'。三列为参考视频、R73普通编辑、R86在线检测与时序引导。普通编辑复用同输入、同种子的原始成片；实际完成门核验条件、噪声和首次介入前的共同计算。</p><p>成人观察范围由原片人工指定为 bbox 中心横坐标占画宽0.40–0.75；算法逐去噪步骤选择时间窗口及开始、停止时机。attention覆盖选中时间段的全部空间位置。实际介入记录取自本次在线audit。</p><p>显示全部98个有效帧，24fps，三列使用相同帧索引与边缘裁剪。原107帧成片和官方原视频另存。当前是一条开发性配对任务；单独附上此前固定引导作对照。</p><p>运行状态：'+r['generation']+'；GPU验证：'+r['GPU_validation']+'。'+html.escape(quality)+'</p>'+body+table+'<details><summary>实际提示词</summary><pre>'+html.escape(cfg['case']['prompt'])+'</pre></details></main></html>'
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(document);save(output.with_suffix('.json'),r,replace=True);save(ROOT/'results/SUMMARY.json',r,replace=True);return {'html':bound(output),'generation':r['generation'],'media':r['media'],'planned_denominator':1}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(build(a.output)))
