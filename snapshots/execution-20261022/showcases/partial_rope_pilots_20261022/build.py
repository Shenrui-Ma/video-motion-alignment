from pathlib import Path
import base64,hashlib,html,json,subprocess,tempfile,shutil
from PIL import Image,ImageDraw,ImageFont
E=Path(__file__).resolve().parents[2]; D=Path(__file__).resolve().parent
R=E.parent/'reports'; R.mkdir(exist_ok=True)
M=json.loads((E/'metrics/manifest.json').read_text())['jobs']
rows=json.loads((E/'summaries/innovation_20261022/partial_pilots_metrics.json').read_text())
methods=['source','native','global_weak','partial_temporal_rope']
labels=['参考视频','Baseline','α = 0.25','部分RoPE频带']
metrics=[('motion_fidelity','MF','运动保真度'),('subject_consistency','SC','主体一致性'),('background_consistency','BC','背景一致性'),('temporal_flickering','TF','时序稳定性'),('motion_smoothness','MS','运动平滑度'),('vtss','VTSS','编辑文本匹配'),('overall_semantic_consistency','OSC','整体语义一致性'),('phrase_semantic_consistency','PSC','目标语义一致性'),('semantic_fidelity','SF','语义保真度')]
lookup={(d['task_id'],d['method'],d['metric']):d['score'] for d in rows if d.get('status')=='done'}
required=[(sid,m,k) for sid in ['short_0252','short_0358'] for m in methods for k,_,_ in metrics]
missing=[k for k in required if k not in lookup]
if missing: raise SystemExit('Waiting for official scores: '+str(missing))
awq={}
for sid in ['short_0252','short_0358']:
 for m in ['native','global_weak']:
  base=E/'metrics/qwen_runtime/host41/snapshot/qwen_runtime/evaluation_awq/results'/(sid+'__'+m)
  awq[sid,m]=[json.loads((base/(metric+'.json')).read_text())['score'] for metric in ['instruction_satisfaction','content_fidelity']]
extra=json.loads((E/'metrics/qwen_runtime/host60_extra/incremental_four_scores.json').read_text())['results']
for sid in ['short_0252','short_0358']:
 x=next(x for x in extra if x['job_id']=='innov41_'+sid+'_partial_temporal_rope')
 awq[sid,'partial_temporal_rope']=[x[k]['score'] for k in ['instruction_satisfaction','content_fidelity']]
def awq_table(sid):
 out='<h3>Qwen2.5-VL-72B · AWQ评分</h3><table><tr><th>方法</th><th>IS · 指令满足度 ↑</th><th>CF · 内容保真度 ↑</th></tr>'
 for m,label in zip(methods[1:],labels[1:]):out+=f'<tr><th>{label}</th><td>{awq[sid,m][0]:.0f}/5</td><td>{awq[sid,m][1]:.0f}/5</td></tr>'
 return out+'</table><p class="sub">使用同一4-bit AWQ权重与官方评分提示词。部分RoPE评测在.60采用CPU跨卡转运修复；Baseline和α = 0.25沿用.41评分，配置记录分别保留。</p>'
annotations={sid:json.loads((D/'visual'/sid/'ANNOTATION.json').read_text()) for sid in ['short_0252','short_0358']}
def event_table(sid):
 a=annotations[sid];out='<h3>关键动作偏移</h3><table><tr><th>动作</th>'+''.join('<th>'+x+'</th>' for x in labels[1:])+'</tr>'
 for e in a['events']:
  out+='<tr><th>'+e['label']+'</th>'+''.join(f"<td>{e['offset_frames'][m]:+.1f}帧</td>" for m in methods[1:])+'</tr>'
 means=a.get('means',a.get('mean_absolute_offset_frames'))
 out+='<tr><th>平均绝对偏移 ↓</th>'+''.join(f'<td>{means[m]:.2f}帧</td>' for m in methods[1:])+'</tr></table>'
 out+='<p>'+a['visual_conclusion']+'</p>'
 return out

def evidence(sid):
 frames=[52] if sid=='short_0252' else [42,85]
 out=''
 for f in frames:
  data=base64.b64encode((D/'visual'/sid/f'comparison_frame_{f:03d}.jpg').read_bytes()).decode()
  caption='参考与全程α = 0.25已抓住面罩杯，Baseline与部分RoPE频带仍在准备抬手。' if sid=='short_0252' else ('部分RoPE频带的瓶口到嘴时刻接近参考；Baseline仍在举瓶。' if f==42 else '参考与全程α = 0.25已结束饮酒，Baseline与部分RoPE频带仍在饮酒。')
  out+=f'<figure style="margin:16px 0"><img style="width:100%" src="data:image/jpeg;base64,{data}"><figcaption class="sub">第{f}帧。{caption}</figcaption></figure>'
 return out

def table(sids):
 vals={}
 for method in methods[1:]:
  for key,_,_ in metrics:
   scores=[lookup[(sid,method,key)]-(lookup[(sid,'source',key)] if key=='motion_fidelity' else 0) for sid in sids]
   vals[method,key]=sum(scores)/len(scores)
 out='<div class="scroll"><table><thead><tr><th>方法</th><th>动作偏移 ↓<small>平均绝对偏移·帧</small></th>'
 for key,ab,cn in metrics: out+=f'<th class="{ "mf" if key=="motion_fidelity" else ""}">{ab} ↑<small>{cn}{"·相对参考差值" if key=="motion_fidelity" else ""}</small></th>'
 out+='</tr></thead><tbody>'
 for method,label in zip(methods[1:],labels[1:]):
  mean=sum(annotations[sid].get('means',annotations[sid].get('mean_absolute_offset_frames'))[method] for sid in sids)/len(sids)
  out+=f'<tr><th>{label}</th><td>{mean:.2f}</td>'
  for key,_,_ in metrics:
   v=vals[method,key]; best=max(vals[m,key] for m in methods[1:]); mark='<b class="best"> ✓</b>' if abs(v-best)<1e-10 else ''
   out+=f'<td class="{"mf" if key=="motion_fidelity" else ""}">{v:+.4f}{mark}</td>' if key=='motion_fidelity' else f'<td>{v:.4f}{mark}</td>'
  out+='</tr>'
 return out+'</tbody></table></div>'
records=[]; sections=[]
with tempfile.TemporaryDirectory(prefix='h3-rope-comparison-') as td:
 td=Path(td); caption=Image.new('RGB',(3072,92),'black'); draw=ImageDraw.Draw(caption); font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf',28)
 for i,label in enumerate(labels):
  box=draw.textbbox((0,0),label,font=font);draw.text((i*768+(768-box[2]+box[0])/2,12-box[1]),label,font=font,fill='white')
 caption.save(td/'caption.png')
 for sid,title in [('short_0252','角色替换：机舱男性替换为年长女性'),('short_0358','外观编辑：给饮酒男子添加眼镜')]:
  jobs=[next(j for j in M if j['task_id']==sid and j['method']==method) for method in methods]
  inputs=[]
  for j in jobs:
   p=td/(j['id']+'.mp4');cached=D/'visual'/sid/(j['method']+'.mp4')
   if cached.exists(): shutil.copyfile(cached,p)
   else: subprocess.run(['scp','-q','H3_HOST_CONFIGURE_LOCALLY:'+j['video'],str(p)],check=True,timeout=180)
   assert hashlib.sha256(p.read_bytes()).hexdigest()==j['sha256'];inputs+=['-i',str(p)]
  n=jobs[0]['valid_frames']; fps=jobs[0]['fps'];filters=[]
  assert all(j['valid_frames']==n and j['fps']==fps for j in jobs)
  for i,j in enumerate(jobs):
   x,y,w,h=j['crop_xywh'];filters.append(f'[{i}:v]trim=end_frame={n},setpts=PTS-STARTPTS,crop={w}:{h}:{x}:{y},scale=768:432:flags=lanczos,setsar=1[v{i}]')
  filters+=['[v0][v1][v2][v3]hstack=inputs=4[top]','[top][4:v]vstack=inputs=2:shortest=1[out]']
  target=D/(sid+'_comparison.mp4')
  subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',*inputs,'-loop','1','-framerate',str(fps),'-i',str(td/'caption.png'),'-filter_complex_threads','2','-filter_complex',';'.join(filters),'-map','[out]','-an','-frames:v',str(n),'-r',str(fps),'-c:v','libx264','-threads','4','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(target)],check=True,timeout=180)
  probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,r_frame_rate','-of','json',str(target)]))['streams'][0]
  assert probe['width']==3072 and probe['height']==524 and int(probe['nb_frames'])==n
  scores=[lookup[(sid,m,'motion_fidelity')] for m in methods[1:]]
  delta=scores[2]-scores[1]
  result=f'部分RoPE频带MF为 {scores[2]:.4f}，相比全程α = 0.25{ "提高" if delta>0 else "下降"} {abs(delta):.4f}。'
  prompt=jobs[-1].get('prompt')
  prompt=prompt or jobs[-1].get('metadata',{}).get('edit_prompt','')
  data=base64.b64encode(target.read_bytes()).decode()
  sections.append(f'<section><h2>{html.escape(title)}</h2><p class="sub">IVEBench · {sid} · {html.escape(jobs[0]["metadata"]["edit_prompt"])}</p>{evidence(sid)}<video controls playsinline preload="metadata" src="data:video/mp4;base64,{data}"></video><p>{result}</p>{event_table(sid)}{table([sid])}{awq_table(sid)}<details><summary>推理配置与输入</summary><p>20步；引导α = 0.25；时间RoPE频率对8–15；参考与输出缓存时间原点差为−107帧。三种编辑沿用同组prompt、seed、模型与几何设置。</p><pre>{html.escape(prompt)}</pre></details></section>')
  records.append({'task_id':sid,'output':str(target),'probe':probe,'inputs':[{'id':j['id'],'sha256':j['sha256']} for j in jobs],'MF':dict(zip(methods[1:],scores))})
  print(sid,probe,flush=True)
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>部分RoPE频带 · 两组对照</title><style>body{margin:0;background:#f5f6f8;color:#18202b;font:16px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}main{max-width:1500px;margin:36px auto;padding:0 24px}h1{font-size:30px}h2{font-size:23px}section{background:white;border:1px solid #dce1e8;border-radius:12px;padding:24px;margin:24px 0}video{width:100%;background:black;border-radius:6px}.sub,small{color:#667180}small{display:block;font-size:11px;font-weight:400}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px;white-space:nowrap}th,td{padding:12px 9px;text-align:center;border-bottom:1px solid #e6e9ee}th:first-child{text-align:left}.mf{border-left:2px solid #a8d9b8;border-right:2px solid #a8d9b8;background:#f3fbf5}thead .mf{border-top:2px solid #a8d9b8}tbody tr:last-child .mf{border-bottom:2px solid #a8d9b8}.best{color:#168c48}pre{white-space:pre-wrap;font:13px/1.6 monospace}details{margin-top:16px;color:#57616e}summary{cursor:pointer}</style><main><h1>部分RoPE频带 · 两组对照</h1><p>视频顺序：参考视频、Baseline、全程α = 0.25、部分RoPE频带。所有列使用相同时刻；底部保留播放器控制区。</p><section><h2>两组平均指标</h2>'''+table(['short_0252','short_0358'])+'''<p class="sub">MF显示相对参考视频的差值，越接近0越好；其余指标显示官方实现的分数，越高越好。绿色勾标记本表三种编辑中的最高值。动作偏移由逐帧视觉标注得到，正数为延后，负数为提前；采用相同事件过渡区间的中点差，范围记录在原始标注中。QA在这两项任务中不适用；IS/CF采用独立AWQ评测，列于各样例下方。</p></section>'''+''.join(sections)+'</main></html>'
target=R/'H3_部分RoPE频带_两组对照_20261022.html';target.write_text(page)
(D/'export.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));print(target, target.stat().st_size)
