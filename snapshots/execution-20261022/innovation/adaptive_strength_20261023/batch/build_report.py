#!/usr/bin/env python3
"""Build an offline report from verified collector evidence. Never touch queues or GPUs."""
from __future__ import annotations
import argparse, base64, hashlib, json, math, shutil, subprocess
from collections import Counter
from datetime import datetime
from html import escape as esc
from html.parser import HTMLParser
from pathlib import Path

B=Path(__file__).resolve().parent
E=B.parents[2]
REPO=E.parent
TITLE='H3 动态强度与跨时刻混合'
METHODS={'dynamic_dof':'DOF 动态强度（已搁置）','dynamic_anchor':'首步锚归一化动态强度','heads_budget':'Head 等能量分配','coverage_blend25':'跨时刻混合（25%）','fixed0375':'固定强度 α = 0.375','temporal_gain_field':'逐时间片动态强度','temporal_gain_field_role5':'同位置组切向动态强度（边界原算子）','causal_layer_budget':'基于前一步统计的层强度分配'}
TASKS={'short_0252':'机舱 · 男性替换为年长女性','short_0358':'饮酒 · 为男性添加眼镜', 'long_0039':'书本 · 将书本改为蓝色', 'long_0059':'擦泪 · 在男性手中添加白手帕'}
STATUS={'verified':'完成并核验','in_progress':'推理中','pending':'待执行','research_hold':'已搁置','attention_required':'待核查'}
METRICS=[
 ('subject_consistency','主体一致性','同一视频内主体特征的跨帧一致程度。'),
 ('background_consistency','背景一致性','同一视频内背景特征的跨帧一致程度。'),
 ('temporal_flickering','时序闪烁评分','相邻帧亮度变化等形成的稳定性评分。'),
 ('motion_smoothness','运动平滑度','帧间运动的平滑程度。'),
 ('vtss','训练适宜性评分 VTSS','官方 training_suitability_assessment 模型输出的视频综合质量分数。'),
 ('overall_semantic_consistency','整体语义一致性','编辑后视频与目标整体描述的语义一致程度。'),
 ('phrase_semantic_consistency','短语语义一致性','编辑后视频与目标编辑短语的语义一致程度。'),
 ('semantic_fidelity','语义保真','编辑结果与源视频的语义特征保留程度。'),
 ('motion_fidelity','动作保真 MF','编辑结果相对源视频的运动特征保留程度。')]
INPUTS={}
MEDIA=[]

def sha(b): return hashlib.sha256(b).hexdigest()
def read(p):
 b=p.read_bytes();INPUTS[str(p.relative_to(E)) if p.is_relative_to(E) else p.name]=sha(b);return json.loads(b)
def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def num(x,d=4,signed=False):return (f'{x:+.{d}f}' if signed else f'{x:.{d}f}') if finite(x) else '待测'
def unique(rows,key):
 out={}
 for r in rows:
  if r[key] in out:raise ValueError(f'duplicate {key}: {r[key]}')
  out[r[key]]=r
 return out
def score(r,k):
 m=r.get('metrics',{}).get(k,{})
 return m.get('score') if m.get('status')=='done' and finite(m.get('score')) else None
def video_sha(r):
 h={m.get('actual_sha256') for m in r.get('media',[]) if m.get('status')=='verified'};h.discard(None)
 if len(h)!=1:raise ValueError('expected one verified output video')
 return next(iter(h))
def embed(p,mime,jid,expected=None):
 b=p.read_bytes();h=sha(b)
 if expected and h!=expected:raise ValueError('media SHA mismatch')
 rec={'name':p.name,'job_id':jid,'mime':mime,'sha256':h,'bytes':len(b)}
 if mime=='video/mp4':
  probe=shutil.which('ffprobe')
  if not probe:raise RuntimeError('ffprobe required')
  rec['ffprobe']=json.loads(subprocess.check_output([probe,'-v','error','-select_streams','v:0','-show_entries','stream=width,height,codec_name,avg_frame_rate,nb_frames:format=duration','-of','json',str(p)],text=True))
 MEDIA.append(rec)
 return f'data:{mime};base64,'+base64.b64encode(b).decode('ascii')
def annotation(r,v,prov):
 if not (v/'ANNOTATION.json').exists():return None,None
 a=read(v/'ANNOTATION.json')
 if (a.get('job_id'),a.get('method'),a.get('video_sha256'))!=(r['job_id'],r['method'],video_sha(r)):raise ValueError('annotation identity mismatch')
 oldp=E/f'timing/event_offset_completion_20261022/{r["task_id"]}/ANNOTATION.json'
 if not oldp.exists():return a,None
 old=read(oldp)
 for role in ('source','native','global_weak'):
  expected=old.get('video_provenance',{}).get(role,{}).get('sha256')
  actual=next((x['sha256'] for x in prov['controls'] if x['id']==f'{r["task_id"]}__{role}'),None)
  if not expected or actual!=expected:raise ValueError('frozen control SHA mismatch')
 oe=unique(old['events'],'id');ne=unique(a['events'],'id')
 if set(oe)!=set(ne) or not ne:raise ValueError('frozen events changed')
 vals=[]
 for k,e in ne.items():
  if e['source_interval']!=oe[k]['source']:raise ValueError('source interval changed')
  if isinstance(e.get('new_interval'),list):
   off=sum(e['new_interval'])/2-sum(e['source_interval'])/2
   if not math.isclose(off,e['signed_offset_frames'],abs_tol=1e-9):raise ValueError('offset mismatch')
   vals.append(abs(off))
 if len(vals)==len(ne):
  if not math.isclose(sum(vals)/len(vals),a['mean_absolute_offset_frames'],abs_tol=1e-9):raise ValueError('mean offset mismatch')
 elif a.get('mean_absolute_offset_frames') is not None:raise ValueError('incomplete event set has a numerical mean')
 return a,old

def text(x,y,s,size=16,color='#22313d',extra=''):
 return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" {extra}>{esc(s)}</text>'
def start(w,h,name):
 return f'<svg class="mechanism" viewBox="0 0 {w} {h}" role="img" aria-label="{name}" xmlns="http://www.w3.org/2000/svg"><title>{name}</title><defs><marker id="arrow-{name}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="#567389"/></marker></defs>'
def matrix(x,y,a,cell=26,labels=True):
 out=[]
 for i,row in enumerate(a):
  for j,v in enumerate(row):
   f=max(0,min(1,v));col=f'rgb({round(239-210*f)},{round(246-134*f)},{round(250-91*f)})'
   out.append(f'<rect x="{x+j*cell}" y="{y+i*cell}" width="{cell-1}" height="{cell-1}" fill="{col}"><title>示意 [{i},{j}]={v:.3f}</title></rect>')
   if labels:out.append(text(x+(j+.5)*cell,y+(i+.66)*cell,f'{v:.2f}'.lstrip('0'),cell*.31,'white' if v>.55 else '#264d65','text-anchor="middle"'))
 return ''.join(out)
def diagrams():
 a=[start(1120,585,'anchor'),text(24,30,'01  首步锚归一化：在当前 Attention 特征内调节强度',22),text(24,56,'n = 去噪步；t = 视频物理时间 bin；每层各有独立首步锚。下图为机制示意。',14,'#627382'),text(24,95,'相同输出 query Qₜ',17),text(24,122,'全多模态 Attention → O',15),text(24,150,'参考视频条件输出',15),matrix(24,168,[[.06,.10,.24,.44,.11,.05],[.05,.08,.16,.40,.22,.09],[.03,.04,.13,.24,.43,.13]],28,False),text(24,273,'全部参考 → R；同一时刻 → Sₜ',14),text(24,299,'m = exp(LSEref − LSEfull)',16),text(24,328,'D = m (Sₜ − R)',22,'#146c94'),'<path d="M237 211L296 211" stroke="#567389" stroke-width="2" marker-end="url(#arrow-anchor)"/>',text(303,95,'Qₜ 固定，只移动参考 K/V 时间',17)]
 for i,cap in enumerate(('t−1','t','t+1')):
  x=305+i*79
  a.extend([f'<rect x="{x}" y="118" width="58" height="64" rx="3" fill="{["#d5e8ed","#8dbccf","#d5e8ed"][i]}"/>',text(x+29,146,cap,17,extra='text-anchor="middle"'),text(x+29,169,('S₋','Sₜ','S₊')[i],16,extra='text-anchor="middle"')])
 a.extend([text(306,211,'b = S₊ − S₋',20),'<line x1="317" y1="326" x2="523" y2="326" stroke="#a5bac6"/><line x1="317" y1="326" x2="502" y2="246" stroke="#146c94" stroke-width="3" marker-end="url(#arrow-anchor)"/><line x1="317" y1="326" x2="493.6" y2="249.6" stroke="#259b83" stroke-width="6"/><line x1="317" y1="326" x2="480" y2="218" stroke="#9a623d" stroke-width="3" marker-end="url(#arrow-anchor)"/><line x1="480" y1="218" x2="493.6" y2="249.6" stroke="#9a623d" stroke-dasharray="4 4"/>',text(500,237,'b',17,'#146c94'),text(478,209,'D',17,'#9a623d'),text(372,297,'Dᵀ',15,'#167661'),text(501,229,'Dᴺ',15,'#9a623d'),text(304,355,'Dᵀ = b ⟨D,b⟩ / ‖b‖²',17),text(304,382,'Dᴺ = D − Dᵀ',17),text(304,409,'A = Σ‖Dᵀ‖²   B = Σ‖Dᴺ‖²',17),'<path d="M554 211L594 211" stroke="#567389" stroke-width="2" marker-end="url(#arrow-anchor)"/>',text(611,95,'首个有效步冻结 A₀、B₀',17),text(611,123,'vT = A/A₀；vN = B/B₀',18),text(611,151,'v = (vT + vN)/2',18),text(611,185,'α₀ = .25；c = (1−α₀)/α₀ = 3；μ = 1',15),'<path d="M616 208V276H1057" fill="none" stroke="#cad7dc"/><path d="M616 248Q700 239 748 226T878 239T1052 214" fill="none" stroke="#218a79" stroke-width="2"/><path d="M616 248Q725 255 803 246T948 255T1052 242" fill="none" stroke="#ab7653" stroke-width="2"/><circle cx="616" cy="248" r="5" fill="#22313d"/>',text(629,232,'锚 = 1',13),text(1010,207,'vT',14,'#218a79'),text(1010,265,'vN',14,'#ab7653'),text(636,300,'示意：比较相对首步的变化，非实测曲线',13,'#627382'),text(611,342,'J = (1−α)²vT + 3α²vN + (α−.25)²v',18),text(611,380,'α* = clip [ (vT + .25v)/(vT + 3vN + v), 0, .5 ]',18),text(24,462,'合并 heads → Wₒ [ O + α* D ]',24,'#146c94'),text(24,495,'首个有效步与无可靠统计时使用 .25；锚在同一 layer / run 内固定。',16),text(24,523,'仅增两次小 query 邻时刻 Attention；不增加 DiT / VAE 前向。统计排除有效窗口首尾 probe。',15,'#627382'),text(24,551,'A / B 描述局部时间变化方向及其正交补；正交补也包含非线性运动、遮挡等变化。',15,'#627382'),'</svg>'])
 h=[start(1120,330,'heads'),text(24,31,'02  Head 分配：总修正能量不变，重新分配系数',22),text(24,58,'Cₕ = Σ‖Dₕ‖² 使用完整分辨率；fₕ 用 probe 中时间切向能量占比估计。',15,'#627382'),text(24,99,'固定 .25',18),text(24,125,'每个 head 的 α 相同',14,'#627382')]
 for i,(old,new) in enumerate(zip([.12,.28,.19,.41],[.26,.08,.51,.15])):
  x=170+i*64
  h.extend([f'<rect x="{x}" y="{253-old*240}" width="39" height="{old*240}" fill="#90b9ce"/>',text(x+19,276,f'h{i+1}',13,extra='text-anchor="middle"'),f'<rect x="{x+389}" y="{253-new*240}" width="39" height="{new*240}" fill="#258d7d"/>',text(x+408,276,f'h{i+1}',13,extra='text-anchor="middle"')])
 h.extend([text(499,99,'重新分配',18),text(499,125,'柱高 = Cₕ αₕ²；总面积相同',14,'#627382'),text(817,108,'max Σ Cₕ fₕ αₕ',19),text(817,148,'Σ Cₕ αₕ² = .25² Σ Cₕ',19),text(817,185,'0 ≤ αₕ ≤ .5',19),text(817,224,'αₕ = min(τ fₕ, .5)',19,'#146c94'),text(817,253,'τ 由能量预算求得',14,'#627382'),text(24,312,'能量口径：head 拼接 / Wₒ 之前。柱图仅示意；实际系数见运行日志热图。',15,'#627382'),'</svg>'])
 p=[[.6,.3,.1,0],[.3,.4,.2,.1],[.1,.2,.4,.3],[0,.1,.3,.6]];ident=[[float(i==j) for j in range(4)] for i in range(4)];mixed=[[.75*ident[i][j]+.25*p[i][j] for j in range(4)] for i in range(4)]
 c=[start(1120,340,'coverage'),text(24,31,'03  跨时刻混合：保留主要同时间约束，允许有限跨时间取用',22),text(24,59,'P 为跨时间参考混合；Pmix = .75 I + .25 P。下图数值为双随机矩阵示意。',15,'#627382'),text(43,96,'同时间 I',18),matrix(24,111,ident,37),text(201,189,'× .75  +',23),text(334,96,'跨时刻 P',18),matrix(314,111,p,37),text(489,189,'× .25  =',23),text(626,96,'混合 Pmix',18),matrix(605,111,mixed,37),text(793,129,'每行 / 每列之和为 1',17),text(793,162,'对角线至少 .75',17,'#146c94'),text(793,196,'跨时间质量最多 .25',17),text(793,230,'α 仍固定为 .25',17),text(24,295,'S̃ₜ = Σⱼ Pmix[t,j] Attn(Qₜ,Kⱼ,Vⱼ)     O′ = O + .25 m (S̃ₜ − R) → Wₒ',21,'#146c94'),text(24,324,'本组单独改变参考时间路由，保持全局强度；与首步锚、head 分配分别实验。',15,'#627382'),'</svg>']
 return {'anchor':''.join(a),'heads':''.join(h),'coverage':''.join(c)}

def heatmap(curve,row):
 points={};compact=[]
 keys=('step','layer','alpha_mean','alpha_min','alpha_max','reference_mass_mean','temporal_energy','complement_energy','anchor_temporal','anchor_complement','normalized_temporal','normalized_complement','anchor_step','anchor_created','used_anchor','fallback','valid_probe_count','correction_energy','applied_energy','boundary_probes_excluded')
 for p in curve.get('points',[]):
  s,l=p.get('step'),p.get('layer')
  if not isinstance(s,int) or not isinstance(l,int) or not (0<=s<20 and 0<=l<50):raise ValueError('invalid alpha indices')
  if (s,l) in points:raise ValueError('duplicate alpha point')
  if not finite(p.get('alpha_mean')) or not 0<=p['alpha_mean']<=.500001:raise ValueError('invalid alpha')
  points[s,l]=p;q={k:p[k] for k in keys if p.get(k) is not None}
  unit='video_bins' if row['method'] in ('temporal_gain_field','temporal_gain_field_role5') else 'heads'
  q[unit+'_recorded']=len(p.get('alpha') or [])
  if row['method'] in ('temporal_gain_field','temporal_gain_field_role5'):q['alpha_by_video_bin']=p['alpha']
  compact.append(q)
 if row['status']=='verified' and row['method']!='coverage_blend25' and len(points)!=1000:raise ValueError('incomplete 20x50 audit for completed feature case')
 cells=[]
 for s in range(20):
  for l in range(50):
   p=points.get((s,l));v=p.get('alpha_mean') if p else None
   if v is None:col='#e0e4e7';tip=f'去噪步 {s+1} / DiT 层 {l+1}：未记录'
   else:
    f=max(0,min(1,v/.5));col=f'rgb({round(238-214*f)},{round(247-143*f)},{round(249-90*f)})'
    tip=f'去噪步 {s+1} / DiT 层 {l+1}（原索引 {s}, {l}）\nα 均值 {v:.6f}；min {p.get("alpha_min",v):.6f}；max {p.get("alpha_max",v):.6f}'
    for k,cn in [('temporal_energy','A'),('complement_energy','B'),('anchor_temporal','A₀'),('anchor_complement','B₀'),('normalized_temporal','vT/(vT+vN)'),('normalized_complement','vN/(vT+vN)')]:
     if finite(p.get(k)):tip+=f'\n{cn} = {p[k]:.7g}'
    if p.get('fallback') is not None:tip+=f'\nfallback = {p["fallback"]}'
   cells.append(f'<rect class="heatcell" x="{62+l*19}" y="{38+s*13}" width="18" height="12" fill="{col}" data-tip="{esc(tip,quote=True)}"><title>{esc(tip)}</title></rect>')
 labels=''.join(text(62+(l-.5)*19,24,str(l),12,extra='text-anchor="middle"') for l in (1,10,20,30,40,50))
 labels+=''.join(text(50,47+(s-1)*13,str(s),12,extra='text-anchor="end"') for s in (1,5,10,15,20))+text(535,329,'DiT 层（1–50）',13,extra='text-anchor="middle"')
 svg='<svg class="heatmap" viewBox="0 0 1030 345" role="img" aria-label="实际采样20步50层alpha热图" xmlns="http://www.w3.org/2000/svg">'+labels+''.join(cells)+'</svg>'
 st=row.get('live_alpha_statistics') or {};info=f'已记录 {len(points)} / 1000 个 step × layer；α 均值 {num(st.get("mean"),6)}，范围 [{num(st.get("min"),6)}, {num(st.get("max"),6)}]。'
 averaging='视频时间片' if row['method'] in ('temporal_gain_field','temporal_gain_field_role5') else 'head'
 result='<div class="heatwrap">'+svg+'<div class="legend"><span>0</span><i></i><span>.5</span><span class="missing"></span>未记录</div><p class="small">'+info+' 悬停查看数值；每格为该层各 '+averaging+' 的均值。纵轴为去噪步。</p></div>'
 if row['method'] in ('temporal_gain_field','temporal_gain_field_role5') and points:
  layers=sorted({l for s,l in points});payload=[dict(step=s,layer=l,alpha=p['alpha']) for (s,l),p in sorted(points.items())]
  for p in payload:
   if not p['alpha'] or not all(finite(v) and 0<=v<=.500001 for v in p['alpha']):raise ValueError('invalid measured video-bin coefficients')
  pid='bin-data-'+row['job_id']
  result+='<div class="binplot" data-values="'+esc(pid)+'"><label>查看 DiT 层 <select>'+''.join(f'<option value="{l}">{l+1}</option>' for l in layers)+'</select></label><svg class="heatmap" viewBox="0 0 1030 345" role="img" aria-label="去噪步与视频时间片的实际强度"></svg><p class="small">横轴为视频时间片，纵轴为去噪步。每格是实际施加的 α；灰色为尚未产生的数据。首尾时间片保持 .25。</p></div><script type="application/json" id="'+esc(pid)+'">'+json.dumps(payload,separators=(',',':')).replace('<','\\u003c')+'</script>'
 return result,compact

def interval(x,ref):
 if not isinstance(x,list) or len(x)!=2:return '<span class="muted">待检查</span>'
 d=sum(x)/2-sum(ref)/2;return f'{x[0]}–{x[1]} <small>({d:+g})</small>'
def events_table(a,old):
 if not a or not old:return '<p class="pending">逐帧事件标注待检查；当前不填偏移值。</p>'
 ne=unique(a['events'],'id');rows=[]
 for e in old['events']:
  n=ne.get(e['id'],{})
  rows.append('<tr><th>'+esc(e['label'])+'</th><td>'+f'{e["source"][0]}–{e["source"][1]}'+'</td>'+''.join('<td>'+interval(e.get(r),e['source'])+'</td>' for r in ('native','global_weak'))+'<td>'+interval(n.get('new_interval'),e['source'])+'</td></tr>')
 means=[]
 for role in ('native','global_weak'):
  vals=[abs(sum(e[role])/2-sum(e['source'])/2) for e in old['events'] if isinstance(e.get(role),list)];means.append(sum(vals)/3 if len(vals)==3 else None)
 rows.append('<tr class="summaryrow"><th>平均绝对偏移 / 帧</th><td>0</td>'+''.join(f'<td>{num(v,3)}</td>' for v in means)+f'<td>{num(a.get("mean_absolute_offset_frames"),3)}</td></tr>')
 return '<div class="tablewrap"><table><thead><tr><th>冻结的事件定义</th><th>参考视频</th><th>普通编辑</th><th>固定 .25</th><th>本次方法</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div><p class="small">24 fps、从第 0 帧编号；表内为转折区间，括号为相对参考的区间中点偏移（正值滞后，负值提前）。'+esc(a.get('uncertainty',''))+'</p>'
def metrics_table(case):
 if not case:return '<p class="pending">官方指标待测。</p>'
 recs=[case.get('controls',{}).get(r,{}) for r in ('source','native','global_weak')]+[case];rows=[]
 for k,cn,desc in METRICS:
  rows.append('<tr><th title="'+esc(desc,quote=True)+'">'+cn+'<small>'+k+'</small></th>'+''.join('<td>'+num(score(r,k),6)+'</td>' for r in recs)+'</tr>')
 ref=score(recs[0],'motion_fidelity');ds=[score(r,'motion_fidelity')-ref if score(r,'motion_fidelity') is not None and ref is not None else None for r in recs]
 rows.append('<tr class="summaryrow"><th>MF − 参考视频自比较值</th>'+''.join('<td>'+num(v,6,True)+'</td>' for v in ds)+'</tr>')
 counts=[sum(score(r,k) is not None for k,_,_ in METRICS) for r in recs]
 out='<div class="tablewrap"><table><thead><tr><th>官方原始指标</th><th>参考视频</th><th>普通编辑</th><th>固定 .25</th><th>本次方法</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
 return out+'<p class="small">九项完成数（参考 / 普通 / .25 / 本次）：'+' / '.join(str(c)+'/9' for c in counts)+'。读取真实 evaluation.rows，保留官方原始尺度。</p>'

def awq_table(case,row,prov,awq):
 """Join separate AWQ results only after matching the exact rendered video SHA."""
 entries=[];rows=[]
 expected={x['id']:x['sha256'] for x in prov.get('controls',[])}
 expected[row['job_id']]=video_sha(row)
 for role,label in [('native','普通编辑'),('global_weak','固定 .25'),('new','本次方法')]:
  jid=row['job_id'] if role=='new' else case.get('controls',{}).get(role,{}).get('job_id',f'{row["task_id"]}__{role}')
  rec=awq.get('jobs',{}).get(jid,{})
  if rec and (rec.get('job_id')!=jid or rec.get('task_id')!=row['task_id']):raise ValueError('AWQ job/task identity mismatch')
  metrics=[]
  for k in ('IS','CF'):
   m=rec.get('metrics',{}).get(k,{})
   item={'metric':k,'status':m.get('status','pending')}
   if m.get('status')=='done':
    if not finite(m.get('score')) or not 1<=m['score']<=5:raise ValueError('AWQ score outside official 1-5 scale')
    if not expected.get(jid) or m.get('input_video_sha256')!=expected[jid]:raise ValueError('AWQ evaluated a different video')
    evaluator=m.get('evaluator',{});cfg=m.get('configuration_id')
    if not cfg or cfg!=evaluator.get('configuration_id'):raise ValueError('AWQ evaluator configuration mismatch')
    item.update(score=m['score'],input_video_sha256=m['input_video_sha256'],configuration_id=cfg,official_commit=m.get('official_commit'),original_result_file_sha256=m.get('original_result_file_sha256'),evaluator={k:evaluator.get(k) for k in ('configuration_id','model_id','revision','quantization_config','load_quantization_config','dtype','torch_dtype_requested','dense_checkpoint_modules','original_precision_reproduction','packages')})
   elif m.get('status') not in (None,'pending','not_applicable'):raise ValueError('Invalid AWQ input status')
   metrics.append(item)
  values=''.join('<td>'+num(m.get('score'),2)+'</td>' for m in metrics)
  configs='<br>'.join(esc(m['metric'])+': <span class="evidence">'+esc(m.get('configuration_id','待测'))+'</span>' for m in metrics)
  rows.append('<tr><th>'+label+'</th>'+values+'<td>'+configs+'</td></tr>')
  entries.append({'job_id':jid,'label':label,'metrics':metrics})
 qa=case.get('quantity_accuracy',{})
 qatxt='不适用（本例不涉及数量修改）' if qa.get('status')=='not_applicable' else '待核查'
 html='<h3>独立 AWQ 评测 · IS / CF</h3><div class="tablewrap"><table><thead><tr><th>视频</th><th>指令满足 IS</th><th>内容保真 CF</th><th>实际评测配置</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div><p class="small">原始 1–5 分。每项保留实际 Qwen2.5-VL-72B AWQ 配置；不同配置不合并均值。CPU bridge 与原执行配置分别标识。数量准确性 QA：'+qatxt+'。</p><details><summary>AWQ 模型、量化、版本与输入校验</summary><pre>'+esc(json.dumps(entries,ensure_ascii=False,indent=2))+'</pre></details>'
 return html,entries

def conclusions(rows,anns,cases):
 by=unique(rows,'job_id');out=[];d=by.get('adapt41_short_0252_dynamic_dof',{});a=anns.get(d.get('job_id'),(None,None))[0];s=d.get('live_alpha_statistics') or {}
 if d.get('status')=='verified' and s.get('recorded_layer_calls')==1000 and s.get('min')==s.get('max')==.5:
  out.append('<strong>DOF 归一化已搁置。</strong>机舱样例的 20 步 × 50 层全部取 α = .5，控制器退化为固定强度。'+('三个事件偏移均为 0 帧，与固定 .25 相同。' if a and a.get('mean_absolute_offset_frames')==0 else '事件对齐情况见下方标注。'))
 f=by.get('adapt41_short_0358_fixed0375',{});a,o=anns.get(f.get('job_id'),(None,None))
 if f.get('status')=='verified' and a and o:
  out.append(f'<strong>增强固定强度后，饮酒样例的时序表现接近。</strong>α = .375 的三事件平均绝对偏移为 {num(a.get("mean_absolute_offset_frames"),3)} 帧，固定 .25 为 {num(o.get("means",{}).get("global_weak"),3)} 帧；两者接近。')
 hd=by.get('adapt41_short_0252_heads_budget',{});ha=anns.get(hd.get('job_id'),(None,None))[0];hc=cases.get(hd.get('job_id'),{})
 if hd.get('status')=='verified':
  mf=score(hc,'motion_fidelity');weak=score(hc.get('controls',{}).get('global_weak',{}),'motion_fidelity')
  finding='<strong>Head 分配已产生不同系数。</strong>'
  if ha:finding+=f'机舱三事件平均绝对偏移 {num(ha.get("mean_absolute_offset_frames"),3)} 帧。'
  if mf is not None and weak is not None:finding+=f'MF 为 {num(mf,6)}，固定 .25 为 {num(weak,6)}（差 {num(mf-weak,6,True)}）。'
  else:finding+='官方指标待测。'
  out.append(finding)
 anchors=[r for r in rows if r['method']=='dynamic_anchor' and r['status']=='verified']
 if anchors:
  detail=[]
  for r in anchors:
   a,o=anns.get(r['job_id'],(None,None));c=cases.get(r['job_id'],{});st=r.get('live_alpha_statistics') or {};mf=score(c,'motion_fidelity');weak=score(c.get('controls',{}).get('global_weak',{}),'motion_fidelity')
   x=TASKS.get(r['task_id'],r['task_id']).split(' · ')[0]+'：实测 α 均值 '+num(st.get('mean'),4)+'。'
   if a and o:x+='平均绝对偏移 '+num(a.get('mean_absolute_offset_frames'),3)+' 帧，固定 .25 为 '+num(o.get('means',{}).get('global_weak'),3)+' 帧。'
   if mf is not None and weak is not None:x+='MF '+num(mf,6)+'，相对固定 .25 为 '+num(mf-weak,6,True)+'。'
   detail.append(x)
  below=all(score(cases.get(r['job_id'],{}),'motion_fidelity') is not None and score(cases.get(r['job_id'],{}).get('controls',{}).get('global_weak',{}),'motion_fidelity') is not None and score(cases[r['job_id']],'motion_fidelity')<score(cases[r['job_id']]['controls']['global_weak'],'motion_fidelity') for r in anchors)
  finding='<strong>首步锚归一化已产生动态强度。</strong>'+''.join(detail)
  drink=next((r for r in anchors if r['task_id']=='short_0358'),None)
  if drink:
   a,o=anns.get(drink['job_id'],(None,None))
   if a and o and abs(a['mean_absolute_offset_frames']-o['means']['global_weak'])<.5:finding+='饮酒的偏移差小于标注区间，时序表现接近。'
  if below:finding+='本批 '+str(len(anchors))+' 例 MF 均低于固定 .25。'
  out.insert(0,finding)
 pending=sum(r['method']=='dynamic_anchor' and r['status']!='verified' for r in rows)
 if pending:out.append(f'<strong>首步锚归一化是下一项验证。</strong>用当前层首次有效 A₀、B₀ 校准相对变化，替代按通道自由度校准。{pending} 个锚归一化任务尚未形成已核验成片。')
 for method,title in [('temporal_gain_field','逐时间片动态强度'),('temporal_gain_field_role5','同位置组切向动态强度'),('causal_layer_budget','按层强度分配')]:
  completed=[r for r in rows if r['method']==method and r['status']=='verified']
  if not completed:continue
  details=[]
  for r in completed:
   a,o=anns.get(r['job_id'],(None,None));c=cases.get(r['job_id'],{})
   mf=score(c,'motion_fidelity');weak=score(c.get('controls',{}).get('global_weak',{}),'motion_fidelity')
   line=TASKS[r['task_id']].split(' · ')[0]+'：'
   if mf is not None and weak is not None:line+='MF '+num(mf,6)+'，相对固定 .25 '+num(mf-weak,6,True)+'；'
   else:line+='官方指标待测；'
   line+='事件平均偏移 '+num(a.get('mean_absolute_offset_frames') if a else None,3)+' 帧。'
   details.append(line)
  out.insert(0,'<strong>'+title+'已完成 '+str(len(completed))+' 例。</strong>'+''.join(details))
 if not out:out.append('按已核验成片、真实指标和逐帧标注更新；当前结果见下方案例表。')
 return '<ol class="findings">'+''.join('<li>'+x+'</li>' for x in out)+'</ol>'

def paired_summary(rows,anns,cases):
 """One row per completed video; use the same frozen controls and events."""
 result=[]
 for r in rows:
  if r['status']!='verified':continue
  jid=r['job_id'];c=cases.get(jid,{});a,old=anns.get(jid,(None,None))
  mf=score(c,'motion_fidelity');w=score(c.get('controls',{}).get('global_weak',{}),'motion_fidelity')
  offset=a.get('mean_absolute_offset_frames') if a else None
  wo=old.get('means',{}).get('global_weak') if old else None
  result.append('<tr><td>'+esc(TASKS[r['task_id']].split(' · ')[0])+'</td><td><a href="#'+esc(jid)+'">'+esc(METHODS[r['method']])+'</a></td><td>'+num(mf,6)+'</td><td>'+num(mf-w if mf is not None and w is not None else None,6,True)+'</td><td>'+num(offset,3)+'</td><td>'+num(wo,3)+'</td></tr>')
 return '<h3>同样例配对结果</h3><div class="tablewrap"><table><thead><tr><th>样例</th><th>本次方法</th><th>MF</th><th>MF − 固定 .25</th><th>本次偏移 / 帧</th><th>固定 .25 偏移 / 帧</th></tr></thead><tbody>'+''.join(result)+'</tbody></table></div><p class="small">偏移为每个样例全部预先固定事件的平均绝对时间偏移，越低越好。机舱固定 .25 已为 0 帧，饮酒为 1.333 帧；小于事件标注区间宽度的差值按表现接近处理。</p>'

CSS='''
:root{--ink:#21313d;--muted:#647584;--blue:#146c94;--line:#dce3e7}*{box-sizing:border-box}body{margin:0;color:var(--ink);background:#f3f5f5;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Noto Sans CJK SC",sans-serif;line-height:1.7;font-size:16px}main{max-width:1180px;margin:auto;padding:48px 30px 80px}header{border-top:5px solid var(--blue);padding:28px 0 25px}h1{font-size:38px;line-height:1.3;margin:4px 0 13px}h2{font-size:25px;line-height:1.4;margin:0 0 18px}h3{font-size:20px;margin:22px 0 12px}p{margin:9px 0 16px}.eyebrow{letter-spacing:2px;font-size:12px;color:var(--blue);font-weight:700}.lede{font-size:18px}.small,small{font-size:13px;color:var(--muted)}small{display:block}.muted{color:var(--muted)}section{margin:25px 0;padding:28px;background:white;border:1px solid var(--line);border-radius:8px}.findings{padding-left:24px;margin:0}.findings li{padding:5px 0 13px}.nav{display:flex;gap:18px;flex-wrap:wrap;margin-top:20px}a{color:var(--blue)}.stats{display:flex;gap:10px;flex-wrap:wrap}.stat{padding:8px 14px;border-radius:4px;background:#eaf0f3;font-size:14px}.stat b{font-size:20px;margin-right:6px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:right;vertical-align:top;font-variant-numeric:tabular-nums}th:first-child,td:first-child{text-align:left}thead th{background:#f0f4f6;font-weight:600}tbody th{font-weight:500;text-align:left}tbody th small{font-size:11px;word-break:break-word}.summaryrow th,.summaryrow td{background:#edf5f6;font-weight:600}.tablewrap{overflow-x:auto;margin:13px 0}video{display:block;width:100%;max-height:760px;background:#000;border-radius:5px}.videocaption{margin-top:8px;font-size:13px;color:var(--muted)}.mechanism,.heatmap{display:block;width:100%;height:auto;font-family:inherit}.mechanism{border:1px solid #e2e8eb;border-radius:6px;background:#fcfefe;margin:18px 0 10px}.badge{display:inline-block;font-size:12px;padding:3px 8px;border-radius:12px;background:#e5eff2;color:#19617b;margin-left:8px}.pending{color:#8a622f;background:#fff7e8;border-left:3px solid #d8a650;padding:10px 15px}details{margin:16px 0;border-top:1px solid var(--line);padding-top:12px}summary{cursor:pointer;font-weight:600;color:#385969}pre{white-space:pre-wrap;word-break:break-word;font-size:12px;background:#f4f6f7;padding:12px}dl{display:grid;grid-template-columns:minmax(160px,230px) 1fr;gap:7px 20px;font-size:14px}dt{font-weight:600}dd{margin:0}.heatwrap{padding:8px 0}.heatcell{cursor:crosshair}.heatcell:hover{stroke:#fb970b;stroke-width:2}.legend{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--muted);justify-content:flex-end}.legend i{display:block;width:160px;height:10px;background:linear-gradient(90deg,#eef7f9,#18689f)}.legend .missing{width:14px;height:10px;background:#e0e4e7;margin-left:16px}#tooltip{display:none;position:fixed;pointer-events:none;white-space:pre-line;z-index:9;background:#173246;color:white;padding:10px 13px;border-radius:5px;font-size:12px;line-height:1.5;max-width:330px;box-shadow:0 5px 20px #0002}.eventnote{border-left:3px solid #368b91;padding-left:14px}.casehead{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.casehead h2{margin-bottom:5px}.metrics-strip{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}.metrics-strip span{background:#eff5f7;padding:9px 13px;border-radius:4px;font-size:14px}.definitiongrid{display:grid;grid-template-columns:1fr 1fr;gap:8px 25px;font-size:14px}.definitiongrid p{margin:0}.evidence{font-family:ui-monospace,monospace;font-size:11px;word-break:break-all}.footer{font-size:12px;color:var(--muted);margin-top:26px}button{border:1px solid #b4c9d1;background:#f2f7f9;color:#245d78;padding:6px 10px;border-radius:4px;cursor:pointer}.speed{display:flex;gap:6px;align-items:center;margin-top:10px;font-size:13px}
@media(max-width:700px){main{padding:20px 12px 40px}section{padding:18px 12px}h1{font-size:29px}h2{font-size:22px}.lede{font-size:16px}th,td{padding:8px;font-size:12px}dl,.definitiongrid{grid-template-columns:1fr}.casehead{display:block}.mechanism{min-width:780px}.diagramscroll{overflow-x:auto}}@media print{body{background:white}main{max-width:none;padding:0}section{break-inside:avoid}video{max-height:450px}nav,.speed{display:none}}
'''
JS='''
const tip=document.getElementById('tooltip');document.querySelectorAll('.heatcell').forEach(c=>{c.addEventListener('pointermove',e=>{tip.textContent=c.dataset.tip;tip.style.display='block';tip.style.left=Math.max(4,Math.min(e.clientX+14,innerWidth-344))+'px';tip.style.top=Math.max(4,Math.min(e.clientY+14,innerHeight-tip.offsetHeight-10))+'px';});c.addEventListener('pointerleave',()=>tip.style.display='none');});document.querySelectorAll('[data-speed]').forEach(b=>b.addEventListener('click',()=>{document.getElementById(b.dataset.video).playbackRate=Number(b.dataset.speed)}));
document.querySelectorAll('.binplot').forEach(plot=>{
 const data=JSON.parse(document.getElementById(plot.dataset.values).textContent),select=plot.querySelector('select'),svg=plot.querySelector('svg'),ns='http://www.w3.org/2000/svg';
 function el(tag,attrs,content){const n=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(content!==undefined)n.textContent=content;svg.appendChild(n);return n;}
 function draw(){svg.replaceChildren();const rows=data.filter(r=>r.layer===Number(select.value)),byStep=new Map(rows.map(r=>[r.step,r.alpha])),bins=Math.max(...rows.map(r=>r.alpha.length)),w=950/bins;
  for(let s=0;s<20;s++)for(let t=0;t<bins;t++){const a=byStep.get(s)?.[t],f=a===undefined?null:Math.max(0,Math.min(1,a/.5)),color=f===null?'#e0e4e7':`rgb(${Math.round(238-214*f)},${Math.round(247-143*f)},${Math.round(249-90*f)})`,r=el('rect',{x:62+t*w,y:38+s*13,width:Math.max(1,w-1),height:12,fill:color});const title=document.createElementNS(ns,'title');title.textContent=`去噪步 ${s+1} / DiT 层 ${Number(select.value)+1} / 视频时间片 ${t+1}: ${a===undefined?'未记录':a.toFixed(6)}`;r.appendChild(title);}
  const ticks=new Set([0,Math.floor((bins-1)/4),Math.floor((bins-1)/2),Math.floor(3*(bins-1)/4),bins-1]);for(const t of ticks)el('text',{x:62+(t+.5)*w,y:24,'font-size':12,'text-anchor':'middle'},String(t+1));for(const s of [1,5,10,15,20])el('text',{x:50,y:47+(s-1)*13,'font-size':12,'text-anchor':'end'},String(s));el('text',{x:535,y:329,'font-size':13,'text-anchor':'middle'},'视频时间片（按原顺序）');}
 select.addEventListener('change',draw);draw();
});
'''
class CheckHTML(HTMLParser):
 def __init__(self):super().__init__();self.videos=[];self.ids=[];self.external=[];self.cells=0
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if a.get('id'):self.ids.append(a['id'])
  if tag=='video':self.videos.append(a)
  if tag=='rect' and a.get('class')=='heatcell':self.cells+=1
  if tag in ('video','img','script','source','link'):
   for k in ('src','poster','href'):
    if a.get(k) and not a[k].startswith('data:'):self.external.append((tag,k,a[k]))

def build(args):
 INPUTS.clear();MEDIA.clear()
 for evidence_path in (B.parent/'operator_equivalence/REPORT.md', E/'innovation/latent_phase_calibration_20261023/POSTHOC_ROLE_ANALYSIS.md', E/'innovation/weak_residual_screen_20261023/RESULT.json'):
  INPUTS[str(evidence_path.relative_to(E))]=sha(evidence_path.read_bytes())
 status=read(args.latest/'status.json');metrics=read(args.latest/'official_metrics.json');plan=read(args.jobs)
 awq=read(args.awq) if args.awq.exists() else {'jobs':{}};awq_evidence={}
 rows=sorted(status['jobs'],key=lambda r:(r['task_id'],{'dynamic_anchor':0,'coverage_blend25':1,'heads_budget':2,'fixed0375':3,'dynamic_dof':4}.get(r['method'],9)));rowmap=unique(rows,'job_id');jobs=unique(plan['jobs'],'id');cases=unique(metrics.get('cases',[]),'job_id')
 if set(rowmap)!=set(jobs):raise ValueError('status/plan job sets differ')
 if status.get('dry_run'):raise ValueError('dry-run collection is not real evidence')
 if any(j not in rowmap or rowmap[j]['status']!='verified' for j in cases):raise ValueError('metrics include unfinished media')
 counts=Counter(r['status'] for r in rows);collected=datetime.fromtimestamp(status['collected_at_unix']).astimezone().isoformat(timespec='seconds')
 anns={};assets={};curves={};compact={};casehtml=[]
 for r in rows:
  jid=r['job_id']
  if r.get('alpha_curve_file'):
   c=read(args.latest/r['alpha_curve_file'])
   if c.get('job_id')!=jid or c.get('audit_sha256')!=r.get('audit_sha256'):raise ValueError('curve/audit identity mismatch')
   curves[jid]=c
  if r['status']!='verified':continue
  visual=args.visual/r['task_id']/r['method'];pp=visual/'PROVENANCE.json';vp=visual/'comparison.mp4'
  if not pp.exists() or not vp.exists():assets[jid]={'pending_media':True};continue
  prov=read(pp)
  if prov.get('job_id')!=jid or prov.get('generated_sha256')!=video_sha(r):raise ValueError('comparison provenance mismatch')
  uri=embed(vp,'video/mp4',jid,prov.get('comparison_sha256'));streams=MEDIA[-1]['ffprobe']['streams']
  if len(streams)!=1:raise ValueError('expected one video stream')
  stream=streams[0];frames=int(stream.get('nb_frames',0))
  if frames and frames!=prov['valid_frames']:raise ValueError('comparison frame count differs')
  if stream.get('avg_frame_rate') not in ('24/1','48/2'):raise ValueError('comparison FPS differs')
  anns[jid]=annotation(r,visual,prov);assets[jid]={'video':uri,'provenance':prov}
 svgs=diagrams();args.assets.mkdir(parents=True,exist_ok=True)
 for name,svg in svgs.items():(args.assets/f'mechanism_{name}.svg').write_text(svg)
 for r in rows:
  if r['status']!='verified':continue
  jid=r['job_id'];tid=r['task_id'];method=r['method'];case=cases.get(jid,{});a,old=anns.get(jid,(None,None));asset=assets.get(jid,{});meta=jobs[jid].get('metadata',{})
  h=f'<section class="case" id="{esc(jid)}"><div class="casehead"><div><div class="eyebrow">IVEBENCH · {esc(tid)}</div><h2>{esc(TASKS.get(tid,tid))}</h2><p>{esc(METHODS.get(method,method))}</p></div><span class="badge">真实成片 · 审计通过</span></div>'
  if asset.get('video'):
   vid='vid-'+jid;h+=f'<video id="{vid}" controls playsinline preload="metadata" src="{asset["video"]}"></video><p class="videocaption">同帧 2×2 对照：左上参考视频；右上普通编辑 Baseline；左下固定 α = .25；右下本次方法。视频与黑底标注已嵌入此 HTML。</p><div class="speed">播放速度 '+''.join(f'<button data-video="{vid}" data-speed="{v}">{v}×</button>' for v in (.25,.5,1))+'</div>'
  else:h+='<p class="pending">完整结果已核验，对照展示素材尚未整理。</p>'
  if a:h+='<p class="eventnote">'+esc(a.get('comparison',''))+'</p>'
  ref=score(case.get('controls',{}).get('source',{}),'motion_fidelity');mf=score(case,'motion_fidelity');weak=score(case.get('controls',{}).get('global_weak',{}),'motion_fidelity')
  h+='<div class="metrics-strip"><span>本次 MF <b>'+num(mf,6)+'</b></span><span>MF − 参考 <b>'+num(mf-ref if mf is not None and ref is not None else None,6,True)+'</b></span><span>MF − 固定 .25 <b>'+num(mf-weak if mf is not None and weak is not None else None,6,True)+'</b></span></div><h3>事件逐帧对齐</h3>'+events_table(a,old)
  if jid in curves:
   hm,points=heatmap(curves[jid],r);compact[jid]=points;h+='<h3>实际 α：20 个去噪步 × 50 个 DiT 层</h3>'+hm
  else:h+='<p class="small">暂无逐层强度记录；固定强度与混合比例见方法配置。</p>'
  h+='<h3>官方九指标</h3>'+metrics_table(case)
  awq_html,awq_rows=awq_table(case,r,asset.get('provenance',{}),awq);h+=awq_html
  for record in awq_rows:
   if record['job_id'] in awq_evidence and awq_evidence[record['job_id']]!=record:raise ValueError('AWQ duplicate join differs')
   awq_evidence[record['job_id']]=record
  timing=case.get('timing',{});h+='<details><summary>配对配置、实际耗时与证据</summary><dl>'
  fields=[('提示词协议',meta.get('prompt_protocol','待核查')),('随机种子',meta.get('seed')),('推理几何',json.dumps(meta.get('geometry',{}),ensure_ascii=False)),('有效视频帧',meta.get('valid_frames')),('采样步数',meta.get('sampling_steps',20)),('采样总时间',num(timing.get('sampling_seconds'),3)+' s'),('采样逐步均值',num(timing.get('mean_step_seconds'),3)+' s'),('动作标注',a.get('annotation_method') if a else '待检查'),('实际输出 SHA-256',video_sha(r)),('运行审计 SHA-256',r.get('audit_sha256'))]
  h+=''.join('<dt>'+esc(k)+'</dt><dd class="'+('evidence' if 'SHA' in k else '')+'">'+esc(str(v))+'</dd>' for k,v in fields)+'</dl><p class="small">沿用历史 actual structured prompt、seed、缓存参考、模型与几何。采样时间为本次实际记录；历史对照的硬件与 x0 采集配置有差异，不用于隔离控制器速度收益。controller_host_dispatch_seconds 只计主机派发，非 GPU 计算时间。</p>'
  if timing.get('per_step_seconds'):h+='<p class="small">每步秒数：'+', '.join(num(x,3) for x in timing['per_step_seconds'])+'</p>'
  raw={k:case.get('metrics',{}).get(k) for k,_,_ in METRICS}
  h+='<details><summary>官方原值与版本记录</summary><pre>'+esc(json.dumps(raw,ensure_ascii=False,indent=2))+'</pre></details></details></section>';casehtml.append(h)
 total=len(rows);held=counts['research_hold'];done=counts['verified'];active=total-held
 header=f'<header><div class="eyebrow">RESEARCH PROGRESS · 2026 / 10 / 23</div><h1>{TITLE}</h1><p class="lede">在已有效的同时间弱引导 α = .25 基础上，分别检验<strong>动态强度、head 能量分配和跨时刻混合</strong>，同时记录动作时序、编辑质量与内部控制行为。</p><p class="small">数据快照：{esc(collected)} · 本页为完整单文件，视频与图表可离线打开。配对沿用历史实际 structured prompt / seed / 参考缓存 / 模型 / 几何，未统一改成简单提示词。</p><div class="stats"><span class="stat"><b>{done}</b>已核验成片</span><span class="stat"><b>{counts["in_progress"]}</b>推理中</span><span class="stat"><b>{counts["pending"]}</b>待执行</span><span class="stat"><b>{held}</b>已搁置</span></div><p class="small">计划共 {total} 项，其中 {held} 项研究性搁置；活动计划 {active} 项。指标统计只纳入完成且适用的结果。</p><nav class="nav"><a href="#findings">当前结论</a><a href="#methods">方法机制</a><a href="#cases">成片对照</a><a href="#plan">任务状态</a><a href="#definitions">指标释义</a></nav></header>'
 findings='<section id="findings"><h2>当前结论</h2>'+conclusions(rows,anns,cases)+paired_summary(rows,anns,cases)+'</section>'
 methods='<section id="methods"><h2>三个独立控制轴</h2><p>原 H3 Attention 输出为 O。同一输出 query 对全部参考视频的条件输出为 R，对同一时间 bin 的条件输出为 Sₜ；原参考概率质量为 m。共有修正写作 <strong>O′ = O + αm(Sₜ − R)</strong>，之后合并 heads 并经过 Wₒ。</p><div class="diagramscroll">'+svgs['anchor']+'</div><p class="small">首步锚方案已实现；实际视频表现见对应成片。其首个有效步使用 .25，此后每个去噪步、每层连续更新 α；c = (1−α₀)/α₀ 是由先验确定的正交补代价系数，μ 是偏离 .25 的正则权重，本次 μ = 1。图中的曲线示意 A/A₀ 与 B/B₀；实际日志为数值稳定性再除以两者共同的和，闭式解保持不变。实测热图只来自采样审计。</p><details><summary>DOF 版本为何已搁置</summary><p>早期版本以 A 与 B/(d−1) 比较。实际 H3 特征中的时间切向已占较大能量，再除以 127 会使正交补权重过小。已完成机舱案例的全部 1000 次 layer 调用达到 α = .5，因此改用每层实际首步 A₀/B₀ 的相对标定。</p></details><h3>逐时间片动态强度</h3><p>同一层的不同视频时间片分别计算 Aₜ、Bₜ，并以各自首个有效步归一化。联合求解 J(a)=Σₜ[(1−aₜ)²vTₜ+3aₜ²vNₜ+0.5(aₜ−.25)²]+.625Σₜ(aₜ₊₁−aₜ)²，约束 0≤aₜ≤.5。这里 vTₜ+vNₜ=1；相邻时间片项限制强度突变，数据不足和首尾时间片使用 .25。这个目标是严格凸三对角二次规划，运行日志记录实际系数与 KKT 误差。</p><h3>基于前一步统计的层分配</h3><p>汇总上一完整去噪步的 50 层数据后，为下一步分配每层 α。以局部时间方向的相对变化作为效用，以 ‖Dₗ‖²/‖Oₗ‖² 作为层尺度，求解线性效用最大化与二次预算约束。正常前两步使用 .25；后续记录计划预算、实际执行预算和当前步能量漂移。它与逐时间片方案分别测试。</p><div class="diagramscroll">'+svgs['heads']+'</div><p class="small">正收益 heads 未全部饱和时使用图中 KKT 形式。其容量不足时，剩余预算分配到零收益 heads；无有效方向信息时使用固定 .25。守恒量是 Wₒ 之前的修正能量。</p><div class="diagramscroll">'+svgs['coverage']+'</div><p class="small">混合时固定当前 Qₜ，分别读取相邻参考时刻的 Kⱼ/Vⱼ。实际 P 限定邻时刻支持并检查行列质量与期望时间顺序；求解失败回到同时间弱引导。混合比例 .25 与外层强度 α = .25 是两个独立参数。</p></section>'
 diagnostics='<section id="diagnostics"><h2>控制信号检查</h2><p><strong>底层引导算子一致。</strong>将三个新控制器的 α 固定为 .25 后，FP32、BF16、FP16 输出与原全程弱引导逐值一致；作用位置、有效时间范围和参考概率总质量也相同。当前对比主要检验强度如何分配。</p><p><strong>原始 latent 差分包含编码位置差异。</strong>实际 H3 VAE 每 17 帧独立编码为 5 个 latent。排除同一时刻后，饮酒参考自身的同组位置／跨组位置匹配代价为 .219／1.096，手帕为 .322／1.094。整段 latent 平移测试通过，但原生编辑的已知动作延迟未被读出，因此这版读出暂不接入控制器；Attention 内部统计另行检查。</p><p><strong>扩展样例筛查。</strong>按预先写定的条件检查五组已完成的扩展任务，仅比较参考视频和固定弱引导：四组改变了场景或动作，一组已经对齐，没有“编辑成功且仍有明确动作时差”的新增样例。</p></section>'
 planrows=[]
 for r in rows:
  note={'research_hold':'DOF 饱和诊断后搁置，不计待完成任务','verified':'成片 / 审计 / SHA 已核验'}.get(r['status'],'等待真实运行或采集结果')
  if r['status']=='in_progress':note=f'已记录 {r.get("completed_forward_calls",0)} / 20 个完整 forward'
  planrows.append('<tr><td>'+esc(TASKS.get(r['task_id'],r['task_id']))+'</td><td>'+esc(METHODS.get(r['method'],r['method']))+'</td><td>'+esc(STATUS.get(r['status'],r['status']))+'</td><td>'+esc(note)+'</td></tr>')
 progress='<section id="plan"><h2>全部任务状态</h2><div class="tablewrap"><table><thead><tr><th>任务</th><th>方法</th><th>状态</th><th>证据 / 说明</th></tr></thead><tbody>'+''.join(planrows)+'</tbody></table></div><p class="small">已完成的 DOF 案例保留作为机制诊断；饮酒 DOF 已搁置。各新增方法使用独立任务与冻结输入；待执行结果不进入均值。</p>'
 partial=[]
 for r in rows:
  if r['status']!='verified' and r['job_id'] in curves:
   hm,points=heatmap(curves[r['job_id']],r);compact[r['job_id']]=points
   partial.append('<h3>'+esc(TASKS.get(r['task_id'],r['task_id']))+' · '+esc(METHODS.get(r['method'],r['method']))+'</h3>'+hm)
 if partial:progress+='<details><summary>进行中任务的实测控制记录（未进入成片指标）</summary>'+''.join(partial)+'</details>'
 progress+='</section>'
 definitions='<section id="definitions"><h2>指标与证据口径</h2><div class="definitiongrid">'+''.join('<p><strong>'+cn+'</strong><br>'+desc+'</p>' for _,cn,desc in METRICS)+'</div><p class="small">VTSS 属于官方 quality / training_suitability_assessment 实现。MF 另列减去参考自比较分数的差值，便于看运动保留缺口；动作是否提前或滞后由冻结事件的逐帧标注给出。AWQ 的 IS / CF 单列，QA 仅适用于数量修改。</p><details><summary>关联方法与可追溯来源</summary><p><a href="https://arxiv.org/html/2609.11507v1">DIAL</a>：参考 Attention 引导；<a href="https://arxiv.org/html/2410.02416v1">APG</a>：引导方向分解；<a href="https://arxiv.org/html/2603.06289v2">FlowMotion</a>：视频运动相关的投影控制。此页描述本地实现与实测进展。</p><p class="small">来源：collector latest/status.json、official_metrics.json、实际 alpha_curves、独立 AWQ 导出（逐项输入 SHA 与配置）；成片 PROVENANCE.json / ANNOTATION.json；历史冻结事件标注。控制器离线反事实不进入实测热图、视频结果或指标分母。</p><pre>'+esc(json.dumps({'input_sha256':INPUTS,'completed_media_cases':done,'plan_count':total,'research_hold':held,'metrics_case_count':len(cases)},ensure_ascii=False,indent=2))+'</pre></details></section>'
 data={'schema':'h3-research-report-evidence-v1','collected_at':collected,'plan_count':total,'active_plan':active,'research_hold':held,'completed_cases':done,'metrics_cases':len(cases),'curves':compact,'awq':awq_evidence,'input_sha256':dict(INPUTS)}
 datajson=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
 html='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+TITLE+' · 实验进展</title><style>'+CSS+'</style></head><body><main>'+header+findings+methods+diagnostics+'<div id="cases"></div>'+''.join(casehtml)+progress+definitions+'<footer class="footer">自动生成的研究进展页 · 整理真实采集证据 · 重新构建可接入后续成片与标注。</footer></main><div id="tooltip" role="tooltip"></div><script type="application/json" id="report-evidence">'+datajson+'</script><script>'+JS+'</script></body></html>'
 parser=CheckHTML();parser.feed(html)
 if parser.external:raise ValueError('nonembedded media/script asset')
 if len(parser.ids)!=len(set(parser.ids)):raise ValueError('duplicate HTML ID')
 if len(parser.videos)!=sum(bool(x.get('video')) for x in assets.values()):raise ValueError('video count mismatch')
 for video in parser.videos:
  if 'controls' not in video:raise ValueError('missing native controls')
  raw=base64.b64decode(video['src'].split(',',1)[1],validate=True)
  if sha(raw) not in {m['sha256'] for m in MEDIA}:raise ValueError('embedded media changed')
 for bad in ('/Users/','/data4/','/home/','PRIVATE_HOST_PREFIX_','ssh-ed25519','BEGIN PRIVATE KEY'):
  if bad in html:raise ValueError('private execution detail leaked: '+bad)
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(html)
 checks={'schema':'h3-report-structure-checks-v1','status':'passed','report_sha256':sha(html.encode()),'report_bytes':len(html.encode()),'completed_cases':done,'embedded_videos':len(parser.videos),'measured_heatmaps':len(compact),'heatmap_grid_cells':parser.cells,'recorded_layer_points':{k:len(v) for k,v in compact.items()},'plan_count':total,'research_hold':held,'active_plan':active,'media':MEDIA,'input_sha256':dict(INPUTS),'external_asset_count':len(parser.external),'html_ids_unique':True,'media_sha_verified':True,'annotation_intervals_verified':True,'browser_check':'blocked_file_protocol','browser_check_reason':'CUA safety policy accepts only http/https and prohibits alternate-browser or local-HTTP bypass; no bypass attempted.','visual_review':'browser page review not performed; static and media checks only','gpu_or_queue_operations':False,'awq_verified_job_count':len(awq_evidence),'awq_verified_score_count':sum(m['status']=='done' for r in awq_evidence.values() for m in r['metrics']),'awq_input_sha_verified':True}
 (args.assets/'BUILD_CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2));(args.assets/'MEASURED_CURVES.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
 print(json.dumps({k:checks[k] for k in ('status','report_bytes','completed_cases','embedded_videos','measured_heatmaps','recorded_layer_points','active_plan','research_hold')},ensure_ascii=False));return checks

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--awq',type=Path,default=E/'metrics/qwen_runtime/adaptive_awq_scores.json')
 p.add_argument('--latest',type=Path,default=B/'results_tools/latest');p.add_argument('--jobs',type=Path,default=B/'results_tools/all_jobs.json');p.add_argument('--visual',type=Path,default=E/'showcases/adaptive_strength_20261023/visual');p.add_argument('--assets',type=Path,default=E/'showcases/adaptive_strength_20261023/report_assets');p.add_argument('--output',type=Path,default=REPO/'reports/H3_动态强度与跨时刻混合_实验进展_20261023.html')
 build(p.parse_args())
if __name__=='__main__':main()
