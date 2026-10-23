from pathlib import Path
import base64,hashlib,html,json,subprocess,tempfile,shutil,statistics,datetime
from PIL import Image,ImageDraw,ImageFont
D=Path(__file__).resolve().parent; E=D.parents[1]; R=E.parent/'reports'
snapshot=json.loads((D/'completed_snapshot.json').read_text());M=snapshot['jobs'];rows=snapshot['scores']
methods=['source','native','global_weak','partial_temporal_rope'];labels=['参考视频','Baseline','α = 0.25','部分RoPE频带']
order=['short_0252','short_0358','long_0039','long_0059','short_0085','short_0274','short_0343']
titles={'short_0252':'角色替换：机舱男性替换为年长女性','short_0358':'外观编辑：给饮酒男子添加眼镜','long_0039':'物体外观编辑：书本改为蓝色','long_0059':'物体添加：擦泪男子手中添加白手帕','short_0085':'外观编辑：女子头发改为红色','short_0274':'角色替换：宇航员替换为外星人','short_0343':'角色替换：浴室女子替换为医生'}
sids=[s for s in order if any(j['task_id']==s and j['method']=='partial_temporal_rope' for j in M)]
assert len(sids)==7, f'Expected final seven completed cases, found {sids}'
mainids={j['id'] for j in json.loads((E/'metrics/qwen_runtime/host41/manifest.main.json').read_text())['jobs']}
jobs={}
for sid in sids:
 for method in methods:
  match=[j for j in M if j['task_id']==sid and j['method']==method and (j['id'] in mainids or method=='partial_temporal_rope')]
  assert len(match)==1,(sid,method,len(match));jobs[sid,method]=match[0]
metrics=[('motion_fidelity','MF','运动保真度'),('subject_consistency','SC','主体一致性'),('background_consistency','BC','背景一致性'),('temporal_flickering','TF','时序稳定性'),('motion_smoothness','MS','运动平滑度'),('vtss','VTSS','编辑文本匹配'),('overall_semantic_consistency','OSC','整体语义一致性'),('phrase_semantic_consistency','PSC','目标语义一致性'),('semantic_fidelity','SF','语义保真度')]
lookup={(x['job_id'],x['metric']):x['score'] for x in rows if x.get('status')=='done' and isinstance(x.get('score'),(int,float))}
def score(sid,m,key):return lookup.get((jobs[sid,m]['id'],key))
annotations={s:json.loads((D/'visual'/s/'ANNOTATION.json').read_text()) for s in ['short_0252','short_0358']}
audits=json.loads((D/'runtime_audit.json').read_text())
awqrows=json.loads((D/'awq_completed_snapshot.json').read_text());awq={}
for sid in sids:
 for method in methods[1:]:
  jid=jobs[sid,method]['id']
  for metric in ['instruction_satisfaction','content_fidelity']:
   if method in ['native','global_weak']:
    p=E/'metrics/qwen_runtime/host41/snapshot/qwen_runtime/evaluation_awq/results'/jid/(metric+'.json')
    x=json.loads(p.read_text()) if p.exists() else None
   else:x=next((x for x in awqrows if x['job_id']==jid and x['metric']==metric and x.get('status')=='done'),None)
   if x and x.get('status')=='done':awq[sid,method,metric]=x['score']
def awq_table(sid):
 out='<h3>IS / CF · Qwen2.5-VL-72B AWQ</h3><table><tr><th>方法</th><th>IS · 指令满足度 ↑</th><th>CF · 内容保真度 ↑</th></tr>'
 for m,label in zip(methods[1:],labels[1:]):
  out+='<tr><th>'+label+'</th>'+''.join('<td>'+ (f'{awq[sid,m,k]:.0f}/5' if (sid,m,k) in awq else '待评')+'</td>' for k in ['instruction_satisfaction','content_fidelity'])+'</tr>'
 return out+'</table>'
def evidence(sid):
 if sid not in annotations:return ''
 out=''
 for f in ([52] if sid=='short_0252' else [42,85]):
  data=base64.b64encode((D/'visual'/sid/f'comparison_frame_{f:03d}.jpg').read_bytes()).decode()
  caption='参考与全程α = 0.25已抓住面罩杯，Baseline与部分RoPE频带仍在准备抬手。' if sid=='short_0252' else ('部分RoPE频带的瓶口到嘴时刻接近参考；Baseline仍在举瓶。' if f==42 else '参考与全程α = 0.25已结束饮酒，Baseline与部分RoPE频带仍在饮酒。')
  out+=f'<figure><img src="data:image/jpeg;base64,{data}" alt="四种方法同帧对照"><figcaption>同帧对比 · 第{f}帧。{caption}</figcaption></figure>'
 return out
def event_table(sid):
 if sid not in annotations:return '<p class="sub">动作偏移：未测。</p>'
 a=annotations[sid];out='<h3>关键动作偏移</h3><table><tr><th>动作</th>'+''.join('<th>'+x+'</th>' for x in labels[1:])+'</tr>'
 for ev in a['events']:out+='<tr><th>'+ev['label']+'</th>'+''.join(f'<td>{ev["offset_frames"][m]:+.1f}帧</td>' for m in methods[1:])+'</tr>'
 mean=a.get('means',a.get('mean_absolute_offset_frames'))
 return out+'<tr><th>平均绝对偏移 ↓</th>'+''.join(f'<td>{mean[m]:.2f}帧</td>' for m in methods[1:])+'</tr></table><p>'+a['visual_conclusion']+'</p>'
def table(caseids):
 vals={};counts={}
 for key,_,_ in metrics:
  valid=[s for s in caseids if all(score(s,m,key) is not None for m in methods)]
  counts[key]=len(valid)
  for m in methods[1:]:vals[m,key]=statistics.mean(score(s,m,key)-(score(s,'source',key) if key=='motion_fidelity' else 0) for s in valid) if valid else None
 out='<div class="scroll"><table><thead><tr><th>方法</th>'
 for key,ab,cn in metrics:out+=f'<th class="{"mf" if key=="motion_fidelity" else ""}">{ab} ↑<small>{cn}{"·相对参考差值" if key=="motion_fidelity" else ""}</small><small>{counts[key]}/{len(caseids)}组</small></th>'
 out+='</tr></thead><tbody>'
 for m,label in zip(methods[1:],labels[1:]):
  out+='<tr><th>'+label+'</th>'
  for key,_,_ in metrics:
   v=vals[m,key];available=[vals[x,key] for x in methods[1:] if vals[x,key] is not None];mark='<b class="best"> ✓</b>' if v is not None and abs(v-max(available))<1e-10 else ''
   text='待评' if v is None else ((f'{v:+.4f}' if key=='motion_fidelity' else f'{v:.4f}')+mark)
   out+=f'<td class="{"mf" if key=="motion_fidelity" else ""}">{text}</td>'
  out+='</tr>'
 return out+'</tbody></table></div>'
records=[];sections=[]
old={r['task_id']:r for r in json.loads((D/'export.json').read_text())}
if (D/'export_completed.json').exists():old.update({r['task_id']:r for r in json.loads((D/'export_completed.json').read_text())})
with tempfile.TemporaryDirectory(prefix='h3-rope-completed-') as tmp:
 td=Path(tmp);caption=Image.new('RGB',(3072,92),'black');draw=ImageDraw.Draw(caption);font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf',28)
 for i,label in enumerate(labels):
  box=draw.textbbox((0,0),label,font=font);draw.text((i*768+(768-box[2]+box[0])/2,12-box[1]),label,font=font,fill='white')
 caption.save(td/'caption.png')
 for sid in sids:
  js=[jobs[sid,m] for m in methods];n=js[0]['valid_frames'];fps=js[0]['fps'];assert all(j['valid_frames']==n and j['fps']==fps for j in js)
  target=D/(sid+'_comparison.mp4');fingerprint=[{'id':j['id'],'sha256':j['sha256']} for j in js]
  cache_ok=target.exists() and sid in old and old[sid]['inputs']==fingerprint
  if not cache_ok:
   inputs=[];filters=[]
   for i,j in enumerate(js):
    p=td/(j['id']+'.mp4');cached=D/'visual'/sid/(j['method']+'.mp4')
    if cached.exists():shutil.copyfile(cached,p)
    else:subprocess.run(['scp','-q','H3_HOST_CONFIGURE_LOCALLY:'+j['video'],str(p)],check=True,timeout=180)
    assert hashlib.sha256(p.read_bytes()).hexdigest()==j['sha256'];inputs+=['-i',str(p)]
    x,y,w,h=j['crop_xywh'];filters.append(f'[{i}:v]trim=end_frame={n},setpts=PTS-STARTPTS,crop={w}:{h}:{x}:{y},scale=768:432:flags=lanczos,setsar=1[v{i}]')
   filters+=['[v0][v1][v2][v3]hstack=inputs=4[top]','[top][4:v]vstack=inputs=2:shortest=1[out]']
   subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',*inputs,'-loop','1','-framerate',str(fps),'-i',str(td/'caption.png'),'-filter_complex_threads','2','-filter_complex',';'.join(filters),'-map','[out]','-an','-frames:v',str(n),'-r',str(fps),'-c:v','libx264','-threads','4','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(target)],check=True,timeout=180)
   for j in js:(td/(j['id']+'.mp4')).unlink(missing_ok=True)
  probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,r_frame_rate','-of','json',str(target)]))['streams'][0]
  assert probe['width']==3072 and probe['height']==524 and int(probe['nb_frames'])==n
  mf={m:score(sid,m,'motion_fidelity') for m in methods[1:]};delta=mf['partial_temporal_rope']-mf['global_weak'] if all(mf[m] is not None for m in ['partial_temporal_rope','global_weak']) else None
  result='MF待评。' if delta is None else f'部分RoPE频带的MF相比全程α = 0.25{"提高" if delta>0 else "下降"} {abs(delta):.4f}。'
  audit=audits.get(js[-1]['id']+'__a1',{});frame_delta=audit.get('rotation',{}).get('delta_physical_frames');delta_text=f'{frame_delta:.0f}帧' if frame_delta is not None else '待核对'
  provenance=js[-1].get('prompt') or js[-1].get('prompt_provenance') or '沿用该组已冻结的条件缓存';prompt=js[-1]['metadata'].get('edit_prompt','')
  data=base64.b64encode(target.read_bytes()).decode()
  sections.append(f'<section id="{sid}"><h2>{html.escape(titles[sid])}</h2><p class="sub">IVEBench · {sid} · 官方任务：{html.escape(prompt)}</p>{evidence(sid)}<video controls playsinline preload="metadata" src="data:video/mp4;base64,{data}"></video><p>{result}</p>{event_table(sid)}{table([sid])}{awq_table(sid)}<details><summary>推理配置与提示词</summary><p>20步；α = 0.25；时间RoPE频率对8–15；本例参考与输出缓存时间原点差为{delta_text}。三种编辑沿用同组prompt、seed、模型与几何设置。</p><pre>{html.escape(provenance if isinstance(provenance,str) else json.dumps(provenance,ensure_ascii=False,indent=2))}</pre></details></section>')
  records.append({'task_id':sid,'output':str(target),'probe':probe,'inputs':fingerprint,'MF':mf,'delta_physical_frames':frame_delta,'cache_reused':cache_ok})
  print(sid,probe,'cache',cache_ok,flush=True)
valid=[s for s in sids if all(score(s,m,'motion_fidelity') is not None for m in methods[1:])]
wins=sum(score(s,'partial_temporal_rope','motion_fidelity')>score(s,'global_weak','motion_fidelity') for s in valid)
summary=f'本轮共完成{len(sids)}组。已有MF的{len(valid)}组中，部分RoPE频带有{wins}组高于全程α = 0.25。部分RoPE试验在本轮收尾，后续转入跨时刻参考覆盖。'
css='''body{margin:0;background:#f5f6f8;color:#18202b;font:16px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}main{max-width:1500px;margin:36px auto;padding:0 24px}h1{font-size:30px}h2{font-size:23px}section{background:white;border:1px solid #dce1e8;border-radius:12px;padding:24px;margin:24px 0}video{width:100%;background:black;border-radius:6px}.sub,small,figcaption{color:#667180}small{display:block;font-size:11px;font-weight:400}.scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px;white-space:nowrap}th,td{padding:12px 9px;text-align:center;border-bottom:1px solid #e6e9ee}th:first-child{text-align:left}.mf{border-left:2px solid #a8d9b8;border-right:2px solid #a8d9b8;background:#f3fbf5}thead .mf{border-top:2px solid #a8d9b8}tbody tr:last-child .mf{border-bottom:2px solid #a8d9b8}.best{color:#168c48}pre{white-space:pre-wrap;font:13px/1.6 monospace}details{margin-top:16px;color:#57616e}summary{cursor:pointer}figure{margin:16px 0}figure img{width:100%}nav{display:flex;flex-wrap:wrap;gap:8px}nav a{padding:5px 12px;border:1px solid #d3dce6;border-radius:6px;color:#315477;text-decoration:none}'''
nav=''.join(f'<a href="#{s}">{html.escape(titles[s].split("：")[-1])}</a>' for s in sids)
page=f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>部分RoPE频带 · 七组对照</title><style>{css}</style><main><h1>部分RoPE频带 · 七组对照</h1><p>{summary}</p><nav>{nav}</nav><section><h2>七组平均指标</h2>{table(sids)}<p class="sub">MF显示相对参考视频的差值，其余指标显示官方分数；绿色勾标记三种编辑中的最高值。每列注明完成组数，使用同一批配对样例求均值。QA在这些任务中不适用。IS/CF使用独立的4-bit AWQ配置，Baseline与α = 0.25沿用.41评分，部分RoPE在.60采用CPU跨卡转运配置。</p><h3>已测动作偏移 · 2/7组</h3><table><tr><th>样例</th><th>Baseline</th><th>α = 0.25</th><th>部分RoPE频带</th></tr>'
for sid,a in annotations.items():
 mean=a.get('means',a.get('mean_absolute_offset_frames'));page+='<tr><th>'+titles[sid].split('：')[-1]+'</th>'+''.join(f'<td>{mean[m]:.2f}帧</td>' for m in methods[1:])+'</tr>'
page+='</table><p class="sub">动作偏移采用原有逐帧标注的事件过渡区间中点差；表内为平均绝对偏移，越低越好。其余5组动作偏移未测。</p></section>'+''.join(sections)+'</main></html>'
target=R/'H3_部分RoPE频带_两组对照_20261022.html';target.write_text(page)
(D/'export_completed.json').write_text(json.dumps(records,ensure_ascii=False,indent=2));(D/'summary_completed.json').write_text(json.dumps({'cases':len(sids),'MF_complete':len(valid),'partial_beats_weak':wins,'visual_annotated':2,'html':str(target),'bytes':target.stat().st_size},ensure_ascii=False,indent=2))
print(target,target.stat().st_size)
