"""Build five existing prompt comparisons with native browser controls; no inference."""
import base64,hashlib,html,json,re,shutil,subprocess,tempfile
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent;E=HERE.parent;TARGET=E.parent/'reports/H3_六段提示词_五组普通编辑_20261022.html'
CASES=[('short_0252','角色替换 — 机舱男子替换为年长女人'),('short_0358','外观编辑 — 饮酒男子戴上眼镜'),('short_0085','外观编辑 — 女子头发改为红色'),('long_0059','物体编辑 — 男子手中添加白手帕'),('short_0343','角色替换 — 浴室女子替换为医生')]
METRICS=[('motion_fidelity','MF','运动保真度·相对参考'),('subject_consistency','SC','主体一致性'),('background_consistency','BC','背景一致性'),('temporal_flickering','TF','时序稳定性'),('motion_smoothness','MS','运动平滑度'),('vtss','VTSS','编辑文本匹配'),('overall_semantic_consistency','OSC','整体语义一致性'),('phrase_semantic_consistency','PSC','目标语义一致性'),('semantic_fidelity','SF','语义保真度')]
LABELS=['参考视频','原提示词 · 普通编辑','六段简写 · 普通编辑']
PAIRS=json.loads((HERE/'paired_metrics.json').read_text());SUMMARY=json.loads((HERE/'paired_summary.json').read_text())
def table(rows,awq=False):
 metrics=[('instruction_satisfaction','IS','指令满足度 /5'),('content_fidelity','CF','内容保真度 /5')] if awq else METRICS
 values={}
 for method in ['native','six_section_native']:
  for key,_,_ in metrics:
   vals=[]
   for p in rows:
    v=p['awq'][method][key]['score'] if awq else p['scores'][method][key]
    if v is not None: vals.append(v-(p['scores']['source'][key] if key=='motion_fidelity' else 0))
   values[method,key]=sum(vals)/len(vals) if len(vals)==len(rows) else None
 out='<div class="scroll"><table><thead><tr><th>提示词</th>'+''.join(f'<th class="{"mf" if k=="motion_fidelity" else ""}">{ab} ↑<small>{cn}</small></th>' for k,ab,cn in metrics)+'</tr></thead><tbody>'
 for method,label in [('native',LABELS[1]),('six_section_native',LABELS[2]),('difference','六段简写 − 原提示词')]:
  out+='<tr><th>'+label+'</th>'
  for key,_,_ in metrics:
   a=values['native',key];b=values['six_section_native',key];v=(b-a if a is not None and b is not None else None) if method=='difference' else values[method,key]
   mark='<b class="best"> ✓</b>' if method!='difference' and v is not None and a is not None and b is not None and v==max(a,b) else ''
   text='待评' if v is None else (f'{v:+.4f}' if method=='difference' or key=='motion_fidelity' else f'{v:.4f}')
   out+=f'<td class="{"mf" if key=="motion_fidelity" else ""}">{text}{mark}</td>'
  out+='</tr>'
 return out+'</tbody></table></div>'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build():
 # Reuse embedded source/six videos from previous version when available.
 embeds=re.findall(r'data:video/mp4;base64,([A-Za-z0-9+/=]+)',TARGET.read_text()) if TARGET.exists() else []
 embedded={}
 if len(embeds)==10:
  for b in embeds:
   raw=base64.b64decode(b);embedded[hashlib.sha256(raw).hexdigest()]=raw
 catalog={c['task_id']:c for c in json.loads((E/'innovation/pilot_ten/manifest_preparation/catalog.json').read_text())['cases']}
 sections=[];records=[]
 with tempfile.TemporaryDirectory(prefix='h3-prompt-five-') as td:
  td=Path(td);caption=Image.new('RGB',(2304,92),'black');draw=ImageDraw.Draw(caption);font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Unicode.ttf',27)
  for i,label in enumerate(LABELS):
   bb=draw.textbbox((0,0),label,font=font);draw.text((i*768+(768-bb[2]+bb[0])/2,12-bb[1]),label,font=font,fill='white')
  caption.save(td/'caption.png')
  for sid,title in CASES:
   p=next(x for x in PAIRS if x['task_id']==sid);jobs=[p['jobs'][m] for m in ['source','native','six_section_native']];out=HERE/(sid+'_prompt_comparison.mp4');inputs=[]
   for j in jobs:
    f=td/(j['id']+'.mp4');local=Path(catalog[sid]['reference_video']) if j['method']=='source' else E/'showcases/partial_rope_pilots_20261022/visual'/sid/(j['method']+'.mp4')
    if j['sha256'] in embedded:f.write_bytes(embedded[j['sha256']])
    elif local.exists() and digest(local)==j['sha256']:shutil.copyfile(local,f)
    else:subprocess.run(['scp','-q','-o','ConnectTimeout=12','H3_HOST_CONFIGURE_LOCALLY:'+j['video'],str(f)],check=True,timeout=180)
    assert digest(f)==j['sha256'];inputs+=['-i',str(f)]
   n=jobs[0]['valid_frames'];fps=jobs[0]['fps'];filters=[]
   for i,j in enumerate(jobs):
    x,y,w,h=j['crop_xywh'];filters.append(f'[{i}:v]trim=end_frame={n},setpts=PTS-STARTPTS,crop={w}:{h}:{x}:{y},scale=768:432:flags=lanczos,setsar=1[v{i}]')
   filters+=['[v0][v1][v2]hstack=inputs=3[top]','[top][3:v]vstack=inputs=2:shortest=1[out]']
   subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',*inputs,'-loop','1','-framerate',str(fps),'-i',str(td/'caption.png'),'-filter_complex_threads','2','-filter_complex',';'.join(filters),'-map','[out]','-an','-frames:v',str(n),'-r',str(fps),'-c:v','libx264','-threads','4','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(out)],check=True,timeout=180)
   probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,nb_frames,r_frame_rate','-of','json',str(out)]))['streams'][0];assert probe['width']==2304 and probe['height']==524 and int(probe['nb_frames'])==n
   data=base64.b64encode(out.read_bytes()).decode();delta=p['mf_delta_six_minus_prior'];prior_label='官方一句话指令' if sid=='short_0343' else ('三段格式，含通用保留指令' if sid=='short_0252' else '详细六段格式，含场景与动作保留描述')
   sections.append(f'<section><h2>{html.escape(title)}</h2><p class="sub">IVEBench · {sid} · {html.escape(p["official_edit_prompt"])}</p><video controls playsinline preload="metadata" src="data:video/mp4;base64,{data}"></video><p>六段简写相比原提示词，MF变化 {delta:+.4f}。</p>{table([p])}{table([p],True)}<details><summary>实际提示词与比较设置</summary><p>原提示词：{prior_label}。两版采用相同seed、H3权重、Euler 20步、分辨率与采样帧数；均为普通编辑。</p><h3>原提示词</h3><pre>{html.escape(p["prior_prompt"])}</pre><h3>六段简写</h3><pre>{html.escape(p["six_section_prompt"])}</pre></details></section>')
   records.append({'task_id':sid,'probe':probe,'output':str(out),'sha256':digest(out),'inputs':[{'id':j['id'],'sha256':j['sha256']} for j in jobs]});print(sid,probe,flush=True)
 css='body{margin:0;background:#f5f6f8;color:#18202b;font:16px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}main{max-width:1500px;margin:36px auto;padding:0 24px}h1{font-size:30px}h2{font-size:23px}section{background:white;border:1px solid #dce1e8;border-radius:12px;padding:24px;margin:24px 0}video{width:100%;background:black;border-radius:6px}.sub,small{color:#667180}small{display:block;font-size:11px;font-weight:400}.scroll{overflow:auto;margin:12px 0}table{width:100%;border-collapse:collapse;font-size:14px;white-space:nowrap}th,td{padding:12px 9px;text-align:center;border-bottom:1px solid #e6e9ee}th:first-child{text-align:left}.mf{border-left:2px solid #a8d9b8;border-right:2px solid #a8d9b8;background:#f3fbf5}thead .mf{border-top:2px solid #a8d9b8}tbody tr:last-child .mf{border-bottom:2px solid #a8d9b8}.best{color:#168c48}pre{white-space:pre-wrap;font:13px/1.6 monospace}details{margin-top:16px;color:#57616e}summary{cursor:pointer}'
 page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>六段提示词 · 五组普通编辑</title><style>'+css+'</style><main><h1>六段提示词 · 五组普通编辑</h1><p>每组依次展示参考视频、原提示词普通编辑、六段简写普通编辑。</p><section><h2>五组平均指标</h2><p>六段简写的MF均值下降0.0156，五组中两组上升；SC上升0.0180，BC上升0.0026。IS与CF均值持平，运动保真度和语义保真度未获得整体改善。</p><p class="sub">原提示词：机舱使用三段格式并附通用保留指令；饮酒、红发、手帕使用详细六段；医生使用官方一句话。新版统一为六段简写，仅summary填写官方指令，其余字段标为未指定。前四组同时改变了提示词内容，医生组仅比较格式。</p>'+table(PAIRS)+table(PAIRS,True)+'<p class="sub">MF显示相对参考视频的差值；差值行显示六段简写减原提示词。九项数值指标和IS/CF均为越高越好，绿色勾表示本表最高值。IS/CF使用Qwen2.5-VL-72B 4-bit AWQ与官方评分提示词；原版在.41评测，新版在.60采用CPU跨卡转运，配置记录分别保留。QA在这五项任务中不适用。</p></section>'+''.join(sections)+'</main></html>'
 TARGET.write_text(page);validation={'html':str(TARGET),'bytes':TARGET.stat().st_size,'embedded_videos':page.count('data:video/mp4;base64,'),'native_controls':page.count('<video controls '),'custom_controls':False,'scientific_visual_review':'not_performed','records':records};assert validation['embedded_videos']==validation['native_controls']==5
 (HERE/'showcase_validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2));print(TARGET,TARGET.stat().st_size)
if __name__=='__main__':build()
